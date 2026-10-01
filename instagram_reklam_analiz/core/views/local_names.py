from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.db import transaction

from core.models import Ad, Campaign, PlatformAccount
from core.services.agency_scope import platform_accounts_for_request, scope_queryset
from core.services.cache_service import CacheService


@login_required
@require_http_methods(["GET", "POST"])
def rename(request, kind, object_id):
    models = {"account": PlatformAccount, "campaign": Campaign, "ad": Ad}
    destinations = {"account": "platform_connections", "campaign": "campaign_center", "ad": "health_center"}
    if kind not in models:
        raise Http404
    qs = models[kind].objects.all()
    qs = platform_accounts_for_request(request, qs) if kind == "account" else scope_queryset(request, qs)
    obj = get_object_or_404(qs, pk=object_id)
    account = obj if kind == "account" else obj.platform_account
    if account and account.agency_client_id:
        from core.views.agency import _user_has_permission
        if not _user_has_permission(account.agency_client.organization, request.user, "manage_accounts"):
            raise PermissionDenied
    elif obj.user_id != request.user.pk:
        raise PermissionDenied
    error = ""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if len(name) > obj._meta.get_field("local_name").max_length:
            error = "Ad çok uzun. Lütfen daha kısa bir ad girin."
        else:
            with transaction.atomic():
                obj.local_name = name
                obj.save(update_fields=["local_name"])
                if kind == "campaign" and account and obj.platform_campaign_id:
                    locked_account = PlatformAccount.objects.select_for_update().get(pk=account.pk)
                    data = dict(locked_account.extra_data or {})
                    aliases = dict(data.get("campaign_names", {}))
                    campaign_id = str(obj.platform_campaign_id)
                    if name:
                        aliases[campaign_id] = name
                    else:
                        aliases.pop(campaign_id, None)
                    data["campaign_names"] = aliases
                    locked_account.extra_data = data
                    locked_account.save(update_fields=["extra_data"])
            for user_id in {request.user.pk, obj.user_id}:
                CacheService.bump_version("health_center", user_id)
                CacheService.bump_version("campaign_center", user_id)
            messages.success(request, "Görünen ad güncellendi.")
            return redirect(destinations[kind])
    return render(request, "platforms/rename.html", {
        "object": obj, "error": error, "back_url": destinations[kind],
        "max_length": obj._meta.get_field("local_name").max_length,
    })


@login_required
@require_http_methods(["GET", "POST"])
def rename_remote_campaign(request, account_id, campaign_id):
    from types import SimpleNamespace
    from core.services import ads_integrations as api
    account = get_object_or_404(platform_accounts_for_request(request), pk=account_id)
    if account.agency_client_id:
        from core.views.agency import _user_has_permission
        if not _user_has_permission(account.agency_client.organization, request.user, "manage_accounts"):
            raise PermissionDenied
    elif account.user_id != request.user.pk:
        raise PermissionDenied
    try:
        campaign = next((row for row in api.campaigns(account) if str(row["id"]) == campaign_id), None)
    except api.IntegrationError as exc:
        messages.error(request, str(exc))
        return redirect("integration_campaigns", account_id=account.pk)
    if campaign is None:
        raise Http404
    current = (account.extra_data or {}).get("campaign_names", {}).get(campaign_id, "")
    error = ""
    if request.method == "POST":
        current = request.POST.get("name", "").strip()
        if len(current) > 255:
            error = "Ad en fazla 255 karakter olabilir."
        else:
            with transaction.atomic():
                account = PlatformAccount.objects.select_for_update().get(pk=account.pk)
                data = dict(account.extra_data or {})
                aliases = dict(data.get("campaign_names", {}))
                if current:
                    aliases[campaign_id] = current
                else:
                    aliases.pop(campaign_id, None)
                data["campaign_names"] = aliases
                account.extra_data = data
                account.save(update_fields=["extra_data"])
                Campaign.objects.filter(platform_account=account, platform_campaign_id=campaign_id).update(local_name=current)
            return redirect("integration_campaigns", account_id=account.pk)
    return render(request, "platforms/rename.html", {
        "object": SimpleNamespace(display_name=current or campaign["name"], local_name=current),
        "error": error, "back_url": "platform_connections", "max_length": 255,
    })
