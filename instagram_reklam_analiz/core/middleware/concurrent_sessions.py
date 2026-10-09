from datetime import timedelta
from importlib import import_module

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, logout
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone

from core.models import UserProfile


def claim_login_session(request, user):
    """A completed sign-in replaces the previous session for a normal member."""
    if (
        not request
        or request.session.get(SESSION_KEY) != str(user.pk)
        or user.is_staff
        or user.is_superuser
        or user.get_username().strip().casefold() == "demo"
    ):
        return

    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key

    with transaction.atomic():
        profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
        if profile.allow_concurrent_sessions:
            return
        previous_key = profile.active_session_key
        profile.active_session_key = session_key
        profile.active_session_last_seen = timezone.now()
        profile.save(update_fields=["active_session_key", "active_session_last_seen", "updated_at"])
        if previous_key and previous_key != session_key:
            # Use the configured backend so cached sessions are invalidated too.
            session_store = import_module(settings.SESSION_ENGINE).SessionStore
            session_store(session_key=previous_key).delete()


class ConcurrentSessionMiddleware:
    """Keep only the session selected by the most recent completed sign-in."""

    HEARTBEAT_AFTER = timedelta(minutes=1)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/payment/pos/callback/"):
            return self.get_response(request)
        user = getattr(request, "user", None)
        if (
            not user
            or not user.is_authenticated
            or user.is_staff
            or user.is_superuser
            or user.get_username().strip().casefold() == "demo"
        ):
            return self.get_response(request)

        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        now = timezone.now()

        with transaction.atomic():
            profile, _ = UserProfile.objects.select_for_update().get_or_create(user=user)
            if profile.allow_concurrent_sessions:
                return self.get_response(request)

            if profile.active_session_key and profile.active_session_key != session_key:
                logout(request)
                messages.error(
                    request,
                    "Bu hesapla yeni bir giriş yapıldığı için bu oturum kapatıldı. Yeniden giriş yapabilirsiniz.",
                )
                return redirect("account_login")

            should_refresh = (
                profile.active_session_key != session_key
                or not profile.active_session_last_seen
                or profile.active_session_last_seen < now - self.HEARTBEAT_AFTER
            )
            if should_refresh:
                profile.active_session_key = session_key
                profile.active_session_last_seen = now
                profile.save(update_fields=["active_session_key", "active_session_last_seen", "updated_at"])

        return self.get_response(request)
