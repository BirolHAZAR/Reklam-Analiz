"""Shared identity and uniqueness rules for member and agency competitors."""
import re
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db.models import Value
from django.db.models.functions import Lower, Replace, Trim

from core.models import AgencyClient, Competitor


def normalize_competitor_identifier(value, platform_code=None):
    value = str(value or "").strip()
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password:
            raise ValueError('Geçerli bir profil veya web sitesi bağlantısı girin.')
        if parsed.hostname == 'adstransparency.google.com':
            match = re.fullmatch(r'/advertiser/(AR\d+)/?', parsed.path, re.I)
            if not match:
                raise ValueError('Google reklamveren bağlantısı /advertiser/AR... biçiminde olmalı.')
            value = match.group(1)
        elif platform_code == 'google_ads' and parsed.hostname:
            value = parsed.hostname.removeprefix('www.')
        elif parsed.hostname in {'tiktok.com', 'www.tiktok.com'}:
            value = parsed.path.strip('/').lstrip('@')
        elif parsed.hostname in {"instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com"}:
            value = parsed.path.strip("/")
        else:
            raise ValueError("Desteklenen platforma ait hesap adı, ID veya profil bağlantısı girin.")
    value = value.lstrip("@").casefold()
    if not re.fullmatch(r"[a-z0-9._-]{1,255}", value):
        raise ValueError("Geçerli bir hesap adı / ID girin.")
    return value


def lock_competitor_scope(user, client=None):
    # Parent row locks also serialize inserts when the competitor does not exist yet.
    if client is not None:
        AgencyClient.objects.select_for_update().get(pk=client.pk)
    else:
        get_user_model().objects.select_for_update().get(pk=user.pk)


def duplicate_competitors(user, platform, identifier, client=None, page_id=""):
    qs = Competitor.objects.filter(platform=platform, agency_client=client)
    if client is None:
        qs = qs.filter(user=user)
    qs = qs.annotate(canonical_identifier=Lower(Replace(Trim("platform_identifier"), Value("@"), Value(""))))
    from django.db.models import Q
    match = Q(canonical_identifier=identifier)
    if page_id:
        match |= Q(raw_data__facebook_page_id=page_id)
        if platform.code == "facebook":
            match |= Q(platform_identifier=page_id)
    return qs.filter(match)


def identity_change_error(competitor, platform, identifier, page_id):
    from core.services.competitor_live_sync import _page_ids_for_competitor
    old_identifier = str(competitor.platform_identifier or "").strip().lstrip("@").casefold()
    old_pages = _page_ids_for_competitor(competitor)
    new_pages = [page_id] if page_id else ([identifier] if platform.code == "facebook" and identifier.isdigit() else [])
    changed = competitor.platform_id != platform.pk or old_pages != new_pages or old_identifier != identifier
    if changed and competitor.ads.exists():
        return "Bu rakibin reklam geçmişi var. Farklı reklamvereni ayrı rakip olarak ekleyin; mevcut reklamların firması değiştirilemez."
    if platform.code == "facebook" and identifier.isdigit() and page_id and identifier != page_id:
        return "Hesap ID'si ile Facebook sayfa ID'si eşleşmiyor."
    return ""


def platform_identity_metadata(platform, identifier):
    """Keep IDs from different platform namespaces separate."""
    if platform.code == "instagram" and identifier.isascii() and identifier.isdigit():
        return {"instagram_user_id": identifier}
    if platform.code == 'google_ads' and re.fullmatch(r'ar\d+', identifier, re.I):
        return {'google_advertiser_id': identifier.upper()}
    if platform.code == 'tiktok' and identifier.isascii() and identifier.isdigit():
        return {'tiktok_business_id': identifier}
    return {}


def set_page_reference(raw, page_id, reset=True):
    raw = dict(raw or {})
    for key in ("facebook_page_ids", "page_ids", "page_id", "public_identity_evidence"):
        raw.pop(key, None)
    raw["facebook_page_id"] = page_id
    if reset:
        for key in list(raw):
            if key.startswith(("last_live_sync", "search_")):
                raw.pop(key)
        raw.update(identity_status="unverified", identity_check_message="")
    return raw
