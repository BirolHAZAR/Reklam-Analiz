from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Platform, PlatformAccount, PlatformConnection, PlatformSyncJob
from core.services.ads_integrations import IntegrationError
from core.services.youtube_channel_sync import sync_youtube_channel
from core.tasks.account_read_sync import sync_account_read_job


class SyncCenterActionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sync-staff", is_staff=True)
        self.other = get_user_model().objects.create_user(username="other-sync")
        self.youtube, _ = Platform.objects.get_or_create(code="youtube", defaults={"name": "YouTube"})
        self.meta, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.connection = PlatformConnection.objects.create(user=self.user, platform=self.youtube,
            status="active", is_active=True, access_token="private-token", extra_data={"source": "google_read_oauth"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.youtube, account_id="channel-id",
            connection=self.connection, access_token="private-token")
        self.client.force_login(self.user)
        self.url = reverse("sync_center_account", args=[self.account.pk])

    @patch("core.tasks.account_read_sync.sync_account_read_job.delay")
    def test_youtube_queues_channel_read_once_and_returns_owned_status(self, delay):
        first = self.client.post(self.url)
        second = self.client.post(self.url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["job_id"], second.json()["job_id"])
        delay.assert_called_once_with(first.json()["job_id"])
        job = PlatformSyncJob.objects.get(pk=first.json()["job_id"])
        self.assertEqual(job.user, self.user)
        job.status, job.error_message = "failed", "private-token provider-response"
        job.save()
        status = self.client.get(first.json()["status_url"])
        self.assertNotContains(status, "private-token")
        self.assertEqual(status.json()["status"], "failed")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(first.json()["status_url"]).status_code, 404)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_post_csrf_and_subscription_are_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        self.user.is_staff = False
        self.user.save()
        with patch("core.services.sync_policy.get_user_entitlement_plan", return_value=None):
            self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertFalse(PlatformSyncJob.objects.exists())

    @patch("core.tasks.ads_pipeline.sync_platform_account_ads.delay")
    @patch("core.tasks.account_read_sync.sync_account_read_job.delay")
    def test_ad_and_organic_accounts_use_separate_tasks(self, read_delay, ad_delay):
        ad = PlatformAccount.objects.create(user=self.user, platform=self.meta, account_id="ad-account", access_token="token")
        response = self.client.post(reverse("sync_center_account", args=[ad.pk]))
        ad_delay.assert_called_once_with(response.json()["job_id"])
        read_delay.assert_not_called()
        instagram, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        profile = PlatformAccount.objects.create(user=self.user, platform=instagram, account_id="profile", access_token="token")
        response = self.client.post(reverse("sync_center_account", args=[profile.pk]))
        read_delay.assert_called_once_with(response.json()["job_id"])

    @patch("core.tasks.account_read_sync.sync_account_read_job.delay", side_effect=RuntimeError("private-broker-url"))
    def test_queue_failure_is_visible_and_does_not_leave_pending_job(self, delay):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private-broker-url", status_code=503)
        self.assertEqual(PlatformSyncJob.objects.get().status, "failed")

    def test_page_shows_named_account_form_and_existing_pending_job(self):
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account)
        response = self.client.get(reverse("sync_center"))
        self.assertContains(response, self.url)
        self.assertContains(response, "Kanal verileri")
        self.assertContains(response, reverse("sync_center_job_status", args=[job.pk]))
        self.assertContains(response, "Senkronizasyon sürüyor")

    @patch("core.services.youtube_channel_sync.api.connection_token", return_value="fresh-token")
    @patch("core.services.youtube_channel_sync.api.discover_accounts")
    def test_youtube_success_refreshes_real_counters_and_recovers_old_ad_error(self, discover, token):
        discover.return_value = [{"id": "channel-id", "kind": "youtube_channel",
            "statistics": {"viewCount": "123", "videoCount": "4", "hiddenSubscriberCount": True}}]
        PlatformSyncJob.objects.create(user=self.user, platform_account=self.account, status="failed",
                                      error_message="unsupported_for_ad_sync")
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account)
        sync_account_read_job.run(job.pk)
        job.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(self.account.extra_data["youtube_channel_statistics"]["viewCount"], 123)
        self.assertNotIn("subscriberCount", self.account.extra_data["youtube_channel_statistics"])
        self.assertIsNotNone(self.account.last_sync)
        sync_account_read_job.run(job.pk)
        discover.assert_called_once_with("youtube", "fresh-token")
        row = next(p for p in self.client.get(reverse("sync_center")).context["platforms"] if p["code"] == "youtube")
        self.assertEqual(row["status_label"], "Senkron tamam")

    @patch("core.services.youtube_channel_sync.api.connection_token", return_value="fresh-token")
    @patch("core.services.youtube_channel_sync.api.discover_accounts")
    def test_wrong_channel_or_invalid_counters_do_not_mark_success(self, discover, token):
        for rows in ([], [{"id": "another-channel", "kind": "youtube_channel", "statistics": {}}],
                     [{"id": "channel-id", "kind": "youtube_channel", "statistics": {"viewCount": "-1", "videoCount": "0"}}],
                     [{"id": "channel-id", "kind": "youtube_channel", "statistics": {}}]):
            discover.return_value = rows
            with self.assertRaises(IntegrationError):
                sync_youtube_channel(self.account)
            self.account.refresh_from_db()
            self.assertIsNone(self.account.last_sync)

    @patch("core.services.youtube_channel_sync.api.connection_token")
    def test_foreign_connection_is_rejected_before_google_call(self, token):
        self.connection.user = self.other
        self.connection.save()
        with self.assertRaises(IntegrationError):
            sync_youtube_channel(self.account)
        token.assert_not_called()

    @patch("core.services.youtube_channel_sync.sync_youtube_channel", side_effect=RuntimeError("private-token raw-response"))
    def test_read_failure_keeps_old_success_time_and_sanitizes_job(self, read):
        job = PlatformSyncJob.objects.create(user=self.user, platform_account=self.account)
        sync_account_read_job.run(job.pk)
        job.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(job.status, "failed")
        self.assertNotIn("private", job.error_message)
        self.assertIsNone(self.account.last_sync)

    @patch("core.tasks.sync_tasks.sync_organic_account.delay")
    @patch("core.services.sync_policy.acquire_sync_lock", return_value=("key", True))
    @patch("core.services.sync_policy.is_sync_due", return_value=True)
    def test_daily_dispatch_includes_authorized_youtube_channel(self, due, lock, delay):
        from core.tasks.sync_tasks import sync_due_organic_accounts
        self.assertEqual(sync_due_organic_accounts.run()["queued"], 1)
        delay.assert_called_once_with(self.account.pk)
        self.account.extra_data = {"organic_last_sync_at": timezone.now().isoformat()}
        self.account.save()
        self.assertEqual(sync_due_organic_accounts.run()["queued"], 0)
