from django.core.management.base import BaseCommand
from core.models import PlatformAccount
from core.services.measurement_policy import prune_unmeasured


class Command(BaseCommand):
    help = "Remove metricless ad entities only; preserve all measured history."

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group(required=True)
        scope.add_argument("--account", type=int)
        scope.add_argument("--all", action="store_true")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        accounts = PlatformAccount.objects.all()
        if not options["all"]:
            accounts = accounts.filter(pk=options["account"])
        for account in accounts:
            counts = prune_unmeasured(account, apply=options["apply"])
            self.stdout.write(str({"account": account.pk, "applied": options["apply"], **counts}))
