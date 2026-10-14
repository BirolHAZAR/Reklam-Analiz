import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import MembershipPlan, Platform, PlatformAccount, PlatformSyncJob, UserSubscription


class CampaignPanelCsrfTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="panel-sync-owner")
        plan = MembershipPlan.objects.create(name="panel-sync-plan", display_name="Panel", price=100,
                                             price_with_kdv=120, features="Sync")
        UserSubscription.objects.create(user=self.user, plan=plan, start_date=timezone.localdate(),
                                        end_date=timezone.localdate()+timedelta(days=30), is_active=True)
        platform, _ = Platform.objects.get_or_create(code="google_ads", defaults={"name": "Google Ads"})
        self.account = PlatformAccount.objects.create(
            user=self.user, platform=platform, account_id="123", access_token="test-token",
        )
        self.browser = Client(enforce_csrf_checks=True)
        self.browser.force_login(self.user)
        session = self.browser.cookies[settings.SESSION_COOKIE_NAME].value
        self.cookies = (f"{settings.SESSION_COOKIE_NAME}={session}; "
                        f"{settings.CSRF_COOKIE_NAME}={'a' * 32}; {settings.CSRF_COOKIE_NAME}={'b' * 32}")

    @patch("core.views.campaign_panel.sync_platform_account_ads")
    def test_rendered_token_works_with_duplicate_csrf_cookies(self, task):
        page = self.browser.get(reverse("campaign_panel"), HTTP_COOKIE=self.cookies)
        self.assertEqual(page.status_code, 200, str(page.headers))
        token = re.search(r"const csrftoken = '([a-zA-Z0-9]+)'", page.content.decode()).group(1)
        response = self.browser.post(
            reverse("api_campaign_panel_sync_account", args=[self.account.pk]),
            HTTP_COOKIE=self.cookies, HTTP_X_CSRFTOKEN=token,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        job = PlatformSyncJob.objects.get(user=self.user, platform_account=self.account)
        self.assertEqual(response.json()["job_id"], job.pk)
        task.delay.assert_called_once_with(job.pk)

    @patch("core.views.campaign_panel.sync_platform_account_ads")
    def test_stale_cookie_token_remains_rejected_without_creating_job(self, task):
        response = self.browser.post(
            reverse("api_campaign_panel_sync_account", args=[self.account.pk]),
            HTTP_COOKIE=self.cookies, HTTP_X_CSRFTOKEN="a" * 32,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PlatformSyncJob.objects.exists())
        task.delay.assert_not_called()

    @patch("core.views.campaign_panel.sync_platform_account_ads")
    def test_repeated_clicks_reuse_pending_and_running_jobs(self, task):
        page = self.browser.get(reverse("campaign_panel"), HTTP_COOKIE=self.cookies)
        token = re.search(r"const csrftoken = '([a-zA-Z0-9]+)'", page.content.decode()).group(1)
        url = reverse("api_campaign_panel_sync_account", args=[self.account.pk])
        def click():
            return self.browser.post(url, HTTP_COOKIE=self.cookies, HTTP_X_CSRFTOKEN=token)
        first = click().json()["job_id"]
        self.assertEqual(click().json()["job_id"], first)
        PlatformSyncJob.objects.filter(pk=first).update(status="running")
        self.assertEqual(click().json()["job_id"], first)
        task.delay.assert_called_once_with(first)
        PlatformSyncJob.objects.filter(pk=first).update(status="failed")
        self.assertNotEqual(click().json()["job_id"], first)
        self.assertEqual(task.delay.call_count, 2)

    @patch("core.views.campaign_panel.sync_platform_account_ads")
    def test_organic_profile_does_not_enqueue_invalid_ad_account_request(self, task):
        platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.account.platform = platform
        self.account.extra_data = {"auth_type": "instagram_login"}
        self.account.save(update_fields=["platform", "extra_data"])
        response = self.browser.post(reverse("api_campaign_panel_sync_account", args=[self.account.pk]),
            HTTP_COOKIE=self.cookies, HTTP_X_CSRFTOKEN="b" * 32)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "meta_ad_account_required")
        self.assertFalse(PlatformSyncJob.objects.exists())
        task.delay.assert_not_called()

    def test_instagram_sources_keep_canonical_ids_and_exclude_other_users(self):
        from core.models import PlatformConnection
        from core.services.campaign_panel_service import build_platform_account_payload
        instagram, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        meta, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        profile = PlatformAccount.objects.create(user=self.user, platform=instagram, account_id="profile",
            access_token="test-token", extra_data={"auth_type": "instagram_login"})
        connection = PlatformConnection.objects.create(user=self.user, platform=meta, access_token="meta-token",
            extra_data={"source": "ads_oauth"})
        sources = [PlatformAccount.objects.create(user=self.user, platform=meta, connection=connection,
            account_id=str(i), access_token="test-token") for i in range(2)]
        other = get_user_model().objects.create_user(username="foreign-meta-owner")
        PlatformAccount.objects.create(user=other, platform=meta, connection=connection,
            account_id="foreign", access_token="test-token")
        payload = build_platform_account_payload(self.user, platform_code="instagram")[0]["accounts"][0]
        self.assertTrue(payload["organic_instagram"])
        self.assertEqual({s["id"] for s in payload["ad_sources"]}, {s.pk for s in sources})
        scoped = build_platform_account_payload(self.user, platform_code="instagram",
            accounts_queryset=PlatformAccount.objects.filter(pk__in=[profile.pk, sources[0].pk]))
        self.assertEqual([s["id"] for s in scoped[0]["accounts"][0]["ad_sources"]], [sources[0].pk])
