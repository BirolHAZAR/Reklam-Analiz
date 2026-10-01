from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import AgencyClient, MembershipPlan, Organization, Platform, PlatformAccount, User, UserSubscription
from core.services.plan_limits import ensure_platform_account_capacity


class TotalPlatformAccountLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="platform-limit", email="limit@example.com", password="test")
        self.user.subscriptions.all().delete()
        self.plan = MembershipPlan.objects.create(
            name="platform-limit-plan", display_name="Limit", price=100, price_with_kdv=120,
            features="Limit", max_instagram_accounts=3,
        )
        UserSubscription.objects.create(
            user=self.user, plan=self.plan, start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30), is_active=True,
        )
        self.instagram = Platform.objects.create(name="Instagram Limit", code="instagram-limit")
        self.facebook = Platform.objects.create(name="Facebook Limit", code="facebook-limit")

    def add_account(self, platform, account_id):
        return PlatformAccount.objects.create(
            user=self.user, platform=platform, account_id=account_id,
            account_name=account_id, access_token="token", is_active=True,
        )

    def test_limit_counts_all_platforms_together(self):
        self.add_account(self.instagram, "ig-1")
        self.add_account(self.facebook, "fb-1")
        self.add_account(self.facebook, "fb-2")
        with self.assertRaisesMessage(ValueError, "toplam 3 platform hesabına"):
            ensure_platform_account_capacity(self.user, [(self.instagram.code, "ig-2")])

    def test_existing_account_update_does_not_consume_another_slot(self):
        self.add_account(self.instagram, "ig-1")
        self.assertTrue(ensure_platform_account_capacity(self.user, [(self.instagram.code, "ig-1")]))

    def test_agency_plan_allows_connection_without_personal_subscription(self):
        self.user.subscriptions.update(end_date=timezone.localdate() - timedelta(days=1))
        organization = Organization.objects.create(owner=self.user, name="Agency", active_plan=self.plan)
        self.assertTrue(ensure_platform_account_capacity(
            self.user, [(self.facebook.code, "fb-1")], organization=organization,
        ))

    def test_agency_without_plan_cannot_use_personal_subscription(self):
        organization = Organization.objects.create(owner=self.user, name="Agency")
        with self.assertRaisesMessage(ValueError, "Aktif deneme veya abonelik"):
            ensure_platform_account_capacity(self.user, [(self.facebook.code, "fb-1")], organization=organization)

    def test_inactive_agency_or_plan_cannot_connect(self):
        organization = Organization.objects.create(owner=self.user, name="Agency", active_plan=self.plan)
        for organization_active, plan_active in [(False, True), (True, False)]:
            with self.subTest(organization_active=organization_active, plan_active=plan_active):
                organization.is_active = organization_active
                organization.active_plan.is_active = plan_active
                with self.assertRaisesMessage(ValueError, "Aktif deneme veya abonelik"):
                    ensure_platform_account_capacity(self.user, [(self.facebook.code, "fb-1")], organization=organization)

    def test_agency_limit_counts_accounts_across_clients_and_users(self):
        organization = Organization.objects.create(owner=self.user, name="Agency", active_plan=self.plan)
        other = User.objects.create_user(username="agency-colleague")
        for index in range(3):
            client = AgencyClient.objects.create(organization=organization, name=f"Brand {index}")
            PlatformAccount.objects.create(user=other, platform=self.facebook, agency_client=client,
                account_id=f"fb-{index}", account_name="Account", access_token="token", is_active=True)
        with self.assertRaisesMessage(ValueError, "toplam 3 platform hesabına"):
            ensure_platform_account_capacity(self.user, [(self.instagram.code, "new")], organization=organization)
