"""Authenticated provider notifications; never match a local user primary key."""
import base64
import binascii
from datetime import datetime, timedelta, timezone as utc_timezone
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import IntegrationApplication, PlatformConnection


def callback_credentials(provider):
    # Disabling new logins must not disable revocation notifications.
    application = IntegrationApplication.objects.filter(provider=provider).first()
    if application:
        return str(application.client_id or "").strip(), str(application.client_secret or "").strip()
    prefix = "FACEBOOK" if provider == "facebook" else "INSTAGRAM"
    return (str(getattr(settings, prefix + "_APP_ID", "") or "").strip(),
            str(getattr(settings, prefix + "_APP_SECRET", "") or "").strip())


def verified_subject(signed_request, secret, app_id):
    if not isinstance(signed_request, str) or not 1 <= len(signed_request) <= 8192:
        raise ValueError
    signature, payload = signed_request.split(".")
    decode = lambda value: base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    supplied = decode(signature)
    expected = hmac.new(secret.encode(), payload.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError
    data = json.loads(decode(payload))
    if not isinstance(data, dict) or data.get("algorithm") != "HMAC-SHA256":
        raise ValueError
    subject = str(data.get("user_id", ""))
    issued = data.get("issued_at")
    if (not re.fullmatch(r"[0-9]{1,100}", subject) or isinstance(issued, bool)
            or not isinstance(issued, int) or issued <= 0
            or issued > timezone.now().timestamp() + 300
            or ("app_id" in data and str(data["app_id"]) != app_id)):
        raise ValueError
    return subject, datetime.fromtimestamp(issued, tz=utc_timezone.utc)


@csrf_exempt
@require_POST
def deauthorize(request, provider):
    if provider not in {"facebook", "instagram"}:
        return JsonResponse({"error": "not_found"}, status=404)
    app_id, secret = callback_credentials(provider)
    if not app_id or not secret:
        return JsonResponse({"error": "callback_unavailable"}, status=503)
    try:
        subject, issued_at = verified_subject(request.POST.get("signed_request"), secret, app_id)
    except (ValueError, TypeError, UnicodeError, binascii.Error, OverflowError, OSError):
        return JsonResponse({"error": "invalid_signed_request"}, status=403)
    identity = Q(extra_data__meta_user_id=subject)
    if provider == "instagram":
        identity |= Q(extra_data__instagram_business_account_id=subject)
    with transaction.atomic():
        connections = PlatformConnection.objects.select_for_update().filter(
            identity, platform__code=provider, extra_data__meta_app_id=app_id,
            # A delayed/replayed event must not revoke a newer authorization.
            created_at__lt=issued_at + timedelta(seconds=1),
        )
        for connection in connections:
            connection.is_active, connection.status = False, "disconnected"
            connection.access_token, connection.refresh_token = "", ""
            connection.token_expiry, connection.scopes = None, []
            connection.extra_data = {key: value for key, value in (connection.extra_data or {}).items()
                                     if key not in {"choices", "pending"}}
            connection.extra_data["meta_deauthorized_at"] = issued_at.isoformat()
            connection.save(update_fields=["is_active", "status", "access_token", "refresh_token",
                                           "token_expiry", "scopes", "extra_data", "updated_at"])
            connection.accounts.update(is_active=False, access_token="", refresh_token="", token_expiry=None)
    # Idempotent, non-enumerating acknowledgement. Data deletion uses the
    # separately configured, public deletion-instructions URL.
    return JsonResponse({"success": True})
