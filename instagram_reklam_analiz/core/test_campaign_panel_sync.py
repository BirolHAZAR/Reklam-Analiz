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
