"""Sentry policy shared by the web application and background workers."""
import logging

from django.core.exceptions import DisallowedHost, PermissionDenied
from django.http import Http404
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger

EXPECTED_REQUEST_ERRORS = (Http404, PermissionDenied, DisallowedHost)


def before_send(event, hint):
    exception = hint.get("exc_info")
    if exception and isinstance(exception[1], EXPECTED_REQUEST_ERRORS):
        return None
    if event.get("level") in {"debug", "info", "warning"}:
        return None
    return event


def initialize_sentry(dsn, environment, release=None):
    import sentry_sdk

    # ErrorManager captures explicitly, with tags and user context. Its local
    # log must not create an additional event before that context is attached.
    ignore_logger("core.ai_agents.error_manager")
    return sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        integrations=[DjangoIntegration(), CeleryIntegration(),
                      LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        before_send=before_send,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
    )
