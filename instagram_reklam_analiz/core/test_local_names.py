from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.models import User, Platform, PlatformAccount, Campaign, Ad, Organization, AgencyClient, OrganizationMember


class LocalNameTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="names-owner")
        self.other = User.objects.create_user(username="names-other")
        self.client.force_login(self.user)
        platform, _ = Platform.objects.get_or_create(code="facebook", defaults={"name": "Facebook"})
        self.account = PlatformAccount.objects.create(user=self.user, platform=platform, account_id="act_123", account_name="Source", access_token="test")

    def test_account_alias_is_unicode_and_survives_source_refresh(self):
        response = self.client.post(reverse("local_name_update", args=["account", self.account.pk]), {"name": "Çığ Şirketi – İstanbul"})
        self.assertEqual(response.status_code, 302)
        PlatformAccount.objects.filter(pk=self.account.pk).update(account_name="Refreshed source")
        self.account.refresh_from_db()
        self.assertEqual(self.account.display_name, "Çığ Şirketi – İstanbul")
        self.assertEqual(self.account.account_name, "Refreshed source")
        self.client.post(reverse("local_name_update", args=["account", self.account.pk]), {"name": ""})
        self.account.refresh_from_db()
        self.assertEqual(self.account.display_name, "Refreshed source")

    def test_other_user_cannot_rename(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("local_name_update", args=["account", self.account.pk]), {"name": "No"}).status_code, 404)

    def test_too_long_name_is_rejected(self):
        response = self.client.post(reverse("local_name_update", args=["account", self.account.pk]), {"name": "a" * 201})
        self.assertContains(response, "Ad çok uzun")
        self.account.refresh_from_db()
        self.assertEqual(self.account.local_name, "")

    def test_campaign_and_ad_rename(self):
        campaign = Campaign.objects.create(user=self.user, platform_account=self.account, platform_campaign_id="c1", name="Original")
        ad = Ad.objects.create(user=self.user, platform_account=self.account, campaign=campaign, name="Original ad")
        for kind, obj in [("campaign", campaign), ("ad", ad)]:
            with self.subTest(kind=kind):
                response = self.client.post(reverse("local_name_update", args=[kind, obj.pk]), {"name": "Yeni Türkçe Ad"})
                self.assertEqual(response.status_code, 302)
                obj.refresh_from_db()
                self.assertEqual(obj.display_name, "Yeni Türkçe Ad")
                self.assertTrue(obj.name.startswith("Original"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.extra_data["campaign_names"]["c1"], "Yeni Türkçe Ad")

    @patch("core.services.ads_integrations.campaigns", return_value=[{"id": "c1", "name": "Source"}])
    def test_remote_alias_preserves_account_metadata(self, campaigns):
        self.account.extra_data = {"currency": "TRY", "source": "ads_oauth"}
        self.account.save(update_fields=["extra_data"])
        url = reverse("remote_campaign_name_update", args=[self.account.pk, "c1"])
        self.assertEqual(self.client.post(url, {"name": "Yaz Kampanyası"}).status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.extra_data["currency"], "TRY")
        self.assertEqual(self.account.extra_data["campaign_names"]["c1"], "Yaz Kampanyası")

    def test_readonly_agency_member_cannot_rename(self):
        organization = Organization.objects.create(owner=self.user, name="Agency")
        brand = AgencyClient.objects.create(organization=organization, name="Brand")
        self.account.agency_client = brand
        self.account.save(update_fields=["agency_client"])
        OrganizationMember.objects.create(organization=organization, user=self.other, role="viewer", is_active=True)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("local_name_update", args=["account", self.account.pk]), {"name": "No"}).status_code, 403)
