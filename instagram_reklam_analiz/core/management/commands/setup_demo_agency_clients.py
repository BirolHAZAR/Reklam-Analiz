from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.management.commands.refresh_demo_agency_history import (
    METRIC_UPDATE_FIELDS,
    Command as HistoryCommand,
)
from core.models import (
    Ad,
    AdGroup,
    AdMetricHistory,
    AgencyClient,
    Campaign,

    Creative,
    Organization,
    Platform,
    PlatformAccount,
    PlatformConnection,
)
from core.services.cache_service import CacheService, DashboardCacheManager


PLATFORMS = (
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("google_ads", "Google Ads"),
    ("tiktok", "TikTok"),
    ("linkedin", "LinkedIn"),
    ("x", "X"),
    ("youtube", "YouTube"),
)


class Command(BaseCommand):
    help = "Demo Ajans altında iki ayrı müşteri ve tamamen ayrıştırılmış raporlama verisi hazırlar."

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username="demo", is_active=True).first()
        if not user:
            raise CommandError("Aktif demo kullanıcısı bulunamadı.")
        organization = Organization.objects.filter(owner=user, is_active=True).order_by("id").first()
        if not organization:
            raise CommandError("Demo Ajans organizasyonu bulunamadı.")

        now = timezone.now()
        with transaction.atomic():
            client_1 = AgencyClient.objects.get(organization=organization, name="Demo Marka")
            client_2, _ = AgencyClient.objects.update_or_create(
                organization=organization,
                name="Demo Marka 2",
                defaults={
                    "legal_name": "Demo Marka 2 Ticaret A.Ş.",
                    "website": "https://demo2.reklamanaliz.net",
                    "contact_name": "Demo Marka 2 Ekibi",
                    "contact_email": "marka2@demo.reklamanaliz.net",
                    "notes": "Ajans firma filtresi ve rapor doğrulaması için ikinci sentetik müşteri.",
                    "is_active": True,
                },
            )
            accounts_2 = self._create_client_two_data(user, client_2, now)

        # Her müşteri kendi kalıcı hesap işaretine göre ayrı ayrı yenilenir.
        call_command("refresh_demo_agency_history", username="demo", client_name="Demo Marka", days=90)
        call_command("refresh_demo_agency_history", username="demo", client_name="Demo Marka 2", days=90)

        DashboardCacheManager.invalidate_user_dashboard(user.id)
        for namespace in (
            "control_tower",
        ):
            CacheService.bump_version(namespace, user.id)

        self.stdout.write(
            self.style.SUCCESS(
                "Demo ajans müşteri ayrımı hazır: Demo Marka ve Demo Marka 2; "
                "müşteri 2 için 7 hesap / 14 kampanya / 28 reklam."
            )
        )

    def _create_client_two_data(self, user, client, now):
        accounts = {}
        campaign_labels = ((1, "Büyüme"), (2, "Yeniden Pazarlama"))
        for platform_code, platform_label in PLATFORMS:
            platform = Platform.objects.get(code=platform_code)
            connection, _ = PlatformConnection.objects.update_or_create(
                user=user,
                platform=platform,
                name=f"Demo Marka 2 {platform_label} Bağlantısı",
                defaults={
                    "access_token": "demo-marka2-token",
                    "refresh_token": "demo-marka2-refresh",
                    "token_expiry": now + timedelta(days=365),
                    "scopes": ["read", "ads_read", "analytics"],
                    "status": "active",
                    "last_sync": now,
                    "extra_data": {"demo": True, "demo_agency_client": client.name},
                    "is_active": True,
                },
            )
            account, _ = PlatformAccount.objects.update_or_create(
                user=user,
                platform=platform,
                account_id=f"demo-marka2-{platform_code}-01",
                defaults={
                    "connection": connection,
                    "agency_client": client,
                    "account_name": f"Demo Marka 2 · {platform_label} Hesabı",
                    "access_token": "demo-marka2-token",
                    "refresh_token": "demo-marka2-refresh",
                    "token_expiry": now + timedelta(days=365),
                    "is_active": True,
                    "last_sync": now,
                    "extra_data": {"demo": True, "demo_agency_client": client.name},
                },
            )
            accounts[platform_code] = account

            for campaign_no, campaign_label in campaign_labels:
                campaign_id = f"{account.account_id}-cmp-{campaign_no}"
                campaign, _ = Campaign.objects.update_or_create(
                    platform_account=account,
                    platform_campaign_id=campaign_id,
                    defaults={
                        "user": user,
                        "platform_connection": connection,
                        "name": f"Demo Marka 2 · {platform_label} {campaign_label}",
                        "objective": "SALES" if campaign_no == 1 else "TRAFFIC",
                        "status": "ACTIVE",
                        "daily_budget": Decimal("1450.00") + Decimal(campaign_no * 250),
                        "currency": "TRY",
                        "start_time": now - timedelta(days=89),
                        "last_synced_at": now,
                        "is_active": True,
                        "raw_data": {
                            "demo": True,
                            "demo_agency_client": client.name,
                            "demo_agency_history": True,
                        },
                    },
                )
                ad_group, _ = AdGroup.objects.update_or_create(
                    campaign=campaign,
                    platform_adgroup_id=f"{campaign_id}-grp-1",
                    defaults={
                        "user": user,
                        "name": f"{campaign_label} Hedef Kitle",
                        "status": "ACTIVE",
                        "optimization_goal": "CONVERSIONS",
                        "billing_event": "IMPRESSIONS",
                        "daily_budget": campaign.daily_budget,
                        "targeting": {"age": "24-44", "locations": ["TR"], "client": client.name},
                        "placements": {"feed": True, "story": True, "search": platform_code in {"google_ads", "youtube"}},
                        "start_time": campaign.start_time,
                        "last_synced_at": now,
                        "is_active": True,
                        "raw_data": {"demo": True, "demo_agency_client": client.name},
                    },
                )
                for ad_no in (1, 2):
                    creative_id = f"{campaign_id}-creative-{ad_no}"
                    creative, _ = Creative.objects.update_or_create(
                        user=user,
                        platform_account=account,
                        platform_creative_id=creative_id,
                        defaults={
                            "platform_connection": connection,
                            "creative_type": "VIDEO" if ad_no == 2 else "IMAGE",
                            "name": f"Demo Marka 2 {platform_label} Kreatif {campaign_no}-{ad_no}",
                            "title": "Yeni Sezon Fırsatları" if ad_no == 1 else "Bugüne Özel Avantaj",
                            "body_text": "Demo Marka 2 için satış ve büyüme odaklı sentetik reklam kreatifi.",
                            "call_to_action": "SHOP_NOW",
                            "image_url": f"https://picsum.photos/seed/marka2-{platform_code}-{campaign_no}-{ad_no}/900/900",
                            "landing_url": "https://demo2.reklamanaliz.net/kampanya",
                            "media_hash": creative_id,
                            "raw_data": {"demo": True, "demo_agency_client": client.name},
                            "first_seen_at": now - timedelta(days=89),
                            "last_seen_at": now,
                        },
                    )
                    Ad.objects.update_or_create(
                        user=user,
                        platform_account=account,
                        platform_ad_id=f"{campaign_id}-ad-{ad_no}",
                        defaults={
                            "source_type": "OWN",
                            "platform_connection": connection,
                            "campaign": campaign,
                            "ad_group": ad_group,
                            "creative": creative,
                            "name": f"Demo Marka 2 · {platform_label} Reklam {campaign_no}-{ad_no}",
                            "status": "ACTIVE",
                            "ad_format": creative.creative_type,
                            "objective": campaign.objective,
                            "headline": creative.title,
                            "primary_text": creative.body_text,
                            "call_to_action": creative.call_to_action,
                            "landing_url": creative.landing_url,
                            "preview_image_url": creative.image_url,
                            "first_seen_at": now - timedelta(days=89),
                            "last_seen_at": now,
                            "started_at": now - timedelta(days=89),
                            "last_synced_at": now,
                            "raw_data": {
                                "demo": True,
                                "demo_agency_client": client.name,
                                "demo_agency_history": True,
                            },
                        },
                    )
        return accounts
