import logging
from unittest.mock import Mock

import sentry_sdk
from django.core.exceptions import DisallowedHost, PermissionDenied
from django.http import Http404
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse
from sentry_sdk.transport import Transport

from config.sentry import before_send, initialize_sentry
from core.ai_agents.error_manager import capture_errors


class RecordingTransport(Transport):
    def __init__(self, options):
        super().__init__(options)
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.headers.get("type") == "event":
                self.events.append(item.payload.json)


class SentryPolicyTests(SimpleTestCase):
    def test_expected_request_errors_are_filtered(self):
        for exc in (Http404(), PermissionDenied(), DisallowedHost()):
            with self.subTest(exception=type(exc)):
                self.assertIsNone(before_send({"level": "error"}, {"exc_info": (type(exc), exc, None)}))

    def test_real_failures_are_preserved(self):
        exc = RuntimeError("Database unavailable")
        event = {"level": "error"}
        self.assertIs(before_send(event, {"exc_info": (type(exc), exc, None)}), event)
        self.assertIs(before_send({"level": "fatal"}, {} )["level"], "fatal")

    def test_low_severity_messages_are_filtered(self):
        for level in ("debug", "info", "warning"):
            self.assertIsNone(before_send({"level": level}, {}))

    def test_expected_http_errors_keep_their_response_semantics(self):
        request = Mock()
        for exc in (Http404(), PermissionDenied()):
            def view(request):
                raise exc
            with self.assertRaises(type(exc)):
                capture_errors(view)(request)

    def test_fault_injection_route_is_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("sentry_test")

    def test_sdk_keeps_real_logs_and_avoids_explicit_capture_duplicates(self):
        with initialize_sentry("https://public@example.com/1", "test"):
            client = sentry_sdk.get_client()
            original = client.transport
            recorder = RecordingTransport(client.options)
            client.transport = recorder
            try:
                logging.getLogger("core.ai_agents.error_manager").error("Explicit capture log")
                sentry_sdk.capture_message("Informational noise", level="info")
                sentry_sdk.capture_exception(RuntimeError("Explicit capture"))
                logging.getLogger("application.test").error("Actual log failure")
                self.assertEqual(len(recorder.events), 2)
                self.assertEqual(recorder.events[0]["exception"]["values"][0]["type"], "RuntimeError")
                self.assertEqual(recorder.events[1]["logger"], "application.test")
                self.assertFalse(client.options["include_local_variables"])
                self.assertEqual(client.options["max_request_body_size"], "never")
            finally:
                client.transport = original
