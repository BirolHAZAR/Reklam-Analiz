from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from core.services.ads_integrations import IntegrationRateLimitError, meta_rows
from core.services.meta_rate_limit import MetaRateLimitError
from core.services.meta_sync_checkpoint import meta_read_checkpoint


class MetaPaginationCheckpointTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.rate = IntegrationRateLimitError(MetaRateLimitError(60))
        self.first = {"data": [{"id": "a1"}], "paging": {
            "next": "https://untrusted.invalid/?token=secret", "cursors": {"after": "next-page"}}}

    @patch("core.services.ads_integrations._request")
    def test_retry_resumes_cursor_without_repeating_first_page_or_following_next_url(self, request):
        request.side_effect = [self.first, self.rate]
        with self.assertRaises(IntegrationRateLimitError), meta_read_checkpoint("manual:1"):
            meta_rows("secret-token", "act_1/ads", {"fields": "id"})
        request.reset_mock()
        request.side_effect = [{"data": [{"id": "a2"}]}]
        with meta_read_checkpoint("manual:1"):
            rows = meta_rows("secret-token", "act_1/ads", {"fields": "id"})
        self.assertEqual(rows, [{"id": "a1"}, {"id": "a2"}])
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs["params"]["after"], "next-page")
        self.assertNotIn("untrusted.invalid", request.call_args.args[1])
        request.reset_mock()
        request.side_effect = [{"data": []}]
        with meta_read_checkpoint("manual:1"):
            meta_rows("secret-token", "act_1/ads", {"fields": "id"})
        self.assertNotIn("after", request.call_args.kwargs["params"])

    @patch("core.services.ads_integrations._request")
    def test_completed_inventory_is_reused_when_insights_hit_quota(self, request):
        request.side_effect = [{"data": [{"id": "ad"}]}, self.rate]
        with self.assertRaises(IntegrationRateLimitError), meta_read_checkpoint("manual:2"):
            meta_rows("token", "act_1/ads", {})
            meta_rows("token", "act_1/insights", {})
        request.reset_mock()
        request.side_effect = [{"data": [{"ad_id": "ad", "spend": "5"}]}]
        with meta_read_checkpoint("manual:2"):
            self.assertEqual(meta_rows("token", "act_1/ads", {}), [{"id": "ad"}])
            meta_rows("token", "act_1/insights", {})
        request.assert_called_once()
        self.assertTrue(request.call_args.args[1].endswith("/insights"))

    @patch("core.services.ads_integrations._request")
    def test_other_job_token_or_query_cannot_reuse_partial_rows(self, request):
        request.side_effect = [self.first, self.rate]
        with self.assertRaises(IntegrationRateLimitError), meta_read_checkpoint("manual:1"):
            meta_rows("owner-token", "act_1/ads", {"fields": "id"})
        for job, token, fields in [("manual:other", "owner-token", "id"),
                                   ("manual:1", "other-token", "id"),
                                   ("manual:1", "owner-token", "id,name")]:
            request.reset_mock()
            request.side_effect = [{"data": []}]
            with meta_read_checkpoint(job):
                self.assertEqual(meta_rows(token, "act_1/ads", {"fields": fields}), [])
            self.assertNotIn("after", request.call_args.kwargs["params"])

    @patch("core.services.ads_integrations._request")
    def test_oauth_token_discovery_is_never_checkpointed(self, request):
        request.side_effect = [{"data": [{"access_token": "private"}]}, self.rate]
        with self.assertRaises(IntegrationRateLimitError), meta_read_checkpoint("manual:1"):
            meta_rows("token", "me/accounts", {})
            meta_rows("token", "act_1/ads", {})
        request.reset_mock()
        request.side_effect = [{"data": []}]
        with meta_read_checkpoint("manual:1"):
            self.assertEqual(meta_rows("token", "me/accounts", {}), [])
        request.assert_called_once()
