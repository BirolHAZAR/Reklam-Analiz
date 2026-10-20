"""Subscriber-owned TikTok reporting connection, separate from social sign-in."""
from datetime import timedelta
import secrets
import time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.models import Organization, Platform, PlatformAccount, PlatformConnection
from core.services import tiktok_oauth as api
from core.services.tiktok_oauth import access_token
from core.services.ads_integrations import IntegrationError, configuration
from core.services.agency_scope import platform_accounts_for_request
from core.services.plan_limits import ensure_platform_account_capacity
from core.views.ads_integrations import _client

SESSION_KEY = "tiktok_reporting_oauth"


@login_required
@require_POST
@never_cache
def connect(request):
    try:
        client = _client(request, request.POST.get("agency_client"))
        state = secrets.token_urlsafe(32)
        url = api.authorization_url(state)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("hesap_ekle")
    request.session[SESSION_KEY] = {
        "state": state, "user": request.user.pk, "created": time.time(),
        "client": client.pk if client else None,
    }
    return redirect(url)


@transaction.atomic
def save_account(user, client, token, profile):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if client:
        Organization.objects.select_for_update().get(pk=client.organization_id)
        if PlatformAccount.objects.filter(platform__code="tiktok", account_id=token["open_id"],
                agency_client__organization=client.organization).exclude(user=user).exists():
            raise IntegrationError("Bu TikTok hesabı ajansınızda zaten kayıtlı.")
    platform, _ = Platform.objects.get_or_create(code="tiktok", defaults={"name": "TikTok", "is_active": True})
    old = PlatformAccount.objects.filter(user=user, platform=platform, account_id=token["open_id"]).first()
    if old and old.agency_client_id != (client.pk if client else None):
        raise IntegrationError("Bu hesap başka bir müşteriyle eşleştirilmiş.")
    ensure_platform_account_capacity(user, [("tiktok", token["open_id"])], organization=client.organization if client else None)
    key, _, _ = configuration("tiktok")
    expiry = timezone.now() + timedelta(seconds=token["expires_in"])
    metadata = {"source": "tiktok_oauth", "client_key": key, "profile": profile,
                "refresh_expiry": (timezone.now() + timedelta(seconds=token["refresh_expires_in"])).isoformat()}
    name = str(profile.get("username") or profile.get("display_name") or "TikTok")[:200]
    connection = PlatformConnection.objects.create(user=user, platform=platform, name=name,
        access_token=token["access_token"], refresh_token=token["refresh_token"], token_expiry=expiry,
        scopes=token["scope"], is_active=True, status="active", extra_data=metadata)
    account, _ = PlatformAccount.objects.update_or_create(user=user, platform=platform, account_id=token["open_id"],
        defaults={"account_name": name, "agency_client": client, "connection": connection,
                  "access_token": token["access_token"], "refresh_token": token["refresh_token"],
                  "token_expiry": expiry, "is_active": True,
                  "extra_data": {**((old.extra_data or {}) if old else {}), **metadata}})
    if old and old.connection_id:
        PlatformConnection.objects.filter(pk=old.connection_id, accounts__isnull=True).update(is_active=False, status="disconnected")
    return account


@login_required
@require_GET
@never_cache
def callback(request):
    flow = request.session.pop(SESSION_KEY, None)
    if (not isinstance(flow, dict) or flow.get("user") != request.user.pk
            or not 0 <= time.time() - flow.get("created", 0) <= 600
            or not secrets.compare_digest(str(flow.get("state", "")).encode(), request.GET.get("state", "").encode())):
        messages.error(request, "TikTok bağlantı isteği geçersiz veya süresi dolmuş. Yeniden bağlayın.")
        return redirect("hesap_ekle")
    if request.GET.get("error") or not request.GET.get("code"):
        messages.info(request, "TikTok izni verilmedi.")
        return redirect("hesap_ekle")
    try:
        client = _client(request, flow.get("client"))
        token, user = api.exchange_code(request.GET["code"])
        account = save_account(request.user, client, token, user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("hesap_ekle")
    messages.success(request, "TikTok hesabı bağlandı.")
    return redirect("tiktok_report", account_id=account.pk)


@login_required
@require_GET
@never_cache
def report(request, account_id):
    account = get_object_or_404(platform_accounts_for_request(request), pk=account_id, platform__code="tiktok",
                              connection__extra_data__source="tiktok_oauth")
    cursor = request.GET.get("cursor")
    if cursor is not None and (not cursor.isascii() or not cursor.isdigit() or len(cursor) > 18):
        return HttpResponseBadRequest("Geçersiz video sayfası.")
    profile, videos, next_cursor, error = {}, [], None, ""
    try:
        if not account.connection_id:
            raise IntegrationError("TikTok hesabını izin ekranıyla yeniden bağlayın.")
        token = access_token(account)
        profile = api.profile(token, account.account_id)
        videos, next_cursor = api.videos(token, int(cursor) if cursor is not None else None)
    except IntegrationError as exc:
        error = str(exc)
    return render(request, "platforms/tiktok_report.html", {
        "account": account, "profile": profile, "videos": videos,
        "next_cursor": next_cursor, "error": error,
    })
