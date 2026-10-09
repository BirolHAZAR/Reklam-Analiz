from datetime import timedelta
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone

from allauth.account.models import EmailAddress

from core.middleware.concurrent_sessions import ConcurrentSessionMiddleware
from core.models import UserProfile


class ConcurrentSessionMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ConcurrentSessionMiddleware(lambda request: HttpResponse("ok"))

    def _request(self, user):
        request = self.factory.get("/dashboard/")
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.create()
        request.user = user
        request._messages = FallbackStorage(request)
        return request

    def test_second_recent_session_is_rejected_by_default(self):
        user = get_user_model().objects.create_user("normal-user", password="secret123")

        first_response = self.middleware(self._request(user))
        second_response = self.middleware(self._request(user))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 302)
        self.assertIn("/accounts/login/", second_response.url)

    def test_admin_permission_allows_multiple_sessions(self):
        user = get_user_model().objects.create_user("allowed-user", password="secret123")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.allow_concurrent_sessions = True
        profile.save(update_fields=["allow_concurrent_sessions"])

        self.assertEqual(self.middleware(self._request(user)).status_code, 200)
        self.assertEqual(self.middleware(self._request(user)).status_code, 200)

    def test_demo_user_is_always_exempt(self):
        user = get_user_model().objects.create_user("DeMo", password="secret123")

        self.assertEqual(self.middleware(self._request(user)).status_code, 200)
        self.assertEqual(self.middleware(self._request(user)).status_code, 200)

    def test_old_authenticated_request_cannot_reclaim_idle_new_session(self):
        user = get_user_model().objects.create_user("idle-session-user", password="secret123")
        current = self._request(user)
        self.middleware(current)
        UserProfile.objects.filter(user=user).update(
            active_session_last_seen=timezone.now() - timedelta(hours=1),
        )
        response = self.middleware(self._request(user))
        self.assertEqual(response.status_code, 302)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.active_session_key, current.session.session_key)


class CompletedLoginSessionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "session-member", email="member@example.com", password="secret123",
        )
        self.first = Client()
        self.second = Client()

    def store(self, session_key):
        return import_module(settings.SESSION_ENGINE).SessionStore(session_key=session_key)

    def assert_login_takeover(self):
        self.assertTrue(self.first.login(username=self.user.username, password="secret123"))
        old_key = self.first.session.session_key
        self.assertEqual(self.store(old_key).get("_auth_user_id"), str(self.user.pk))

        self.assertTrue(self.second.login(username=self.user.username, password="secret123"))
        new_key = self.second.session.session_key
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, new_key)
        self.assertNotEqual(old_key, new_key)
        self.assertIsNone(self.store(old_key).get("_auth_user_id"))
        self.assertEqual(self.store(new_key).get("_auth_user_id"), str(self.user.pk))
        return old_key, new_key

    def test_new_completed_login_closes_previous_session(self):
        self.assert_login_takeover()

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.cached_db")
    def test_takeover_invalidates_cached_session_too(self):
        self.assert_login_takeover()

    def test_failed_login_keeps_existing_session(self):
        self.first.login(username=self.user.username, password="secret123")
        old_key = self.first.session.session_key
        self.assertFalse(self.second.login(username=self.user.username, password="wrong"))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, old_key)
        self.assertEqual(self.store(old_key).get("_auth_user_id"), str(self.user.pk))

    def test_missing_previous_session_does_not_block_login(self):
        UserProfile.objects.filter(user=self.user).update(
            active_session_key="a" * 32, active_session_last_seen=timezone.now(),
        )
        self.assertTrue(self.second.login(username=self.user.username, password="secret123"))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, self.second.session.session_key)

    def test_late_logout_of_old_session_keeps_new_session_registered(self):
        old_key, new_key = self.assert_login_takeover()
        request = RequestFactory().get("/accounts/logout/")
        request.session = self.store(old_key)
        user_logged_out.send(sender=type(self.user), request=request, user=self.user)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, new_key)

    def test_exempt_accounts_keep_previous_sessions(self):
        for exemption in ("is_staff", "is_superuser", "allow_concurrent_sessions", "demo"):
            with self.subTest(exemption=exemption):
                username = "demo" if exemption == "demo" else "exempt-" + exemption
                user = get_user_model().objects.create_user(username, password="secret123")
                if exemption in {"is_staff", "is_superuser"}:
                    setattr(user, exemption, True)
                    user.save(update_fields=[exemption])
                elif exemption == "allow_concurrent_sessions":
                    UserProfile.objects.filter(user=user).update(allow_concurrent_sessions=True)
                first, second = Client(), Client()
                first.login(username=username, password="secret123")
                old_key = first.session.session_key
                second.login(username=username, password="secret123")
                self.assertEqual(self.store(old_key).get("_auth_user_id"), str(user.pk))

    @override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory", ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=False)
    def test_verified_allauth_login_takes_over_session(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.first.login(username=self.user.username, password="secret123")
        old_key = self.first.session.session_key
        response = self.second.post("/accounts/login/", {"login": self.user.username, "password": "secret123"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("confirm-email", response.url)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, self.second.session.session_key)
        self.assertIsNone(self.store(old_key).get("_auth_user_id"))

    @override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory", ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=False)
    def test_pending_email_verification_does_not_close_existing_session(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=False, primary=True)
        self.first.login(username=self.user.username, password="secret123")
        old_key = self.first.session.session_key
        response = self.second.post("/accounts/login/", {"login": self.user.username, "password": "secret123"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("confirm-email", response.url)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.active_session_key, old_key)
        self.assertEqual(self.store(old_key).get("_auth_user_id"), str(self.user.pk))
