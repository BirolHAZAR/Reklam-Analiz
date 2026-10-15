import base64
from datetime import timedelta
import hashlib
import hmac
from io import StringIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Platform, PlatformAccount, PlatformConnection, IntegrationApplication


@override_settings(FACEBOOK_APP_ID="app-1", FACEBOOK_APP_SECRET="secret-1",
                   INSTAGRAM_APP_ID="ig-app", INSTAGRAM_APP_SECRET="ig-secret")
class MetaDeauthorizationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="callback-owner")
        self.platform, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.connection = PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="private-token", refresh_token="private-refresh", scopes=["ads_read"],
            extra_data={"meta_app_id": "app-1", "meta_user_id": "123", "source": "ads_oauth"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=self.platform,
            connection=self.connection, account_id="act_900", access_token="private-token")
        self.client = Client(enforce_csrf_checks=True)
        self.url = reverse("meta_deauthorize", args=["facebook"])

    def signed(self, secret="secret-1", **overrides):
        data = {"algorithm": "HMAC-SHA256", "user_id": "123",
                "issued_at": int(timezone.now().timestamp()), **overrides}
        encode = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")
        payload = encode(json.dumps(data).encode())
        return encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()) + "." + payload

    def test_signed_anonymous_post_revokes_tokens_and_is_idempotent(self):
        for _ in range(2):
            response = self.client.post(self.url, {"signed_request": self.signed()})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"success": True})
        self.connection.refresh_from_db()
        self.account.refresh_from_db()
        self.assertFalse(self.connection.is_active)
        self.assertEqual(self.connection.status, "disconnected")
        self.assertEqual(self.connection.access_token, "")
        self.assertEqual(self.connection.refresh_token, "")
        self.assertEqual(self.connection.scopes, [])
        self.assertFalse(self.account.is_active)
        self.assertEqual(self.account.access_token, "")

    def test_invalid_signatures_payloads_and_future_events_do_not_mutate_data(self):
        for signed in [None, "", "bad", "x.y.z", "a." + "a" * 9000, self.signed(secret="wrong"),
                       self.signed(algorithm="none"), self.signed(user_id="not-a-number"),
                       self.signed(issued_at=True), self.signed(issued_at=-1),
                       self.signed(issued_at=int(timezone.now().timestamp()) + 900),
                       self.signed(app_id="another-app")]:
            with self.subTest(signed_type=type(signed).__name__):
                response = self.client.post(self.url, {"signed_request": signed or ""})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), {"error": "invalid_signed_request"})
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.access_token, "private-token")

    def test_provider_subject_is_not_a_local_user_primary_key(self):
        response = self.client.post(self.url, {"signed_request": self.signed(user_id=str(self.user.pk))})
        self.assertEqual(response.status_code, 200)
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.is_active)

    def test_same_provider_subject_revokes_all_local_connections(self):
        other_user = get_user_model().objects.create_user(username="second-local-account")
        second = PlatformConnection.objects.create(user=other_user, platform=self.platform,
            access_token="second-token", extra_data=dict(self.connection.extra_data))
        self.assertEqual(self.client.post(self.url, {"signed_request": self.signed()}).status_code, 200)
        second.refresh_from_db()
        self.assertFalse(second.is_active)
        self.assertEqual(second.access_token, "")

    @override_settings(SUBSCRIPTION_ACCESS_ENFORCED=False)
    @patch("core.services.plan_limits.ensure_platform_account_capacity")
    def test_account_selection_preserves_verified_callback_identity(self, capacity):
        self.connection.extra_data.update(pending=True, choices=[{"id": "act_900", "name": "Owned account"}])
        self.connection.save()
        client = Client()
        client.force_login(self.user)
        session = client.session
        session["ads_pending:facebook"] = self.connection.pk
        session.save()
        response = client.post(reverse("integration_select", args=["facebook"]), {"accounts": ["act_900"]})
        self.assertEqual(response.status_code, 302)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.extra_data["meta_user_id"], "123")
        self.assertEqual(self.connection.extra_data["meta_app_id"], "app-1")
        self.assertNotIn("pending", self.connection.extra_data)

    def test_app_and_provider_isolation_and_new_authorization_survive(self):
        instagram, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        for changes in [{"meta_app_id": "other"}, {"platform": instagram}, {"new": True}]:
            metadata = {"meta_user_id": "123", "meta_app_id": changes.get("meta_app_id", "app-1")}
            connection = PlatformConnection.objects.create(user=self.user,
                platform=changes.get("platform", self.platform), access_token="keep", extra_data=metadata)
            if changes.get("new"):
                PlatformConnection.objects.filter(pk=connection.pk).update(created_at=timezone.now() + timedelta(days=1))
            self.client.post(self.url, {"signed_request": self.signed()})
            connection.refresh_from_db()
            self.assertTrue(connection.is_active)
            self.assertEqual(connection.access_token, "keep")

    def test_instagram_accepts_oauth_subject_or_professional_profile_namespace(self):
        platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.connection.platform = platform
        self.connection.extra_data = {"meta_app_id": "ig-app", "meta_user_id": "456",
                                      "instagram_business_account_id": "789"}
        self.connection.save()
        url = reverse("meta_deauthorize", args=["instagram"])
        for subject in ["456", "789"]:
            self.connection.is_active = True
            self.connection.access_token = "token"
            self.connection.save()
            self.assertEqual(self.client.post(url, {"signed_request": self.signed(
                secret="ig-secret", user_id=subject)}).status_code, 200)
            self.connection.refresh_from_db()
            self.assertFalse(self.connection.is_active)

    def test_disabled_application_still_accepts_its_own_revocation(self):
        IntegrationApplication.objects.create(provider="facebook", client_id="saved-app",
                                             client_secret="saved-secret", enabled=False)
        self.connection.extra_data["meta_app_id"] = "saved-app"
        self.connection.save()
        response = self.client.post(self.url, {"signed_request": self.signed(secret="saved-secret")})
        self.assertEqual(response.status_code, 200)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.is_active)

    def test_method_provider_and_missing_configuration_fail_closed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(reverse("meta_deauthorize", args=["google_ads"])).status_code, 404)
        with override_settings(FACEBOOK_APP_SECRET=""):
            self.assertEqual(self.client.post(self.url, {"signed_request": self.signed()}).status_code, 503)

    @patch("core.management.commands.backfill_meta_callback_subjects._request")
    def test_existing_connection_backfill_is_verified_dry_run_by_default(self, request):
        self.connection.extra_data = {"source": "ads_oauth"}
        self.connection.save()
        request.return_value = {"data": {"is_valid": True, "app_id": "app-1", "user_id": "123"}}
        output = StringIO()
        call_command("backfill_meta_callback_subjects", username=self.user.username, stdout=output)
        self.connection.refresh_from_db()
        self.assertNotIn("meta_user_id", self.connection.extra_data)
        call_command("backfill_meta_callback_subjects", username=self.user.username, apply=True, stdout=output)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.extra_data["meta_user_id"], "123")
        self.assertNotIn("private-token", output.getvalue())
        self.assertNotIn("secret-1", output.getvalue())
        request.return_value["data"]["app_id"] = "foreign-app"
        with self.assertRaises(CommandError):
            call_command("backfill_meta_callback_subjects", username=self.user.username, apply=True, stdout=output)
