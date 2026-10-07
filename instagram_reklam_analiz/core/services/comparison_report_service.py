from django.db.models import Sum
from core.models import Ad, AdMetricHistory


class ComparisonReportService:
    def __init__(self, user):
        self.user = user

    def ad_history(self, ad_id):
        return AdMetricHistory.objects.filter(ad_id=ad_id, ad__user=self.user, ad__source_type="OWN").order_by("date")
