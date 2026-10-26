import time
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import AgencyClient, IntegrationApplication, Organization, PlatformAccount, PlatformConnection
from core.services import tiktok_oauth as api
from core.services.ads_integrations import IntegrationError
from core.views.tiktok_oauth import SESSION_KEY, access_token, save_account


@override_settings(TIKTOK_CLIENT_KEY="test-key", TIKTOK_CLIENT_SECRET="test-secret",
    TIKTOK_REDIRECT_URI="https://www.reklamanaliz.net/connect/tiktok/callback/")
class TikTokOAuthTests(TestCase):
    def setUp(self):
        capacity = patch("core.views.tiktok_oauth.ensure_platform_account_capacity")
        self.capacity = capacity.start()
        self.addCleanup(capacity.stop)
        self.user = get_user_model().objects.create_user(username="tik-owner", is_superuser=True, is_staff=True)
        self.client.force_login(self.user)
        self.token = {"access_token": "private-access", "refresh_token": "private-refresh", "open_id": "subject",
                      "expires_in": 86400, "refresh_expires_in": 31536000, "scope": list(api.SCOPES)}
        self.profile = {"open_id": "subject", "username": "example", "display_name": "Example", "follower_count": 0}

    def flow(self, **changes):
        session = self.client.session
        session[SESSION_KEY] = {"state": "nonce", "user": self.user.pk, "created": time.time(), "client": None, **changes}
        session.save()

    def test_connect_post_only_and_no_secret_in_redirect(self):
        self.assertEqual(self.client.get(reverse("tiktok_connect")).status_code, 405)
        result = self.client.post(reverse("tiktok_connect"))
        parsed = urlsplit(result.url)
        self.assertEqual(parsed.hostname, "www.tiktok.com")
        params = parse_qs(parsed.query)
        self.assertEqual(params["scope"], [",".join(api.SCOPES)])
        self.assertEqual(params["disable_auto_auth"], ["1"])
        self.assertEqual(params["state"], [self.client.session[SESSION_KEY]["state"]])
        self.assertNotIn("test-secret", result.url)

    @patch("core.views.tiktok_oauth.api.exchange_code")
    def test_bad_expired_cross_user_cancelled_and_replayed_requests(self, exchange):
        url = reverse("tiktok_oauth_callback")
        for changes, params in [({}, {"state": "wrong"}), ({"created": time.time()-601}, {}),
                                ({"user": self.user.pk+1}, {}), ({}, {"error": "denied"})]:
            self.flow(**changes)
            self.client.get(url, {"state": "nonce", "code": "one-use", **params})
        self.client.get(url, {"state": "nonce", "code": "one-use"})
        exchange.assert_not_called()
        self.assertFalse(PlatformConnection.objects.exists())

    @patch("core.views.tiktok_oauth.api.exchange_code")
    def test_callback_saves_encrypted_credentials_and_replay_is_rejected(self, exchange):
        exchange.return_value = self.token, self.profile
        self.flow()
        url = reverse("tiktok_oauth_callback")
        result = self.client.get(url, {"state": "nonce", "code": "one-use"})
        account = PlatformAccount.objects.get()
        self.assertEqual(result.url, reverse("tiktok_report", args=[account.pk]))
        self.assertEqual(account.connection.refresh_token, "private-refresh")
        with connection.cursor() as cursor:
            cursor.execute("SELECT access_token, refresh_token FROM core_platformconnection WHERE id=%s", [account.connection_id])
            self.assertTrue(all(value.startswith("enc:v1:") for value in cursor.fetchone()))
        self.client.get(url, {"state": "nonce", "code": "one-use"})
        self.assertEqual(exchange.call_count, 1)

    @patch("core.services.tiktok_oauth.requests.request")
    def test_tiktok_success_error_envelope_and_safe_errors(self, request):
        request.return_value = Mock(ok=True)
        request.return_value.json.return_value = {"data": {"user": self.profile}, "error": {"code": "ok"}}
        self.assertEqual(api.profile("private-access", "subject")["follower_count"], 0)
        with self.assertRaises(IntegrationError):
            api.profile("private-access", "another-subject")
        request.return_value.json.return_value = {"error": {"code": "access_token_invalid", "message": "private-access"}}
        with self.assertRaises(IntegrationError) as failure:
            api.profile("private-access", "subject")
        self.assertNotIn("private-access", str(failure.exception))

    @patch("core.services.tiktok_oauth.request")
    def test_token_requires_all_read_scopes_and_refresh_token(self, request):
        payload = {**self.token, "scope": ",".join(api.SCOPES), "token_type": "Bearer"}
        request.return_value = payload
        self.assertEqual(api.token_request(grant_type="authorization_code", code="code")["scope"], list(api.SCOPES))
        for changes in ({"scope": "user.info.basic"}, {"refresh_token": ""}, {"expires_in": 0}, {"token_type": "unexpected"}):
            request.return_value = {**payload, **changes}
            with self.assertRaises(IntegrationError):
                api.token_request(grant_type="authorization_code", code="code")

    @patch("core.views.tiktok_oauth.api.token_request")
    def test_refresh_rotates_tokens_and_rejects_subject_change(self, refresh):
        account = save_account(self.user, None, self.token, self.profile)
        PlatformConnection.objects.filter(pk=account.connection_id).update(token_expiry=timezone.now()-timedelta(seconds=1))
        refresh.return_value = {**self.token, "access_token": "rotated", "refresh_token": "rotated-refresh", "open_id": "other"}
        with self.assertRaises(IntegrationError):
            access_token(account)
        refresh.return_value = {**self.token, "access_token": "rotated", "refresh_token": "rotated-refresh"}
        self.assertEqual(access_token(account), "rotated")
        account.refresh_from_db()
        self.assertEqual(account.refresh_token, "rotated-refresh")
        self.assertEqual(account.connection.refresh_token, "rotated-refresh")

    @patch("core.views.tiktok_oauth.api.videos")
    @patch("core.views.tiktok_oauth.api.profile")
    def test_report_is_scoped_and_never_contains_credentials(self, profile, videos):
        profile.return_value = self.profile
        videos.return_value = [{"id": "video", "title": "<script>alert(1)</script>", "view_count": 0}], 42
        account = save_account(self.user, None, self.token, self.profile)
        url = reverse("tiktok_report", args=[account.pk])
        result = self.client.get(url)
        self.assertContains(result, "?cursor=42")
        self.assertContains(result, "&lt;script&gt;")
        for secret in ("private-access", "private-refresh", "test-secret"):
            self.assertNotContains(result, secret)
        self.assertEqual(self.client.get(url, {"cursor": "-1"}).status_code, 400)
        self.client.force_login(get_user_model().objects.create_user(username="other", is_staff=True))
        self.assertEqual(self.client.get(url).status_code, 404)

    @patch("core.services.tiktok_oauth.request")
    def test_video_pagination_and_unknown_counts_are_preserved(self, request):
        request.return_value = {"data": {"videos": [{"id": "v", "view_count": 0}], "has_more": True, "cursor": 42}}
        rows, cursor = api.videos("token", 12)
        self.assertEqual(cursor, 42)
        self.assertEqual(rows[0]["view_count"], 0)
        self.assertIsNone(rows[0]["like_count"])
        self.assertEqual(request.call_args.kwargs["json"], {"max_count": 20, "cursor": 12})

    def test_admin_settings_validate_dedicated_callback_and_disable_access(self):
        app = IntegrationApplication(provider="tiktok", client_id="key", client_secret="secret",
            redirect_uri="https://www.reklamanaliz.net/connect/tiktok/callback/", enabled=True)
        app.full_clean()
        app.save()
        app.enabled = False
        app.save()
        with self.assertRaises(IntegrationError):
            api.authorization_url("state")

    @patch("core.views.tiktok_oauth.api.exchange_code")
    def test_capacity_failure_rolls_back_and_is_presented_safely(self, exchange):
        self.capacity.side_effect = ValueError("Paket hesabı limiti doldu.")
        exchange.return_value = self.token, self.profile
        self.flow()
        response = self.client.get(reverse("tiktok_oauth_callback"), {"state": "nonce", "code": "code"})
        self.assertEqual(response.url, reverse("hesap_ekle"))
        self.assertFalse(PlatformAccount.objects.exists())
        self.assertFalse(PlatformConnection.objects.exists())

    def test_reconnect_preserves_alias_and_cannot_move_to_another_client(self):
        account = save_account(self.user, None, self.token, self.profile)
        old = account.connection
        account.local_name = "My alias"
        account.save()
        account = save_account(self.user, None, self.token, self.profile)
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(account.local_name, "My alias")
        org = Organization.objects.create(owner=self.user, name="Agency")
        brand = AgencyClient.objects.create(organization=org, name="Brand")
        with self.assertRaises(IntegrationError):
            save_account(self.user, brand, self.token, self.profile)

    def test_organic_token_cannot_be_reused_after_subject_or_scope_change(self):
        account = save_account(self.user, None, self.token, self.profile)
        account.account_id = "changed-subject"
        with self.assertRaises(IntegrationError):
            access_token(account)
        account.account_id = self.token["open_id"]
        account.connection.scopes = ["user.info.basic"]
        account.connection.save()
        with self.assertRaises(IntegrationError):
            access_token(account)

    @patch("core.services.tiktok_oauth.profile")
    @patch("core.services.tiktok_oauth.token_request")
    def test_health_check_refreshes_before_generic_token_probe(self, refresh, profile):
        from core.services.platform_token_service import _validate_connection
        account = save_account(self.user, None, self.token, self.profile)
        PlatformConnection.objects.filter(pk=account.connection_id).update(token_expiry=timezone.now()-timedelta(seconds=1))
        refresh.return_value = {**self.token, "access_token": "new-access"}
        connection = account.connection
        self.assertTrue(_validate_connection(connection)["valid"])
        profile.assert_called_once_with("new-access", "subject")
