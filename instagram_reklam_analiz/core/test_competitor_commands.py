import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import Ad, Competitor, Platform


@override_settings(META_AD_LIBRARY_ACCESS_TOKEN="diagnostic-secret")
class CompetitorCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="command-test")
        self.platform, _ = Platform.objects.get_or_create(code="instagram", defaults={"name": "Instagram"})
        self.competitor = Competitor.objects.create(
            user=self.user, platform=self.platform, name="Example Brand",
            platform_identifier="@examplebrand",
        )

    def set_page(self, **kwargs):
        call_command("set_competitor_page", user_id=self.user.pk,
                     competitor_id=self.competitor.pk, page_reference="123", **kwargs)

    @patch("core.tasks.competitor_sync.queue_competitor_sync")
    def test_identity_update_does_not_claim_verification_or_queue_by_default(self, queue):
        with self.captureOnCommitCallbacks(execute=True):
            self.set_page(stdout=io.StringIO())
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data["facebook_page_id"], "123")
        self.assertEqual(self.competitor.raw_data["identity_status"], "unverified")
        queue.assert_not_called()

    def test_wrong_user_cannot_repair_another_users_competitor(self):
        with self.assertRaises(CommandError):
            call_command("set_competitor_page", user_id=self.user.pk + 1,
                         competitor_id=self.competitor.pk, page_reference="123")
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data, {})

    def test_changing_advertiser_with_existing_ads_is_rejected(self):
        Ad.objects.create(user=self.user, competitor=self.competitor,
                          source_type="COMPETITOR", platform_ad_id="ad-1")
        with self.assertRaises(CommandError):
            self.set_page()
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data, {})

    def test_conflicting_legacy_page_aliases_are_replaced(self):
        self.competitor.raw_data = {"page_id": "456", "facebook_page_ids": ["456"],
                                    "public_identity_evidence": {"name": "stale"}}
        self.competitor.save()
        self.set_page(stdout=io.StringIO())
        self.competitor.refresh_from_db()
        from core.services.competitor_live_sync import _page_ids_for_competitor
        self.assertEqual(_page_ids_for_competitor(self.competitor), ["123"])
        self.assertNotIn("public_identity_evidence", self.competitor.raw_data)

    @patch("core.tasks.competitor_sync.queue_competitor_sync")
    def test_explicit_sync_is_queued_after_commit(self, queue):
        with self.captureOnCommitCallbacks(execute=True):
            self.set_page(sync=True, stdout=io.StringIO())
            queue.assert_not_called()
        queue.assert_called_once_with(self.competitor.pk)

    @patch("core.services.competitor_live_sync.requests.get")
    def test_diagnostics_without_fetch_never_contacts_provider(self, get):
        output = io.StringIO()
        call_command("diagnose_competitors", user_id=self.user.pk, stdout=output)
        get.assert_not_called()
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data, {})
        self.assertNotIn("diagnostic-secret", output.getvalue())

    @patch("core.services.competitor_live_sync.MetaAdLibraryCompetitorSync._fetch")
    def test_fetch_uses_record_page_and_does_not_write_or_expose_token(self, fetch):
        self.competitor.raw_data = {"facebook_page_id": "123"}
        self.competitor.save()
        fetch.return_value = {"data": [{"id": "ad-1", "page_id": "123", "page_name": "diagnostic-secret"}]}
        output = io.StringIO()
        call_command("diagnose_competitors", user_id=self.user.pk, fetch=True, stdout=output)
        self.competitor.refresh_from_db()
        self.assertEqual(self.competitor.raw_data, {"facebook_page_id": "123"})
        self.assertFalse(self.competitor.ads.exists())
        self.assertNotIn("diagnostic-secret", output.getvalue())
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["upstream_rows"], 1)
        self.assertEqual(result["page_ids"], ["123"])
