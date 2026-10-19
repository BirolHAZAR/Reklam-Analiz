from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import requests
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import IntegrationApplication, Platform, PlatformAccount, PlatformConnection
from core.services import ads_integrations as api
from core.services import linkedin_ads as li


class LinkedInAnalyticsBoundaryTests(SimpleTestCase):
    @override_settings(LINKEDIN_ADS_API_VERSION="202610")
    @patch.object(li, "_request", return_value={"elements": []})
    def test_prepared_request_preserves_restli_grammar_and_encodes_urns(self, request):
        params = {"q": "analytics", "fields": "pivotValues,dateRange,impressions,clicks,costInLocalCurrency",
                  "accounts": "List(urn:li:sponsoredAccount:123)",
                  "campaigns": "List(urn:li:sponsoredCampaign:456)",
                  "dateRange": "(start:(year:2026,month:10,day:1),end:(year:2026,month:10,day:19))"}
        li.read("private-token", "adAnalytics", params)
        args, kwargs = request.call_args
        prepared = requests.Request(args[0], args[1], **kwargs).prepare()
        query = urlparse(prepared.url).query
        self.assertIn("fields=pivotValues,dateRange,impressions,clicks,costInLocalCurrency", query)
        self.assertIn("accounts=List(urn%3Ali%3AsponsoredAccount%3A123)", query)
        self.assertIn("campaigns=List(urn%3Ali%3AsponsoredCampaign%3A456)", query)
        self.assertIn("dateRange=(start:(year:2026,month:10,day:1),end:(year:2026,month:10,day:19))", query)
        self.assertEqual(parse_qs(query), {key: [str(value)] for key, value in params.items()})
        self.assertNotIn("private-token", prepared.url)

    @override_settings(LINKEDIN_ADS_API_VERSION="202610")
    @patch.object(li, "_request", return_value={"elements": []})
    def test_search_grammar_survives_and_cursor_cannot_add_query_parameters(self, request):
        cursor = "a+b/:()&fields=secret%2Cmore"
        search = "(status:(values:List(ACTIVE,PAUSED,ARCHIVED)))"
        li.read("private-token", "adAccounts/123/adCampaigns",
                {"q": "search", "search": search, "pageSize": 100, "pageToken": cursor})
        args, kwargs = request.call_args
        query = urlparse(requests.Request(args[0], args[1], **kwargs).prepare().url).query
        self.assertIn("search=" + search, query)
        self.assertEqual(parse_qs(query), {"q": ["search"], "search": [search],
                                         "pageSize": ["100"], "pageToken": [cursor]})

    def test_linkedin_campaign_states_have_human_readable_labels(self):
        from core.services.campaign_reporting import decorate_campaign
        for state, group in (("COMPLETED", "inactive"), ("CANCELED", "inactive"),
                             ("DRAFT", "other"), ("PENDING_DELETION", "inactive")):
            row = decorate_campaign({"status": state})
            self.assertEqual(row["status_group"], group)
            self.assertNotEqual(row["status_label"], "Durum bilinmiyor")

    @patch.object(li, "read")
    def test_rounded_month_boundary_is_not_reported_as_selected_period(self, read):
        read.return_value = {"elements": [{"dateRange": {
            "start": {"year": 2026, "month": 1, "day": 1},
            "end": {"year": 2026, "month": 1, "day": 31}}}]}
        with self.assertRaisesMessage(api.IntegrationError, "tarihleri yuvarladı"):
            li.analytics("private", "123", date(2026, 1, 15), date(2026, 1, 31))

    @patch.object(li, "read")
    def test_exact_range_is_accepted(self, read):
        row = {"dateRange": {"start": {"year": 2026, "month": 10, "day": 1},
                             "end": {"year": 2026, "month": 10, "day": 19}}}
        read.return_value = {"elements": [row]}
        self.assertEqual(li.analytics("private", "123", date(2026, 10, 1), date(2026, 10, 19)), [row])

    @patch.object(li, "read")
    def test_truncated_report_is_rejected(self, read):
        read.return_value = {"elements": [{}] * 15000}
        with self.assertRaisesMessage(api.IntegrationError, "eksiksiz"):
            li.analytics("private", "123", date(2026, 10, 1), date(2026, 10, 19))

    @patch.object(li, "read")
    def test_malformed_schedule_is_not_rendered(self, read):
        read.return_value = {"elements": [{"account": "urn:li:sponsoredAccount:123", "id": 7,
                                          "runSchedule": "invalid"}]}
        with self.assertRaises(api.IntegrationError):
            li.campaigns("private", "123")


@override_settings(LINKEDIN_ADS_APPROVED=True, LINKEDIN_ADS_API_VERSION="202610",
                   LINKEDIN_CLIENT_ID="li-client", LINKEDIN_CLIENT_SECRET="private-secret",
                   LINKEDIN_REDIRECT_URI="https://www.reklamanaliz.net/connect/linkedin/callback/")
class LinkedInAdsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="linkedin-owner")
        self.other = get_user_model().objects.create_user(username="linkedin-other")
        self.client.force_login(self.user)
        self.platform, _ = Platform.objects.get_or_create(code="linkedin", defaults={"name": "LinkedIn"})

    def connection(self, **kwargs):
        return PlatformConnection.objects.create(user=self.user, platform=self.platform,
            access_token="private-token", scopes=list(li.SCOPES), is_active=True, status="active",
            token_expiry=timezone.now()+timedelta(hours=1),
            extra_data={"source": "ads_oauth", "linkedin_client_id": "li-client"}, **kwargs)

    def account(self, connection=None):
        return PlatformAccount.objects.create(user=self.user, platform=self.platform,
            connection=connection or self.connection(), account_id="123", account_name="LinkedIn test",
            is_active=True, access_token="private-token", extra_data={"currency": "TRY", "timezone": "UTC"})

    @override_settings(LINKEDIN_ADS_APPROVED=False)
    @patch.object(li, "_request")
    def test_pending_approval_blocks_oauth_without_provider_request(self, request):
        result = self.client.post(reverse("integration_connect", args=["linkedin"]))
        self.assertRedirects(result, reverse("platform_connections"), fetch_redirect_response=False)
        request.assert_not_called()
        self.assertNotIn("ads_oauth:linkedin", self.client.session)

    def test_oauth_requests_only_read_permissions_and_unpredictable_state(self):
        url = reverse("integration_connect", args=["linkedin"])
        self.assertEqual(self.client.get(url).status_code, 405)
        result = self.client.post(url)
        parsed = urlparse(result.url)
        self.assertEqual(parsed.netloc, "www.linkedin.com")
        query = parse_qs(parsed.query)
        self.assertEqual(query["scope"], ["r_ads r_ads_reporting"])
        self.assertGreater(len(query["state"][0]), 30)
        self.assertNotIn("private-secret", result.url)

    @patch.object(li, "_request")
    def test_callback_rejects_wrong_or_replayed_state_without_token_request(self, request):
        self.client.post(reverse("integration_connect", args=["linkedin"]))
        state = self.client.session["ads_oauth:linkedin"]["state"]
        callback = reverse("linkedin_ads_callback")
        self.client.get(callback, {"state": "wrong", "code": "secret-code"})
        self.client.get(callback, {"state": state, "code": "secret-code"})
        request.assert_not_called()
        self.assertFalse(PlatformConnection.objects.filter(user=self.user).exists())

    @patch.object(li, "read")
    @patch.object(li, "_request")
    def test_callback_selection_and_shared_report_keep_owner_and_client_binding(self, request, read):
        request.return_value = {"access_token": "private-token", "expires_in": 3600,
                                "scope": "r_ads,r_ads_reporting"}
        read.side_effect = [
            {"elements": [{"account": "urn:li:sponsoredAccount:123", "role": "VIEWER"}]},
            {"id": 123, "name": "Test account", "status": "ACTIVE", "currency": "TRY"},
        ]
        self.client.post(reverse("integration_connect", args=["linkedin"]))
        state = self.client.session["ads_oauth:linkedin"]["state"]
        result = self.client.get(reverse("linkedin_ads_callback"), {"state": state, "code": "private-code"})
        self.assertRedirects(result, reverse("integration_select", args=["linkedin"]), fetch_redirect_response=False)
        pending = PlatformConnection.objects.get(user=self.user)
        self.assertFalse(pending.is_active)
        selection = reverse("integration_select", args=["linkedin"])
        self.client.post(selection, {"accounts": ["999"]})
        self.assertFalse(PlatformAccount.objects.filter(user=self.user).exists())
        self.client.post(selection, {"accounts": ["123"]})
        pending.refresh_from_db()
        self.assertEqual(li.connection_token(pending), "private-token")
        account = PlatformAccount.objects.get(user=self.user)
        read.side_effect = [{"elements": [{"account": "urn:li:sponsoredAccount:123", "id": 7,
                                          "name": "Campaign", "status": "ACTIVE"}]},
                            {"elements": [{"pivotValues": ["urn:li:sponsoredCampaign:7"],
                                           "impressions": 100, "clicks": 5, "costInLocalCurrency": "25.50"}]}]
        report = reverse("integration_campaigns", args=[account.pk])
        response = self.client.get(report)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["summary"]["spend"], Decimal("25.50"))
        self.assertNotContains(response, "private-token")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(report).status_code, 404)

    @patch.object(li, "_request")
    def test_exchange_rejects_profile_only_scope_and_invalid_lifetime(self, request):
        for scope, expires in (("openid profile", 3600), ("r_ads r_ads_reporting", 0), (None, 3600)):
            request.return_value = {"access_token": "private-token", "scope": scope, "expires_in": expires}
            with self.subTest(scope=scope, expires=expires), self.assertRaises(api.IntegrationError):
                li.exchange_code("private-code")

    def test_saved_settings_validate_exact_callback_and_hide_secret(self):
        from core.integration_admin import IntegrationApplicationForm
        app = IntegrationApplication(provider="linkedin", client_id="saved-client", client_secret="saved-secret",
            redirect_uri="https://www.reklamanaliz.net/connect/linkedin/callback/", enabled=True)
        app.full_clean()
        app.save()
        self.assertEqual(api.configuration("linkedin")[0], "saved-client")
        self.assertNotIn("saved-secret", str(IntegrationApplicationForm(instance=app)["client_secret"]))
        app.redirect_uri = "https://www.reklamanaliz.net/accounts/linkedin_oauth2/login/callback/"
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            app.full_clean()

    def test_expired_changed_app_or_disconnected_grant_requires_reauthorization(self):
        connection = self.connection()
        for field, value in (("token_expiry", timezone.now()-timedelta(seconds=1)),
                             ("status", "disconnected"), ("scopes", ["r_ads"]),
                             ("extra_data", {"source": "ads_oauth", "linkedin_client_id": "old"})):
            original = getattr(connection, field)
            setattr(connection, field, value)
            with self.subTest(field=field), self.assertRaises(api.IntegrationError):
                li.connection_token(connection)
            setattr(connection, field, original)

    @patch.object(li, "read")
    def test_account_membership_pagination_never_follows_external_next_url(self, read):
        read.side_effect = [
            {"elements": [{"account": "urn:li:sponsoredAccount:123"}],
             "paging": {"links": [{"rel": "next", "href": "https://evil.invalid"}], "total": 2}},
            {"elements": [{"account": "urn:li:sponsoredAccount:456"}], "paging": {"total": 2}},
            {"id": 123, "status": "ACTIVE", "currency": "TRY"},
            {"id": 456, "status": "CANCELED"},
        ]
        self.assertEqual([r["id"] for r in li.discover_accounts("private")], ["123"])
        self.assertEqual(read.call_args_list[1].args[2]["start"], 1)
        self.assertTrue(all("evil" not in call.args[1] for call in read.call_args_list))

    @patch.object(li, "read")
    def test_repeated_campaign_cursor_fails_instead_of_looping(self, read):
        read.return_value = {"elements": [], "metadata": {"nextPageToken": "same"}}
        with self.assertRaises(api.IntegrationError):
            li.campaigns("private", "123")
        self.assertEqual(read.call_count, 2)

    @patch.object(li, "read")
    def test_daily_reporting_chunks_dates_and_preserves_decimal_spend(self, read):
        read.side_effect = [
            {"id": 7, "account": "urn:li:sponsoredAccount:123"},
            {"elements": [{"pivotValues": ["urn:li:sponsoredCampaign:7"],
                           "dateRange": {"start": {"year": 2026, "month": 1, "day": 31}},
                           "impressions": 100, "clicks": 2, "costInLocalCurrency": "0.10"}]},
            {"elements": []},
        ]
        rows = li.campaign_performance("private", "123", "7", date(2026, 1, 1), date(2026, 2, 2))
        self.assertEqual(rows[0]["spend"], Decimal("0.10"))
        self.assertEqual(read.call_count, 3)
        self.assertIn("month:2,day:1", read.call_args_list[-1].args[2]["dateRange"])

    @patch.object(li, "read")
    def test_campaign_from_different_account_is_rejected(self, read):
        read.return_value = {"id": 7, "account": "urn:li:sponsoredAccount:999"}
        with self.assertRaises(api.IntegrationError):
            li.campaign_performance("private", "123", "7", date(2026, 1, 1), date(2026, 1, 2))
        self.assertEqual(read.call_count, 1)

    @patch("core.services.linkedin_ads.requests.request")
    def test_provider_errors_and_transport_never_echo_secrets(self, request):
        response = Mock(ok=False, status_code=403, is_redirect=False)
        response.json.return_value = {"message": "private-token private-secret private-code"}
        request.return_value = response
        with self.assertRaises(api.IntegrationError) as exc:
            li.read("private-token", "adAccountUsers")
        self.assertNotIn("private", str(exc.exception))
        self.assertFalse(request.call_args.kwargs["allow_redirects"])
        request.side_effect = requests.Timeout("private-secret")
        with self.assertRaises(api.IntegrationError) as exc:
            li.read("private-token", "adAccountUsers")
        self.assertNotIn("private", str(exc.exception))

    def test_legacy_manual_profile_token_cannot_be_added_as_ads_account(self):
        self.client.post(reverse("hesap_ekle"), {"platform": "linkedin", "access_token": "private"})
        self.assertFalse(PlatformAccount.objects.filter(user=self.user).exists())

    @override_settings(LINKEDIN_ADS_APPROVED=False)
    def test_admin_status_distinguishes_pending_approval_from_working_setup(self):
        from django.contrib import admin
        app = IntegrationApplication(provider="linkedin", client_id="id", client_secret="private")
        self.assertIn("onayı bekleniyor", admin.site._registry[IntegrationApplication].configuration_status(app))

    @patch.object(li, "read")
    def test_campaign_cursor_collects_all_pages(self, read):
        read.side_effect = [
            {"elements": [{"account": "urn:li:sponsoredAccount:123", "id": 7, "name": "A"}],
             "metadata": {"nextPageToken": "page-two"}},
            {"elements": [{"account": "urn:li:sponsoredAccount:123", "id": 8, "name": "B"}]},
        ]
        self.assertEqual([r["id"] for r in li.campaigns("private", "123")], ["7", "8"])
        self.assertEqual(read.call_args.args[2]["pageToken"], "page-two")

    @patch.object(li, "read")
    def test_wrong_campaign_pivot_and_nonfinite_spend_fail_closed(self, read):
        for pivots, spend in ((["urn:li:person:7"], "1"), (["urn:li:sponsoredCampaign:7"], "NaN")):
            read.return_value = {"elements": [{"pivotValues": pivots, "costInLocalCurrency": spend}]}
            with self.subTest(pivots=pivots, spend=spend), self.assertRaises(api.IntegrationError):
                li.campaign_summaries("private", "123", date(2026, 1, 1), date(2026, 1, 2))

    def test_cross_owner_connection_cannot_be_used_for_report(self):
        connection = self.connection()
        connection.user = self.other
        connection.save()
        account = self.account(connection)
        with patch.object(li, "read") as read, self.assertRaises(api.IntegrationError):
            api.campaigns(account)
        read.assert_not_called()
