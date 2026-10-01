from datetime import timedelta
import secrets
import time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.models import Organization, Platform, PlatformAccount, PlatformConnection
from core.services import instagram_oauth as api
from core.services.ads_integrations import IntegrationError
from core.services.plan_limits import ensure_platform_account_capacity
from core.views.ads_integrations import _client

SESSION_KEY = "instagram_login_oauth"


@login_required
@require_POST
@never_cache
def connect(request):
    try:
        client = _client(request, request.POST.get("agency_client"))
        state = secrets.token_urlsafe(32)
        url = api.authorization_url(state)
    except IntegrationError as exc:
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
        if PlatformAccount.objects.filter(platform__code="instagram", account_id=profile["id"],
                agency_client__organization=client.organization).exclude(user=user).exists():
            raise IntegrationError("Bu Instagram hesabı ajansınızda zaten kayıtlı.")
    platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram", "is_active": True})
    old = PlatformAccount.objects.filter(user=user, platform=platform, account_id=profile["id"]).first()
    if old and old.agency_client_id != (client.pk if client else None):
        raise IntegrationError("Bu hesap başka bir müşteriyle eşleştirilmiş. Önce mevcut eşleştirmeyi düzenleyin.")
    ensure_platform_account_capacity(user, [("instagram", profile["id"])], organization=client.organization if client else None)
    metadata = {"source": "instagram_oauth", "auth_type": "instagram_login",
                "instagram_business_account_id": profile["id"], "username": profile["username"],
                "agency_client": client.pk if client else None}
    expiry = timezone.now() + timedelta(seconds=token["expires_in"])
    connection = PlatformConnection.objects.create(
        user=user, platform=platform, name="@" + profile["username"],
        access_token=token["access_token"], token_expiry=expiry,
        scopes=token["scope"], is_active=True, status="active", extra_data=metadata,
    )
    account, _ = PlatformAccount.objects.update_or_create(
        user=user, platform=platform, account_id=profile["id"], defaults={
            "account_name": "@" + profile["username"], "agency_client": client,
            "connection": connection, "access_token": token["access_token"],
            "refresh_token": "", "token_expiry": expiry, "is_active": True,
            "extra_data": {**((old.extra_data or {}) if old else {}), **metadata},
        },
    )
    if old and old.connection_id:
        PlatformConnection.objects.filter(pk=old.connection_id, user=user, accounts__isnull=True).update(is_active=False, status="disconnected")
    return account


@login_required
@require_GET
@never_cache
def callback(request):
    flow = request.session.pop(SESSION_KEY, None)
    if (not flow or flow.get("user") != request.user.pk
            or not 0 <= time.time() - flow.get("created", 0) <= 600
            or not secrets.compare_digest(flow.get("state", "").encode("utf-8"), request.GET.get("state", "").encode("utf-8"))):
        messages.error(request, "Bağlantı isteğinin süresi dolmuş veya istek geçersiz. Instagram'ı yeniden bağlayın.")
        return redirect("hesap_ekle")
    if request.GET.get("error") or not request.GET.get("code"):
        messages.info(request, "Instagram izni verilmedi. Hazır olduğunuzda yeniden bağlayabilirsiniz.")
        return redirect("hesap_ekle")
    try:
        client = _client(request, flow.get("client"))
        token, profile = api.exchange_code(request.GET["code"])
        account = save_account(request.user, client, token, profile)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("hesap_ekle")
    messages.success(request, f"{account.display_name} Instagram hesabı bağlandı.")
    return redirect("platform_connections")
