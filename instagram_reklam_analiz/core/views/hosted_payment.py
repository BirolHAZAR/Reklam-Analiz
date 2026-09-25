from decimal import InvalidOperation
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from core.models import HostedPaymentSession
from core.services import hosted_gateway
from core.services.hosted_payment import complete_card_payment


@csrf_exempt
@never_cache
@sensitive_post_parameters()
@require_POST
def hosted_payment_callback(request, session_id):
    session = get_object_or_404(HostedPaymentSession.objects.select_related("payment", "payment__billing_info"), pk=session_id)
    try:
        verified = hosted_gateway.verify(session, request.POST)
        complete_card_payment(session.pk, verified)
    except (hosted_gateway.GatewayError, InvalidOperation, UnicodeError, ValueError):
        return render(request, "payment/gateway_result.html", {"message": "Ödeme doğrulanamadı veya incelemesi sürüyor. Hesap hareketlerinizi kontrol edin; tutar çekildiyse tekrar ödeme yapmadan destek ekibine ulaşın."}, status=400)
    return render(request, "payment/gateway_result.html", {"success": True, "message": "Ödemeniz doğrulandı ve satın aldığınız haklar hesabınıza tanımlandı."})
