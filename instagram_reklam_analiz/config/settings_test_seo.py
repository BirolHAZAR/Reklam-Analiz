"""Isolated SEO regression tests: no production database, Redis or telemetry."""
import os

os.environ["DEBUG"] = "True"
os.environ["SENTRY_DSN"] = ""

from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
RATE_LIMIT_ENABLED = False
SERPAPI_API_KEY = ''
GOOGLE_COMPETITOR_DETAILS_ENABLED = False
TIKTOK_AD_LIBRARY_ACCESS_TOKEN = ''
SEARCHAPI_API_KEY = ''
META_COMPETITOR_SOURCE = 'graph'
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
