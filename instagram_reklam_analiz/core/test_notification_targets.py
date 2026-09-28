from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ActivityLog, Ad, Notification, SystemErrorLog
from core.services.activity_service import object_activity_link, record_activity_from_notification
from core.services.platform_token_service import _notify_admins_for_env_failure, _validate_meta_ad_library_token


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class NotificationTargetTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="notification-admin",
            email="notification-admin@example.com",
            password="test-password",
            is_staff=True,
        )

    def test_env_failure_notification_opens_exact_error_record(self):
        _notify_admins_for_env_failure(
            "META_AD_LIBRARY_ACCESS_TOKEN",
            "Application does not have permission for this action",
        )

        error_log = SystemErrorLog.objects.get(tags__token_label="META_AD_LIBRARY_ACCESS_TOKEN")
        notification = Notification.objects.get(user=self.admin)
        expected_target = reverse("admin:core_systemerrorlog_change", args=[error_log.pk])
        self.assertEqual(notification.link, expected_target)

        self.client.force_login(self.admin)
        center_response = self.client.get(reverse("notification_center"))
        self.assertContains(center_response, 'class="notification-row-open"')
        self.assertContains(center_response, reverse("open_notification", args=[notification.pk]))

        response = self.client.get(reverse("open_notification", args=[notification.pk]))

        self.assertRedirects(response, expected_target, fetch_redirect_response=False)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_repeated_env_failure_reuses_recent_error_record(self):
        for _ in range(2):
            _notify_admins_for_env_failure(
                "META_AD_LIBRARY_ACCESS_TOKEN",
                "Application does not have permission for this action",
            )

        self.assertEqual(SystemErrorLog.objects.filter(tags__token_label="META_AD_LIBRARY_ACCESS_TOKEN").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.admin).count(), 1)

    @patch("core.services.platform_token_service.requests.get")
    def test_meta_details_reach_notification_without_truncation_or_token(self, get):
        token = "secret-test-token"
        explanation = "Complete API registration. " * 30 + token
        get.return_value = Mock(ok=False)
        get.return_value.json.return_value = {"error": {
            "message": "Application does not have permission for this action",
            "code": 10,
            "error_subcode": 2332004,
            "error_user_title": "Access required",
            "error_user_msg": explanation,
            "fbtrace_id": "test-trace",
        }}
        result = _validate_meta_ad_library_token(token)
        self.assertFalse(result["valid"])
        _notify_admins_for_env_failure("META_AD_LIBRARY_ACCESS_TOKEN", result["error"])
        notification = Notification.objects.get(user=self.admin)
        error_log = SystemErrorLog.objects.get(tags__token_label="META_AD_LIBRARY_ACCESS_TOKEN")
        for message in (notification.message, error_log.extra_data["diagnostic_message"]):
            self.assertIn("error_subcode: 2332004", message)
            self.assertIn(explanation.replace(token, "[ACCESS_TOKEN]"), message)
            self.assertIn("fbtrace_id: test-trace", message)
            self.assertNotIn(token, message)

    def test_generic_dashboard_notification_resolves_named_ad(self):
        ad = Ad.objects.create(user=self.admin, name="Yaz İndirimi Reklamı", source_type="OWN")
        notification = Notification.objects.create(
            user=self.admin,
            title="Demo ROAS fırsatı",
            message="Yaz İndirimi Reklamı bugün yüksek ROAS üretti.",
            link="/dashboard/",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("open_notification", args=[notification.pk]))

        self.assertRedirects(response, object_activity_link(ad), fetch_redirect_response=False)

    def test_legacy_competitor_ad_link_opens_exact_ad(self):
        ad = Ad.objects.create(user=self.admin, name="Rakip Reklam", source_type="COMPETITOR")
        notification = Notification.objects.create(
            user=self.admin,
            title="Rakip reklamında yüksek etkileşim",
            message="Rakip Reklam yüksek etkileşim yakaladı.",
            link=f"/rakip-reklam-paneli/?ad={ad.pk}",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("open_notification", args=[notification.pk]))

        self.assertRedirects(response, object_activity_link(ad), fetch_redirect_response=False)

    def test_notification_creates_activity_record(self):
        notification = Notification.objects.create(
            user=self.admin,
            title="Kampanya güncellendi",
            message="Kampanya durumu değişti.",
            link="/campaign-center/",
        )

        activity = record_activity_from_notification(notification)

        self.assertIsNotNone(activity)
        self.assertTrue(ActivityLog.objects.filter(pk=activity.pk, user=self.admin).exists())
