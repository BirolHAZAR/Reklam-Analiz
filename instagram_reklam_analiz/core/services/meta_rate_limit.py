"""Shared Meta cooldowns; never store credentials or repeat write requests."""
import hashlib
import json
import math
from datetime import timezone as utc_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

from django.core.cache import cache
from django.utils import timezone

RATE_CODES = {4, 17, 32, 613, 80000, 80001, 80002, 80003, 80004, 80005, 80006, 80008, 80009, 80014}


class MetaRateLimitError(ValueError):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__(f"Meta istek sınırı: {self.retry_after} saniye sonra yeniden deneyin.")


def _key(url, kwargs):
    if urlsplit(url).hostname not in {"graph.facebook.com", "graph.instagram.com", "api.instagram.com"}:
        return None
    headers = kwargs.get("headers") or {}
    params = kwargs.get("params") or {}
    data = kwargs.get("data") or {}
    token = params.get("input_token") or headers.get("Authorization") or params.get("access_token") or data.get("access_token") or params.get("fb_exchange_token")
    if not token:
        return None
    token = str(token)
    if token.startswith("Bearer "):
        token = token[7:]
    return "meta:cooldown:" + hashlib.sha256(token.encode()).hexdigest()


def before_request(url, kwargs):
    key = _key(url, kwargs)
    if key:
        remaining = (cache.get(key) or 0) - timezone.now().timestamp()
        if remaining > 0:
            raise MetaRateLimitError(remaining)


def after_response(url, kwargs, response, payload):
    key = _key(url, kwargs)
    if not key:
        return
    error = payload.get("error") if isinstance(payload, dict) else None
    error = error if isinstance(error, dict) else {}
    headers = response.headers
    delay = 0
    raw_retry = headers.get("Retry-After")
    if raw_retry:
        try:
            delay = max(0, float(raw_retry))
        except (TypeError, ValueError):
            try:
                deadline = parsedate_to_datetime(raw_retry)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=utc_timezone.utc)
                delay = max(0, deadline.timestamp() - timezone.now().timestamp())
            except (TypeError, ValueError, OverflowError):
                pass
    for name in ("X-App-Usage", "X-Page-Usage", "X-Ad-Account-Usage", "X-Business-Use-Case-Usage"):
        try:
            usage = json.loads(headers.get(name) or "{}")
        except (TypeError, ValueError):
            continue
        pending = [usage]
        while pending:
            item = pending.pop()
            if isinstance(item, list):
                pending.extend(item)
            elif isinstance(item, dict):
                pending.extend(value for value in item.values() if isinstance(value, (dict, list)))
                percentages = [item.get(field, 0) for field in ("call_count", "total_cputime", "total_time", "acc_id_util_pct")]
                if any(isinstance(value, (int, float)) and value >= 90 for value in percentages):
                    regain = item.get("estimated_time_to_regain_access", 0)
                    delay = max(delay, 60, float(regain) * 60 if isinstance(regain, (int, float)) else 0)
    limited = response.status_code == 429 or str(error.get("code")) in {str(code) for code in RATE_CODES}
    if limited:
        delay = max(delay, 60)
    if delay > 0:
        until = timezone.now().timestamp() + delay
        # Preserve a longer cooldown already observed by another request.
        until = max(until, cache.get(key) or 0)
        cache.set(key, until, timeout=max(1, math.ceil(until - timezone.now().timestamp())))
    if limited:
        raise MetaRateLimitError(delay)
