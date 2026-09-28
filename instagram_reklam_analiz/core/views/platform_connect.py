# core/views/platform_connect.py
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.db import IntegrityError
from django.views.decorators.http import require_POST
import requests

from core.models import PlatformAccount, Platform
from core.services.notification_helper import NotificationHelper


# Legacy entry point now leads to the consent-based integrations screen.
@login_required
def facebook_login(request):
    return redirect("integrations")


from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import Platform, PlatformAccount, PlatformConnection


@login_required
def platform_connections(request):
    user = request.user

    platforms = Platform.objects.filter(is_active=True).order_by("name")
    platform_data = []
    total_account_count = 0
    total_active_account_count = 0
    total_connection_count = 0
    total_active_connection_count = 0

    for platform in platforms:
        connections = list(
            PlatformConnection.objects
            .filter(user=user, platform=platform)
            .prefetch_related("accounts")
            .order_by("-created_at")
        )

        accounts = list(
            PlatformAccount.objects
            .filter(user=user, platform=platform)
            .select_related("connection")
            .order_by("account_name", "account_id")
        )

        account_count = len(accounts)
        active_account_count = sum(1 for account in accounts if account.is_active)
        connection_count = len(connections)
        active_connection_count = sum(
            1 for connection in connections
            if connection.status == "active" and connection.is_active and connection.access_token
        )
        standalone_token_count = sum(
            1 for account in accounts
            if not account.connection_id and account.is_active and account.access_token
        )
        active_token_count = active_connection_count + standalone_token_count

        total_account_count += account_count
        total_active_account_count += active_account_count
        total_connection_count += connection_count
        total_active_connection_count += active_token_count

        platform_data.append({
            "platform": platform,
            "connections": connections,
            "accounts": accounts,
            "account_count": account_count,
            "active_account_count": active_account_count,
            "connection_count": connection_count,
            "active_connection_count": active_connection_count,
            "active_token_count": active_token_count,
        })
    return render(request, "platforms/platform_connections.html", {
        "platform_data": platform_data,
        "total_account_count": total_account_count,
        "total_active_account_count": total_active_account_count,
        "total_connection_count": total_connection_count,
        "total_active_connection_count": total_active_connection_count,
    })


@login_required
@require_POST
def platform_account_update(request, account_id):
    account = get_object_or_404(
        PlatformAccount.objects.select_related("platform"),
        id=account_id,
        user=request.user,
    )
    account_name = request.POST.get("account_name", "").strip()
    external_account_id = request.POST.get("account_id", "").strip()
    connection_id = request.POST.get("connection", "").strip()

    if not external_account_id:
        messages.error(request, "Platform ID boş bırakılamaz.")
        return redirect("platform_connections")

    connection = None
    if connection_id:
        connection = get_object_or_404(
            PlatformConnection,
            id=connection_id,
            user=request.user,
            platform=account.platform,
        )

    account.account_name = account_name
    account.account_id = external_account_id
    account.connection = connection
    account.is_active = request.POST.get("is_active") == "on"
    try:
        account.save(update_fields=[
            "account_name", "account_id", "connection", "is_active", "updated_at"
        ])
    except IntegrityError:
        messages.error(request, "Bu Platform ID aynı platformda zaten kayıtlı.")
    else:
        messages.success(request, f"{account.account_name or account.account_id} hesabı güncellendi.")
    return redirect("platform_connections")


@login_required
@require_POST
def platform_account_delete(request, account_id):
    account = get_object_or_404(PlatformAccount, id=account_id, user=request.user)
    account_label = account.account_name or account.account_id
    account.delete()
    messages.success(request, f"{account_label} hesabı silindi.")
    return redirect("platform_connections")
