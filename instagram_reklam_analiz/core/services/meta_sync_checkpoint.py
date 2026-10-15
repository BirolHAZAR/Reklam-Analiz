"""Resume read-only Meta pagination within one Celery sync job."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json

from django.core.cache import cache

_session = ContextVar("meta_sync_checkpoint", default=None)
# Large jobs can spend several hours in provider-enforced quota windows.
TTL = 24 * 3600


@contextmanager
def meta_read_checkpoint(job_key):
    if not job_key:
        yield
        return
    registry = "meta:sync:" + hashlib.sha256(str(job_key).encode()).hexdigest()
    marker = _session.set(registry)
    try:
        yield
    except Exception:
        # Preserve successfully read pages while the task waits for its retry.
        raise
    else:
        cache.delete_many([*(cache.get(registry) or []), registry])
    finally:
        _session.reset(marker)


def checkpoint_key(token, path, params):
    registry = _session.get()
    # OAuth discovery can return tokens; checkpoint only advertising reads.
    if not registry or not path.startswith("act_") or path.rsplit("/", 1)[-1] not in {"ads", "insights", "campaigns"}:
        return None
    fingerprint = json.dumps([registry, token, path, params], sort_keys=True, default=str)
    return "meta:page:" + hashlib.sha256(fingerprint.encode()).hexdigest()


def save_checkpoint(key, rows, after, complete):
    if not key:
        return
    registry = _session.get()
    keys = set(cache.get(registry) or [])
    keys.add(key)
    cache.set(registry, list(keys), timeout=TTL)
    cache.set(key, {"rows": rows, "after": after, "complete": complete}, timeout=TTL)
