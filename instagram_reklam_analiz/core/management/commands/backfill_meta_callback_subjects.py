"""Associate existing Facebook connections with provider-verified subjects."""
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import PlatformConnection
from core.services.ads_integrations import _request, IntegrationError
from core.services.demo_policy import is_demo_object
from core.views.meta_deauthorization import callback_credentials


class Command(BaseCommand):
    help = "Verify Facebook callback identity metadata. Read-only unless --apply is supplied."

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group(required=True)
        scope.add_argument("--username")
        scope.add_argument("--all-users", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        app_id, secret = callback_credentials("facebook")
        if not app_id or not secret:
            raise CommandError("Meta callback credentials are not configured.")
        connections = PlatformConnection.objects.filter(
            platform__code="facebook", is_active=True,
        ).order_by("pk")
        if options.get("username"):
            connections = connections.filter(user__username=options["username"])
        for connection in connections:
            if is_demo_object(connection) or not connection.access_token:
                self.stdout.write(f"connection={connection.pk} skipped=True")
                continue
            token = connection.access_token
            try:
                payload = _request("GET", settings.FACEBOOK_GRAPH_URL + "/debug_token",
                    operation="Meta callback kimliğini doğrulama",
                    params={"input_token": token, "access_token": app_id + "|" + secret})
            except IntegrationError:
                raise CommandError("Meta identity check failed; no unverified identity was saved.") from None
            data = payload.get("data", {})
            subject = str(data.get("user_id", ""))
            if (data.get("is_valid") is not True or str(data.get("app_id", "")) != app_id
                    or not re.fullmatch(r"[0-9]{1,100}", subject)):
                raise CommandError("Token identity or application does not match; no identity was saved.")
            if options["apply"]:
                with transaction.atomic():
                    current = PlatformConnection.objects.select_for_update().get(pk=connection.pk)
                    if not current.is_active or current.access_token != token:
                        raise CommandError("Connection changed during verification; run again.")
                    current.extra_data = {**(current.extra_data or {}),
                                          "meta_user_id": subject, "meta_app_id": app_id}
                    current.save(update_fields=["extra_data", "updated_at"])
            self.stdout.write(f"connection={connection.pk} verified=True saved={options['apply']}")
