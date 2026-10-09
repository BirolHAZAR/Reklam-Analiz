from datetime import timedelta
import secrets
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.models import AgencyClient, IntegrationApplication, Platform, PlatformAccount, PlatformConnection
from core.services import ads_integrations as api
from core.services.agency_scope import get_agency_scope, platform_accounts_for_request


def _client(request, client_id):
    if not client_id:
        if get_agency_scope(request).is_agency:
            raise api.IntegrationError("Önce hesabın bağlanacağı ajans müşterisini seçin.")
        return None
    if not str(client_id).isdigit():
        raise api.IntegrationError("Geçerli bir ajans müşterisi seçin.")
    client = get_object_or_404(AgencyClient, pk=client_id, is_active=True, organization__is_active=True)
    from core.views.agency import _user_has_permission
    if not _user_has_permission(client.organization, request.user, "manage_accounts"):
        raise PermissionDenied
    return client


@login_required
@require_GET
def integrations(request):
    get_agency_scope(request)
    return redirect("platform_connections")


def account_connection_context(request):
    scope = get_agency_scope(request)
    providers = []
    for code, name in {**api.CONNECTION_PROVIDERS, "instagram": "Instagram"}.items():
        setup_error = ""
        try:
            api.configuration(code)
            ready = True
        except api.IntegrationError as exc:
            ready = False
            setup_error = str(exc)
        settings_url = ""
        if request.user.is_superuser:
            application = IntegrationApplication.objects.filter(provider=code).only("pk").first()
            settings_url = (
                reverse("admin:core_integrationapplication_change", args=[application.pk])
                if application else reverse("admin:core_integrationapplication_add") + f"?provider={code}"
            )
        providers.append({"code": code, "name": name, "ready": ready, "setup_error": setup_error, "settings_url": settings_url})
    accounts = list(platform_accounts_for_request(request).filter(platform__code__in=api.PROVIDERS).select_related("platform", "connection", "agency_client"))
    for account in accounts:
        connection = account.connection
        account.ads_authorized = bool(
            connection and (connection.extra_data or {}).get("source") == "ads_oauth"
            and account.is_active and connection.is_active and connection.status == "active"
            and (not connection.is_token_expired or (account.platform.code == "google_ads" and connection.refresh_token))
        )
    return {
        "connection_is_agency": scope.is_agency,
        "providers": [p for p in providers if p["code"] != "instagram"],
        "instagram_provider": next(p for p in providers if p["code"] == "instagram"),
        "clients": scope.clients, "selected_client": scope.selected_client,
        "accounts": accounts,
    }


@login_required
@require_POST
@never_cache
def connect(request, provider):
    if provider not in api.CONNECTION_PROVIDERS:
        raise Http404
    try:
        client = _client(request, request.POST.get("agency_client"))
        state = secrets.token_urlsafe(32)
        url = api.authorization_url(provider, state)
    except api.IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect("platform_connections")
    request.session[f"ads_oauth:{provider}"] = {
        "state": state, "user": request.user.pk, "created": time.time(), "client": client.pk if client else None,
    }
    return redirect(url)


@login_required
@require_GET
@never_cache
def callback(request, provider):
    if provider not in api.CONNECTION_PROVIDERS:
        raise Http404
    flow = request.session.pop(f"ads_oauth:{provider}", None)
    if not flow or flow.get("user") != request.user.pk or time.time() - flow["created"] > 600 or not secrets.compare_digest(flow["state"], request.GET.get("state", "")):
        messages.error(request, "Bağlantı isteği geçersiz veya süresi dolmuş. Yeniden başlatın.")
        return redirect("platform_connections")
    if request.GET.get("error") or not request.GET.get("code"):
        messages.warning(request, "Platform izni verilmedi; hesap bağlanmadı.")
        return redirect("platform_connections")
    try:
        client = _client(request, flow.get("client"))
        token = api.exchange_code(provider, request.GET["code"])
        choices = api.discover_accounts(provider, token["access_token"])
        if not choices:
            raise api.IntegrationError("Erişilebilir YouTube kanalı bulunamadı. Google hesabınızın yetkisini kontrol edin." if provider in api.GOOGLE_READ_PROVIDERS else "Erişilebilir aktif reklam hesabı bulunamadı. Platformdaki reklam hesabı yetkinizi kontrol edin.")
        platform, _ = Platform.objects.get_or_create(code=provider, defaults={"name": api.CONNECTION_PROVIDERS[provider], "is_active": True})
        connection = PlatformConnection.objects.create(
            user=request.user, platform=platform, name=api.CONNECTION_PROVIDERS[provider],
            access_token=token["access_token"], refresh_token=token.get("refresh_token", ""),
            token_expiry=None if provider == "facebook" and token.get("expires_in") is None else timezone.now() + timedelta(seconds=int(token.get("expires_in", 3600))),
            scopes=token.get("scope", "").split(), is_active=False, status="disconnected",
            extra_data={"source": "google_read_oauth" if provider in api.GOOGLE_READ_PROVIDERS else "ads_oauth", "pending": True, "choices": choices,
                        "agency_client": client.pk if client else None},
        )
        request.session[f"ads_pending:{provider}"] = connection.pk
        return redirect("integration_select", provider=provider)
    except api.IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect("platform_connections")


@login_required
@require_http_methods(["GET", "POST"])
@never_cache
def select_accounts(request, provider):
    if provider not in api.CONNECTION_PROVIDERS:
        raise Http404
    connection = get_object_or_404(PlatformConnection, pk=request.session.get(f"ads_pending:{provider}"), user=request.user, platform__code=provider)
    if not connection.extra_data.get("pending") or connection.created_at < timezone.now() - timedelta(minutes=15):
        messages.error(request, "Hesap seçiminin süresi doldu. Bağlantıyı yeniden başlatın.")
        return redirect("platform_connections")
    choices = [dict(row) for row in connection.extra_data.get("choices", [])]
    existing_ids = set(platform_accounts_for_request(request).filter(
        platform=connection.platform,
    ).values_list("account_id", flat=True))
    selected_ids = set(request.POST.getlist("accounts")) if request.method == "POST" else set()
    for choice in choices:
        choice["already_connected"] = str(choice["id"]) in existing_ids
        choice["selected"] = str(choice["id"]) in selected_ids
    connected_accounts = platform_accounts_for_request(request).filter(platform=connection.platform)
    error = ""
    if request.method == "POST":
        try:
            client = _client(request, connection.extra_data.get("agency_client"))
            selected = set(request.POST.getlist("accounts"))
            allowed = {str(row["id"]): row for row in connection.extra_data.get("choices", [])}
            if not selected or not selected <= allowed.keys():
                raise api.IntegrationError("Listeden en az bir hesap seçin.")
            from core.services.plan_limits import ensure_platform_account_capacity
            with transaction.atomic():
                # Serialize selections and enforce the existing subscription limit.
                from django.contrib.auth import get_user_model
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                if client:
                    from core.models import Organization
                    Organization.objects.select_for_update().get(pk=client.organization_id)
                    if PlatformAccount.objects.filter(agency_client__organization=client.organization, platform=connection.platform, account_id__in=selected).exclude(user=request.user).exists():
                        raise api.IntegrationError("Bu reklam hesabı ajansınızda zaten kayıtlı. Mevcut müşteri hesabını kullanın.")
                connection = PlatformConnection.objects.select_for_update().get(pk=connection.pk)
                if not connection.extra_data.get("pending"):
                    raise api.IntegrationError("Bu hesap seçimi zaten tamamlandı.")
                ensure_platform_account_capacity(request.user, [(provider, cid) for cid in selected], organization=client.organization if client else None)
                connection.is_active, connection.status = True, "active"
                source = "google_read_oauth" if provider in api.GOOGLE_READ_PROVIDERS else "ads_oauth"
                connection.extra_data = {"source": source, "agency_client": client.pk if client else None}
                connection.save()
                replaced_connections = set()
                for cid in sorted(selected):
                    old = PlatformAccount.objects.filter(user=request.user, platform=connection.platform, account_id=cid).first()
                    if old and old.agency_client_id != (client.pk if client else None):
                        raise api.IntegrationError("Seçilen hesap başka bir müşteriyle eşleştirilmiş. Önce mevcut eşleştirmeyi düzenleyin.")
                    if old and old.connection_id:
                        replaced_connections.add(old.connection_id)
                    account, _ = PlatformAccount.objects.update_or_create(user=request.user, platform=connection.platform, account_id=cid, defaults={
                        "connection": connection, "agency_client": client, "account_name": allowed[cid]["name"],
                        "access_token": connection.access_token, "refresh_token": connection.refresh_token,
                        "token_expiry": connection.token_expiry, "is_active": True,
                        "extra_data": {**(old.extra_data if old else {}), **allowed[cid], "source": source},
                    })
                PlatformConnection.objects.filter(pk__in=replaced_connections, user=request.user, accounts__isnull=True).update(is_active=False, status="disconnected")
            request.session.pop(f"ads_pending:{provider}", None)
            messages.success(request, f"{len(selected)} hesap bağlandı." if provider in api.GOOGLE_READ_PROVIDERS else f"{len(selected)} reklam hesabı bağlandı. Kampanyaları görüntüleyebilirsiniz.")
            return redirect("platform_connections")
        except (api.IntegrationError, ValueError) as exc:
            error = str(exc)
    return render(request, "platforms/integration_select.html", {
        "provider_name": api.CONNECTION_PROVIDERS.get(provider), "choices": choices,
        "connected_accounts": connected_accounts, "error": error,
    })


@login_required
@require_GET
@never_cache
def account_campaigns(request, account_id, campaign_id=None):
    account = get_object_or_404(platform_accounts_for_request(request).select_related("platform", "connection"), pk=account_id, is_active=True, platform__code__in=api.PROVIDERS)
    context = {"account": account, "campaigns": [], "metrics": [], "campaign": None}
    try:
        rows = api.campaigns(account)
        aliases = (account.extra_data or {}).get("campaign_names", {})
        for row in rows:
            row["name"] = aliases.get(str(row["id"])) or row["name"]
        context["campaigns"] = rows
        if campaign_id:
            campaign = next((r for r in rows if str(r["id"]) == str(campaign_id)), None)
            if not campaign:
                from django.http import Http404
                raise Http404
            end = api.account_today(account)
            start = end - timedelta(days=29)
            context.update(campaign=campaign, start=start, end=end, metrics=api.campaign_performance(account, campaign_id, start, end))
    except api.IntegrationError as exc:
        context["error"] = str(exc)
    return render(request, "platforms/integration_campaigns.html", context)
