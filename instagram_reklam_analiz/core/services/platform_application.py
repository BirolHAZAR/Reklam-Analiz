"""Resolve app credentials for the existing Instagram token maintenance tools."""
from django.conf import settings


def instagram_application_credentials():
    from core.models import IntegrationApplication
    app = IntegrationApplication.objects.filter(provider="instagram").first()
    if app is None:
        return settings.INSTAGRAM_APP_ID, settings.INSTAGRAM_APP_SECRET
    if not app.enabled or not app.client_id or not app.client_secret:
        raise ValueError("Instagram uygulama ayarları etkin değil veya eksik.")
    return app.client_id, app.client_secret
