from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import BillingInfo, Invoice, Payment, PaymentTransaction, UserSubscription
from core.services.entitlements import grant_plan_ai_credits


def renewal_period_delta(subscription):
    if subscription.billing_period == UserSubscription.BILLING_YEARLY:
        return timedelta(days=365)
    return timedelta(days=30)


def renewal_base_amount(subscription):
    plan = subscription.plan
    if subscription.billing_period == UserSubscription.BILLING_YEARLY:
        return plan.yearly_price
    return plan.price


def due_auto_renewal_subscriptions(today=None):
    today = today or timezone.localdate()
    return (
        UserSubscription.objects
        .select_related("user", "plan", "organization", "default_payment_method")
        .filter(
            is_active=True,
            auto_renew=True,
            next_renewal_date__lte=today,
            plan__isnull=False,
            default_payment_method__isnull=False,
            default_payment_method__is_active=True,
        )
    )


def renew_subscription(subscription):
    # Hosted one-off checkout has no recurring mandate. Never simulate a charge.
    return {"success": False, "reason": "recurring_provider_not_configured", "subscription_id": subscription.id}


def process_due_auto_renewals(limit=100):
    results = []
    for subscription in due_auto_renewal_subscriptions()[:limit]:
        try:
            results.append(renew_subscription(subscription))
        except Exception as exc:
            results.append({"success": False, "subscription_id": subscription.id, "reason": str(exc)})
    return results
