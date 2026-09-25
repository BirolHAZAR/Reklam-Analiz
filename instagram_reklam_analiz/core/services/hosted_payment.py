import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import (AICreditLedger, HostedPaymentSession, Invoice, MembershipPlan, Organization, OrganizationMember, Payment, PaymentGatewaySettings, PaymentTransaction, ReferralReward, UserSubscription)
from core.services.entitlements import add_ai_credits, grant_plan_ai_credits
from core.services.product_research_credits import add_product_research_units
from core.services.legal_documents import record_purchase_acceptance, queue_purchase_legal_email
from core.services.referrals import record_pending_referral, award_referral_for_subscription
from core.services import hosted_gateway


def start_card_payment(request, form, *, plan=None, package=None, kind="subscription", billing_period="monthly", amount, kdv_amount, referral_code="", referral_benefits=None):
    gateway = PaymentGatewaySettings.load()
    if not gateway.available_for(request.user):
        return render(request, "payment/gateway_result.html", {"message": "Kart ödemesi şu anda kullanıma açık değil. Havale seçeneğini veya destek kanalını kullanabilirsiniz."}, status=503)
    from core.views.payment import _get_or_create_billing_info
    with transaction.atomic():
        bill = _get_or_create_billing_info(request.user, form.cleaned_data)
        payment = Payment.objects.create(user=request.user, plan=plan, billing_info=bill, amount=amount, kdv_amount=kdv_amount,
                                         billing_period=billing_period, payment_method="credit_card", status="pending",
                                         ai_credit_package=package if kind == "ai_credit" else None,
                                         product_research_package=package if kind == "product_research" else None)
        record_purchase_acceptance(request, payment, immediate_service_consent=form.cleaned_data["immediate_service_consent"])
        session = HostedPaymentSession.objects.create(payment=payment, provider=gateway.provider, configuration=json.dumps(hosted_gateway.configuration(gateway)),
            purchase_data={"ip": request.META.get("REMOTE_ADDR", ""), "label": payment.purchase_label,
                           "units": int(package.credits if kind == "ai_credit" else package.units) if package else 0,
                           "agency_name": request.POST.get("agency_name", "").strip() or bill.company_name})
        if referral_code:
            benefits = referral_benefits or {}
            record_pending_referral(code=referral_code, referred_user=request.user, payment=payment,
                reward_type=benefits.get("reward_type"), reward_amount=benefits.get("reward_amount"), note="Sanal POS doğrulaması bekleniyor.")
    try:
        result = hosted_gateway.initialize(session)
    except hosted_gateway.GatewayError:
        # Keep pending on network ambiguity; do not create another charge automatically.
        return render(request, "payment/gateway_result.html", {"message": "Ödeme sayfası şu anda açılamadı. Yeniden denemeden önce hesap hareketlerinizi kontrol edin veya destek ekibine ulaşın."}, status=502)
    request.session.pop("checkout_referral_code", None)
    if "redirect" in result:
        return redirect(result["redirect"])
    return render(request, "payment/gateway_redirect.html", result)


@transaction.atomic
def complete_card_payment(session_id, verified_result):
    session = HostedPaymentSession.objects.select_for_update().select_related("payment").get(pk=session_id)
    payment = Payment.objects.select_for_update().get(pk=session.payment_id)
    if session.verified:
        return payment
    if payment.payment_method != "credit_card" or payment.status != "pending":
        raise hosted_gateway.GatewayError("Sipariş aktivasyona uygun değil.")
    # Serialize entitlement updates across different orders for the same user.
    get_user_model().objects.select_for_update().get(pk=payment.user_id)
    today = timezone.localdate()
    subscription = None
    if payment.plan_id:
        plan = payment.plan
        organization = None
        if plan.plan_type == MembershipPlan.PLAN_TYPE_AGENCY:
            name = session.purchase_data.get("agency_name") or f"{payment.user.email} Ajansı"
            organization, _ = Organization.objects.update_or_create(owner=payment.user, name=name, defaults={"active_plan": plan, "is_active": True, "report_brand_name": name})
            OrganizationMember.objects.update_or_create(organization=organization, user=payment.user, defaults={"role": OrganizationMember.ROLE_OWNER, "is_active": True, "invited_email": payment.user.email})
        duration = 365 if payment.billing_period == "yearly" else 30
        subscription, _ = UserSubscription.objects.update_or_create(user=payment.user, organization=organization, defaults={"plan": plan, "start_date": today, "end_date": today + timedelta(days=duration), "billing_period": payment.billing_period,
            "auto_renew": False, "default_payment_method": None, "next_renewal_date": today + timedelta(days=duration), "is_active": True})
        grant_plan_ai_credits(subscription)
    elif payment.ai_credit_package_id:
        add_ai_credits(user=payment.user, amount=session.purchase_data["units"], action=AICreditLedger.ACTION_PURCHASE, package=payment.ai_credit_package, reference=f"pos-ai:{payment.pk}", note="Doğrulanmış kart ödemesi")
    elif payment.product_research_package_id:
        add_product_research_units(user=payment.user, amount=session.purchase_data["units"], package=payment.product_research_package, reference=f"pos-research:{payment.pk}", note="Doğrulanmış kart ödemesi")
    else:
        raise hosted_gateway.GatewayError("Sipariş ürünü bulunamadı.")
    payment.status = "completed"
    payment.transaction_id = verified_result["reference"]
    payment.save(update_fields=["status", "transaction_id", "updated_at"])
    Invoice.objects.create(user=payment.user, subscription=subscription, billing_info=payment.billing_info,
        invoice_number=f"INV-{timezone.now():%Y%m%d}-{payment.user_id}-{payment.pk}", amount=payment.amount - payment.kdv_amount, kdv_amount=payment.kdv_amount, total_amount=payment.amount,
        payment_method="credit_card", is_paid=True, payment_date=timezone.now(), due_date=today, status="paid", description=session.purchase_data["label"])
    PaymentTransaction.objects.create(user=payment.user, payment=payment, transaction_type="payment", amount=payment.amount, status="success", reference_id=payment.transaction_id,
        response_data={"provider": session.provider, **verified_result}, notes="Ödeme kuruluşu tarafından doğrulandı.")
    pending_reward = ReferralReward.objects.filter(payment=payment).select_related("referral_code").first()
    if subscription and pending_reward:
        award_referral_for_subscription(code=pending_reward.referral_code.code, referred_user=payment.user, subscription=subscription, payment=payment, reward_type=pending_reward.reward_type, reward_amount=pending_reward.reward_amount)
    session.verified = True
    session.save(update_fields=["verified"])
    queue_purchase_legal_email(payment.legal_acceptance)
    return payment
