from django.urls import path
from core.views.hosted_payment import hosted_payment_callback
from core.views import payment, platform_connect
from core.views.hesap_ekle import hesap_ekle_view, hesap_sil
from core.views import platform_connect
from core.views import ads_integrations
from core.views import local_names
from core.views import instagram_oauth

urlpatterns = [
    path('connect/youtube/callback/', ads_integrations.callback, {'provider': 'youtube'}, name='youtube_callback'),
    path('connect/instagram/', instagram_oauth.connect, name='instagram_connect'),
    path('connect/instagram/callback/', instagram_oauth.callback, name='instagram_oauth_callback'),
    path('names/<str:kind>/<int:object_id>/', local_names.rename, name='local_name_update'),
    path('names/accounts/<int:account_id>/campaigns/<str:campaign_id>/', local_names.rename_remote_campaign, name='remote_campaign_name_update'),
    path('integrations/', ads_integrations.integrations, name='integrations'),
    path('integrations/<str:provider>/connect/', ads_integrations.connect, name='integration_connect'),
    path('integrations/<str:provider>/accounts/', ads_integrations.select_accounts, name='integration_select'),
    path('integrations/accounts/<int:account_id>/campaigns/', ads_integrations.account_campaigns, name='integration_campaigns'),
    path('integrations/accounts/<int:account_id>/campaigns/<str:campaign_id>/', ads_integrations.account_campaigns, name='integration_campaign_detail'),
    path('connect/google-ads/callback/', ads_integrations.callback, {'provider': 'google_ads'}, name='google_ads_callback'),
    path("payment/pos/callback/<uuid:session_id>/", hosted_payment_callback, name="hosted_payment_callback"),
    path(
        "platform-connections/",
        platform_connect.platform_connections,
        name="platform_connections"
    ),



    path('pricing/', payment.pricing_view, name='pricing'),
    path('checkout/<int:plan_id>/', payment.checkout, name='checkout'),
    path('checkout/ai-kredi/<int:package_id>/', payment.credit_checkout, name='credit_checkout'),
    path('checkout/urun-arastirma/<int:package_id>/', payment.product_research_checkout, name='product_research_checkout'),
    path('payment/success/', payment.payment_success, name='payment_success'),
    path('account/', payment.my_account, name='my_account'),
    path('account/subscriptions/', payment.my_subscriptions, name='my_subscriptions'),
    path('account/invoices/', payment.my_invoices, name='my_invoices'),
    path('account/payments/', payment.my_payments, name='my_payments'),
    path('account/invoices/<int:invoice_id>/pdf/', payment.invoice_pdf, name='invoice_pdf'),
    path('account/invoices/<int:invoice_id>/', payment.invoice_detail, name='invoice_detail'),
    path('hesap-ekle/', hesap_ekle_view, name='hesap_ekle'),
    path('hesap-sil/<int:account_id>/', hesap_sil, name='hesap_sil'),
    path('platform-connections/accounts/<int:account_id>/update/', platform_connect.platform_account_update, name='platform_account_update'),
    path('platform-connections/accounts/<int:account_id>/delete/', platform_connect.platform_account_delete, name='platform_account_delete'),
    path('connect/facebook/', platform_connect.facebook_login, name='facebook_login'),
    path('connect/facebook/callback/', ads_integrations.callback, {'provider': 'facebook'}, name='facebook_callback'),
]
