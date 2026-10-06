# core/views/rakip_ekle.py
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.models import Ad, Competitor, Platform, PlatformAccount
from core.services.agency_scope import (
    get_agency_scope,
    platform_accounts_for_request,
    scope_client_queryset,
    scope_queryset,
)
from core.services.cache_service import CacheService
from core.services.competitor_live_sync import parse_meta_page_reference, competitor_library_url
from core.services.competitor_public_sources import SUPPORTED_COMPETITOR_PLATFORMS, source_status, competitor_user_error
from core.services.competitor_identity import (
    normalize_competitor_identifier, duplicate_competitors, lock_competitor_scope,
    identity_change_error, set_page_reference, platform_identity_metadata,
)

logger = logging.getLogger(__name__)


COMPETITORS_CACHE_TIMEOUT = 300


def _invalidate_competitor_cache(user, competitor_id=None):
    CacheService.bump_version("competitors", user.id)
    CacheService.bump_version("competitor_movements_page", user.id)
    CacheService.bump_version("competitor_movements", user.id)
    CacheService.bump_version("competitor_intelligence", user.id)
    if competitor_id:
        CacheService.bump_version("competitor_ads", user.id, competitor_id)


def _platform_code(platform):
    return getattr(platform, "code", None) or getattr(platform, "slug", None) or (platform.name.lower().replace(" ", "_") if platform else "other")


def _competitor_payload(competitor):
    return {
        "id": competitor.id,
        "name": competitor.name or competitor.platform_identifier,
        "platform_identifier": competitor.platform_identifier,
        "platform_id": competitor.platform_id,
        "platform_code": _platform_code(competitor.platform),
        "platform_name": competitor.platform.name if competitor.platform else "Diğer",
        "platform_account_id": competitor.platform_account_id,
        "agency_client_id": competitor.agency_client_id,
        "agency_client_name": competitor.agency_client.name if competitor.agency_client else "",
        "website": competitor.website or "",
        "category": competitor.category or "direct",
        "description": competitor.description or "",
        "is_active": competitor.is_active,
        "sync_status": (competitor.raw_data or {}).get("last_live_sync_status", "pending"),
        "sync_error": competitor_user_error((competitor.raw_data or {}).get("last_live_sync_error", "")),
        "sync_warning": (competitor.raw_data or {}).get("last_live_sync_warning", ""),
        "identity_status": (competitor.raw_data or {}).get("identity_status", "unverified"),
        "identity_message": (competitor.raw_data or {}).get("identity_check_message", ""),
        "facebook_page_id": (competitor.raw_data or {}).get("facebook_page_id", ""),
        "instagram_user_id": (competitor.raw_data or {}).get("instagram_user_id", ""),
        "library_url": competitor_library_url(competitor),
        "source_status": source_status(competitor),
        "total_ads": competitor.ads.filter(source_type="COMPETITOR").count(),
        "created_at": competitor.created_at.isoformat() if competitor.created_at else None,
    }


def _get_user_platform_account(request, platform, agency_client=None):
    if not platform:
        return None

    accounts = platform_accounts_for_request(request, active_only=True).filter(platform=platform)
    if agency_client is not None:
        accounts = accounts.filter(agency_client=agency_client)
    return (
        accounts
        .order_by("-created_at")
        .first()
    )


@login_required
@transaction.atomic
def rakip_ekle(request):
    """
    Rakip ekleme sayfası.

    Kalıcı V2 mimari:
    - Rakip profili Competitor tablosunda tutulur.
    - Rakibe ait reklamlar Ad(source_type='COMPETITOR', competitor=competitor) olarak tutulur.
    """

    agency_scope = get_agency_scope(request)
    platforms = Platform.objects.filter(is_active=True, code__in=SUPPORTED_COMPETITOR_PLATFORMS).order_by("name")

    if request.method == "POST":
        _invalidate_competitor_cache(request.user)
        platform_id = request.POST.get("platform")
        if not platform_id:
            messages.error(request, "Lütfen bir platform seçin.")
            return redirect("rakip_ekle")
        platform = get_object_or_404(Platform, id=platform_id, is_active=True, code__in=SUPPORTED_COMPETITOR_PLATFORMS)
        platform_identifier = (request.POST.get("platform_identifier") or "").strip()
        try:
            platform_identifier = normalize_competitor_identifier(platform_identifier, platform.code)
            page_id = parse_meta_page_reference(request.POST.get("facebook_page_id")) if platform.code in {'instagram', 'facebook'} else ''
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("rakip_ekle")
        name = (request.POST.get("name") or "").strip() or platform_identifier
        website = (request.POST.get("website") or "").strip()
        category = request.POST.get("category") or "direct"
        description = (request.POST.get("description") or "").strip()
        is_active = request.POST.get("is_active") == "on"
        selected_client = agency_scope.selected_client
        if agency_scope.is_agency:
            requested_client_id = str(request.POST.get("agency_client") or "").strip()
            selected_client = next(
                (client for client in agency_scope.clients if str(client.id) == requested_client_id),
                None,
            )
            if selected_client is None:
                messages.error(request, "Rakibin bağlanacağı ajans firmasını seçin.")
                return redirect("rakip_ekle")

        if not platform_id:
            messages.error(request, "Lütfen bir platform seçin.")
            return redirect("rakip_ekle")

        if not platform_identifier:
            messages.error(request, "Hesap adı / ID boş olamaz.")
            return redirect("rakip_ekle")

        if platform.code == "facebook" and platform_identifier.isdigit() and page_id and platform_identifier != page_id:
            messages.error(request, "Hesap ID'si ile Facebook sayfa ID'si eşleşmiyor.")
            return redirect("rakip_ekle")
        platform_account = _get_user_platform_account(request, platform, selected_client)

        lock_competitor_scope(request.user, selected_client)
        existing_qs = duplicate_competitors(request.user, platform, platform_identifier, selected_client, page_id)
        existing = existing_qs.first()

        if existing:
            messages.warning(request, f"{platform_identifier} zaten rakip listenizde var.")
            return redirect("rakip_ekle")

        competitor = Competitor.objects.create(
            user=request.user,
            platform=platform,
            platform_account=platform_account,
            agency_client=selected_client,
            platform_identifier=platform_identifier,
            name=name,
            website=website or None,
            category=category,
            description=description,
            is_active=is_active,
            raw_data={
                **platform_identity_metadata(platform, platform_identifier),
                "created_from": "rakip_ekle",
                "facebook_page_id": page_id,
                "identity_status": "unverified",
                "platform_code": _platform_code(platform),
                "platform_name": platform.name,
                "created_at": timezone.now().isoformat(),
            },
        )

        if competitor.is_active:
            from core.tasks.competitor_sync import queue_competitor_sync
            transaction.on_commit(lambda: queue_competitor_sync(competitor.id))
        messages.success(request, f"{competitor.name} başarıyla eklendi.")
        return redirect("rakip_ekle")

    return render(request, "rakip/rakip_ekle.html", {"platforms": platforms, "agency_scope": agency_scope})


@login_required
def api_rakipler(request):
    agency_scope = get_agency_scope(request)
    version = CacheService.get_version("competitors", request.user.id)
    cached = CacheService.get(
        "competitors", "user", request.user.id, "scope", agency_scope.cache_key, version=version
    )
    if cached is not None:
        return JsonResponse(cached)

    competitors = (
        scope_client_queryset(
            request,
            Competitor.objects.filter(platform__code__in=SUPPORTED_COMPETITOR_PLATFORMS),
        )
        .select_related("platform", "platform_account")
        .order_by("platform__name", "name")
    )

    data = [_competitor_payload(c) for c in competitors]
    payload = {"success": True, "rakipler": data, "count": len(data)}
    CacheService.set(
        "competitors",
        "user",
        request.user.id,
        "scope",
        agency_scope.cache_key,
        value=payload,
        timeout=COMPETITORS_CACHE_TIMEOUT,
        version=version,
    )
    return JsonResponse(payload)


@login_required
def api_rakip_detay(request, competitor_id):
    competitor = get_object_or_404(
        scope_client_queryset(
            request,
            Competitor.objects.select_related("platform", "platform_account"),
        ),
        id=competitor_id,
    )
    _invalidate_competitor_cache(request.user, competitor.id)
    return JsonResponse({"success": True, "competitor": _competitor_payload(competitor)})


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_rakip_guncelle(request, competitor_id):
    competitor = get_object_or_404(scope_client_queryset(request, Competitor.objects.all()), id=competitor_id)
    lock_competitor_scope(competitor.user, competitor.agency_client)
    competitor = Competitor.objects.select_for_update().get(pk=competitor.pk)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Geçersiz JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"success": False, "error": "JSON nesnesi gerekiyor."}, status=400)

    platform_id = payload.get("platform_id")
    if platform_id and not str(platform_id).isdigit():
        return JsonResponse({"success": False, "error": "Geçerli platform ID'si gerekiyor."}, status=400)
    platform = Platform.objects.filter(id=platform_id, code__in=SUPPORTED_COMPETITOR_PLATFORMS).first() if platform_id else competitor.platform
    if not platform or _platform_code(platform) not in SUPPORTED_COMPETITOR_PLATFORMS:
        return JsonResponse({"success": False, "error": "Bu platform için rakip reklam takibi desteklenmiyor."}, status=400)
    try:
        page_id = parse_meta_page_reference(payload.get("facebook_page_id", (competitor.raw_data or {}).get("facebook_page_id", ""))) if platform.code in {'instagram', 'facebook'} else ''
        platform_identifier = normalize_competitor_identifier(payload.get("platform_identifier", competitor.platform_identifier), platform.code)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    platform_account = (competitor.platform_account if platform.pk == competitor.platform_id else
                        _get_user_platform_account(request, platform, competitor.agency_client))

    name = str(payload.get("name", competitor.name) or "").strip() or platform_identifier
    website = str(payload.get("website", competitor.website) or "").strip()
    category = payload.get("category", competitor.category) or "direct"
    description = str(payload.get("description", competitor.description) or "").strip()
    is_active = payload.get("is_active", competitor.is_active)
    if not isinstance(is_active, bool):
        return JsonResponse({"success": False, "error": "Aktif takip değeri true/false olmalıdır."}, status=400)

    if not platform_identifier:
        return JsonResponse({"success": False, "error": "Hesap adı / ID boş olamaz."}, status=400)

    identity_error = identity_change_error(competitor, platform, platform_identifier, page_id)
    if identity_error:
        return JsonResponse({"success": False, "error": identity_error}, status=400)
    duplicate = (
        duplicate_competitors(competitor.user, platform, platform_identifier, competitor.agency_client, page_id)
        .exclude(id=competitor.id)
        .exists()
    )
    if duplicate:
        return JsonResponse({"success": False, "error": "Bu rakip zaten kayıtlı."}, status=400)

    identity_changed = (competitor.platform_id != platform.pk or
                        competitor.platform_identifier.strip().lstrip('@').casefold() != platform_identifier or
                        (competitor.raw_data or {}).get('facebook_page_id', '') != page_id)
    competitor.platform = platform
    competitor.platform_account = platform_account
    competitor.platform_identifier = platform_identifier
    competitor.name = name
    competitor.website = website or None
    competitor.category = category
    competitor.description = description
    competitor.is_active = is_active

    raw_data = set_page_reference(competitor.raw_data, page_id, reset=identity_changed)
    if identity_changed:
        raw_data.pop('google_advertiser_candidates', None)
        for identity_key in ('google_advertiser_id', 'tiktok_business_id'):
            raw_data.pop(identity_key, None)
    raw_data.pop("instagram_user_id", None)
    raw_data.update(platform_identity_metadata(platform, platform_identifier))
    raw_data.update({
        "facebook_page_id": page_id,
        "platform_code": _platform_code(platform),
        "platform_name": platform.name if platform else "Diğer",
        "updated_at": timezone.now().isoformat(),
    })
    competitor.raw_data = raw_data
    competitor.save()
    _invalidate_competitor_cache(request.user, competitor.id)
    if competitor.is_active:
        from core.tasks.competitor_sync import queue_competitor_sync
        transaction.on_commit(lambda: queue_competitor_sync(competitor.id))

    # Bağlı rakip reklamları da yeni rakip bilgisiyle eşitlenir.
    Ad.objects.filter(competitor=competitor, source_type="COMPETITOR").update(
        is_active=is_active,
    )

    return JsonResponse({"success": True, "competitor": _competitor_payload(competitor)})


@login_required
@require_http_methods(["DELETE"])
def api_rakip_sil(request, competitor_id):
    competitor = get_object_or_404(scope_client_queryset(request, Competitor.objects.all()), id=competitor_id)

    # Rakip silinince ona ait rakip reklamlar da silinir.
    related_ads = scope_queryset(
        request,
        Ad.objects.filter(source_type="COMPETITOR", competitor=competitor),
    )
    deleted_ads_count, _ = related_ads.delete()
    deleted_competitor_id = competitor.id
    competitor.delete()

    _invalidate_competitor_cache(request.user, deleted_competitor_id)
    return JsonResponse({"success": True, "deleted_ads_count": deleted_ads_count})
