from datetime import timedelta
import secrets
import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
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
    for code, name in {**api.CONNECTION_PROVIDERS, "instagram": "Instagram", "tiktok": "TikTok", "x": "X"}.items():
        setup_error = ""
        try:
            api.configuration(code)
            if code == "x":
                from core.services.x_oauth import require_read_access
                require_read_access()
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
    accounts = list(platform_accounts_for_request(request).filter(platform__code__in=api.AD_ACCOUNT_PLATFORM_CODES)
        .filter(~Q(platform__code="tiktok") | Q(connection__extra_data__source="tiktok_ads_oauth"))
        .filter(~Q(platform__code="x") | Q(connection__extra_data__source="x_ads_oauth"))
        .select_related("platform", "connection", "agency_client"))
    for account in accounts:
        connection = account.connection
        account.ads_authorized = bool(
            connection and (connection.extra_data or {}).get("source") in {"ads_oauth", "tiktok_ads_oauth", "x_ads_oauth"}
            and account.is_active and connection.is_active and connection.status == "active"
            and (not connection.is_token_expired or (account.platform.code == "google_ads" and connection.refresh_token))
        )
    return {
        "connection_is_agency": scope.is_agency,
        "providers": [p for p in providers if p["code"] not in {"instagram", "tiktok", "x"}],
        "x_provider": next(p for p in providers if p["code"] == "x"),
        "instagram_provider": next(p for p in providers if p["code"] == "instagram"),
        "tiktok_provider": next(p for p in providers if p["code"] == "tiktok"),
        "clients": scope.clients, "selected_client": scope.selected_client,
        "accounts": accounts,
    }


@login_required
@require_POST
@never_cache
def connect(request, provider):
    if provider == "x_ads":
        from core.views.x_ads_oauth import connect as x_connect
        return x_connect(request)
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
    code = request.GET.get("auth_code") if provider == "tiktok_ads" else request.GET.get("code")
    if request.GET.get("error") or not code:
        messages.warning(request, "Platform izni verilmedi; hesap bağlanmadı.")
        return redirect("platform_connections")
    try:
        client = _client(request, flow.get("client"))
        token = api.exchange_code(provider, code)
        choices = api.discover_accounts(provider, token["access_token"])
        if not choices:
            raise api.IntegrationError("Erişilebilir YouTube kanalı bulunamadı. Google hesabınızın yetkisini kontrol edin." if provider in api.GOOGLE_READ_PROVIDERS else "Erişilebilir aktif reklam hesabı bulunamadı. Platformdaki reklam hesabı yetkinizi kontrol edin.")
        platform, _ = Platform.objects.get_or_create(code=api.provider_platform_code(provider), defaults={"name": api.CONNECTION_PROVIDERS[provider], "is_active": True})
        connection = PlatformConnection.objects.create(
            user=request.user, platform=platform, name=api.CONNECTION_PROVIDERS[provider],
            access_token=token["access_token"], refresh_token=token.get("refresh_token", ""),
            token_expiry=None if provider in {"facebook", "tiktok_ads"} and token.get("expires_in") is None else timezone.now() + timedelta(seconds=int(token.get("expires_in", 3600))),
            scopes=token.get("scope", "").split(), is_active=False, status="disconnected",
            extra_data={"source": api.provider_source(provider), "pending": True, "choices": choices,
                        **{key: token[key] for key in ("meta_user_id", "meta_app_id") if provider == "facebook" and key in token},
                        **({"linkedin_client_id": token["linkedin_client_id"]} if provider == "linkedin" else {}),
                        **({"tiktok_ads_app_id": token["tiktok_ads_app_id"]} if provider == "tiktok_ads" else {}),
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
    connection = get_object_or_404(PlatformConnection, pk=request.session.get(f"ads_pending:{provider}"), user=request.user, platform__code=api.provider_platform_code(provider))
    if not connection.extra_data.get("pending") or connection.extra_data.get("source") != api.provider_source(provider) or connection.created_at < timezone.now() - timedelta(minutes=15):
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
                ensure_platform_account_capacity(request.user, [(api.provider_platform_code(provider), cid) for cid in selected], organization=client.organization if client else None)
                connection.is_active, connection.status = True, "active"
                source = api.provider_source(provider)
                connection.extra_data = {"source": source, "agency_client": client.pk if client else None,
                    **({"x_ads_consumer_key":connection.extra_data.get("x_ads_consumer_key"), "authorized_account_ids":sorted(selected)} if provider == "x_ads" else {}),
                    **{key: connection.extra_data[key] for key in ("meta_user_id", "meta_app_id")
                       if provider == "facebook" and key in connection.extra_data},
                    **({"linkedin_client_id": connection.extra_data.get("linkedin_client_id")} if provider == "linkedin" else {}),
                    **({"tiktok_ads_app_id": connection.extra_data.get("tiktok_ads_app_id")} if provider == "tiktok_ads" else {})}
                connection.save()
                replaced_connections = set()
                for cid in sorted(selected):
                    old = PlatformAccount.objects.filter(user=request.user, platform=connection.platform, account_id=cid).first()
                    if provider == 'x_ads' and old and (old.extra_data or {}).get('source') == 'x_oauth':
                        raise api.IntegrationError('Bu kimlik organik X hesabına ait; reklam bağlantısıyla değiştirilemez.')
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
def account_campaigns(request, account_id=None, campaign_id=None):
    from urllib.parse import urlencode
    from core.services.campaign_reporting import decorate_campaign, summarize_metrics
    accounts = platform_accounts_for_request(request).select_related("platform", "connection").filter(
        is_active=True, platform__code__in=api.AD_ACCOUNT_PLATFORM_CODES,
    ).filter(~Q(platform__code="tiktok") | Q(connection__extra_data__source="tiktok_ads_oauth")).filter(~Q(platform__code="x") | Q(connection__extra_data__source="x_ads_oauth")).order_by("platform__name", "account_name", "pk")
    selected_id = account_id if account_id is not None else request.GET.get("account")
    account = get_object_or_404(accounts, pk=selected_id) if str(selected_id or "").isdigit() else None
    if selected_id and account is None:
        raise Http404
    end = api.account_today(account) if account else timezone.localdate()
    start = end - timedelta(days=29)
    scope = get_agency_scope(request)
    selected_status = request.GET.get("status", "")
    if selected_status not in {"", "active", "inactive", "other"}:
        selected_status = ""
    search = request.GET.get("q", "").strip()[:100]
    context = {"account": account, "accounts": accounts, "campaigns": [], "metrics": [], "campaign": None,
               "agency_scope": scope, "selected_status": selected_status, "search": search,
               "currency": (account.extra_data or {}).get("currency") if account else "",
               "start": start, "end": end, "summary": None, "total_campaigns": 0,
               "active_campaigns": 0, "inactive_campaigns": 0}
    if not account:
        return render(request, "platforms/integration_campaigns.html", context)
    if request.GET.get("start") or request.GET.get("end"):
        try:
            start = parse_date(request.GET.get("start", ""))
            end = parse_date(request.GET.get("end", ""))
        except ValueError:
            start = end = None
        if not start or not end or start > end or (end - start).days > 365:
            context["error"] = "Başlangıç ve bitiş tarihini kontrol edin. En fazla 366 günlük bir dönem seçebilirsiniz."
            return render(request, "platforms/integration_campaigns.html", context)
    params = {"start": start.isoformat(), "end": end.isoformat()}
    if scope.selected_client:
        params["agency_client"] = scope.selected_client.pk
    context.update(start=start, end=end, report_query=urlencode(params))
    try:
        rows = [decorate_campaign(row, today=api.account_today(account)) for row in api.campaigns(account)]
        aliases = (account.extra_data or {}).get("campaign_names", {})
        for row in rows:
            row["name"] = aliases.get(str(row["id"])) or row["name"]
        context.update(total_campaigns=len(rows), active_campaigns=sum(row["status_group"] == "active" for row in rows),
                       inactive_campaigns=sum(row["status_group"] == "inactive" for row in rows))
        if campaign_id:
            campaign = next((r for r in rows if str(r["id"]) == str(campaign_id)), None)
            if not campaign:
                from django.http import Http404
                raise Http404
            metrics = api.campaign_performance(account, campaign_id, start, end)
            context.update(campaign=campaign, metrics=[{**row, **summarize_metrics([row])} for row in metrics],
                           summary=summarize_metrics(metrics))
        else:
            visible = [row for row in rows if (not selected_status or row["status_group"] == selected_status)
                       and (not search or search.casefold() in row["name"].casefold() or search in str(row["id"]))]
            context["campaigns"] = visible
            try:
                summaries = api.campaign_summaries(account, start, end, campaign_ids=[row["id"] for row in visible]) if visible else {}
                for row in visible:
                    row["performance"] = summarize_metrics([summaries[str(row["id"])]]) if str(row["id"]) in summaries else None
                context["summary"] = summarize_metrics([summaries[str(row["id"])] for row in visible if str(row["id"]) in summaries])
                if account.platform.code == 'x':
                    context['campaigns'] = [row for row in visible if str(row['id']) in summaries]
            except api.IntegrationError as exc:
                context["metrics_error"] = str(exc)
    except api.IntegrationError as exc:
        context["error"] = str(exc)
    return render(request, "platforms/integration_campaigns.html", context)
