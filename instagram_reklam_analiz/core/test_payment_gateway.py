import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse

from core.admin import PaymentGatewaySettingsForm
from core.models import (AICreditLedger, AICreditPackage, BillingInfo, HostedPaymentSession, Invoice, LegalDocument, LegalSiteSettings, MembershipPlan, Payment, PaymentGatewaySettings, PaymentTransaction)
from core.services import hosted_gateway
from core.services.hosted_payment import complete_card_payment
from core.services.legal_documents import record_purchase_acceptance
from core.services.subscription_renewal import renew_subscription


@override_settings(SUBSCRIPTION_ACCESS_ENFORCED=False)
class PaymentGatewayTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="gateway-buyer", email="buyer@example.com", password="test")
        self.client.force_login(self.user)
        self.config = PaymentGatewaySettings.objects.create(enabled=True, sandbox=False, iyzico_api_key="test-key-only", iyzico_secret_key="test-secret-only")
        LegalDocument.objects.all().update(status="published")
        self.plan = MembershipPlan.objects.create(name="gateway-test", display_name="Gateway Plan", price=100, price_with_kdv=120, is_active=True)
        self.bill = BillingInfo.objects.create(user=self.user, first_name="Test", last_name="Buyer", email="buyer@example.com", phone="5551112233", tc_kimlik="11111111111", address="Test address", city="Istanbul", district="Test", zip_code="34000")

    def payload(self):
        return {"customer_type": "individual", "first_name": "Test", "last_name": "Buyer", "email": "buyer@example.com", "phone": "5551112233", "tc_kimlik": "11111111111", "address": "Test address", "city": "Istanbul", "district": "Test", "zip_code": "34000", "payment_method": "credit_card", "legal_acceptance": "on", "immediate_service_consent": "on"}

    def session(self, provider="iyzico"):
        payment = Payment.objects.create(user=self.user, plan=self.plan, billing_info=self.bill, amount=120, kdv_amount=20, payment_method="credit_card")
        config = hosted_gateway.configuration(self.config)
        config.update(garanti_merchant_id="1234567", garanti_terminal_id="12345678", garanti_store_key="test-store", garanti_prov_password="test-prov")
        session = HostedPaymentSession.objects.create(payment=payment, provider=provider, configuration=json.dumps(config), token="test-token", purchase_data={"ip": "127.0.0.1", "label": "Gateway Plan"})
        from django.test import RequestFactory
        request = RequestFactory().post("/checkout/")
        request.user = self.user
        record_purchase_acceptance(request, payment, immediate_service_consent=True)
        return session

    def signed_iyzico_result(self, session, **overrides):
        data = {"status": "success", "paymentStatus": "SUCCESS", "paymentId": "provider-123", "fraudStatus": 1, "currency": "TRY", "basketId": session.pk.hex, "conversationId": session.pk.hex, "price": 120.0, "paidPrice": 120.0, "token": "test-token"}
        data.update(overrides)
        values = [str(data[field]) for field in ("paymentStatus", "paymentId", "currency", "basketId", "conversationId")]
        values += [format(Decimal(str(data[field])).normalize(), "f") for field in ("paidPrice", "price")]
        values += [data["token"]]
        data["signature"] = hmac.new(b"test-secret-only", ":".join(values).encode(), hashlib.sha256).hexdigest()
        return data

    @patch("core.services.hosted_gateway.initialize", return_value={"redirect": "https://api.iyzipay.com/checkoutform/test"})
    def test_checkout_creates_pending_order_without_card_fields_or_entitlements(self, initialize):
        response = self.client.post(reverse("checkout", args=[self.plan.pk]), self.payload())
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(user=self.user)
        self.assertEqual(payment.status, "pending")
        self.assertFalse(Invoice.objects.filter(user=self.user).exists())
        self.assertFalse(PaymentTransaction.objects.filter(payment=payment).exists())
        response = self.client.get(reverse("checkout", args=[self.plan.pk]))
        self.assertNotContains(response, 'name="card_number"')
        self.assertNotContains(response, 'name="cvv"')
        self.assertContains(response, "iyzico-card-band.png")

    def test_unconfigured_or_sandbox_pos_cannot_complete_public_purchase(self):
        for enabled, sandbox in [(False, False), (True, True)]:
            self.config.enabled, self.config.sandbox = enabled, sandbox
            self.config.save()
            response = self.client.post(reverse("checkout", args=[self.plan.pk]), self.payload())
            self.assertEqual(response.status_code, 503)
            self.assertFalse(Payment.objects.filter(user=self.user).exists())

    @patch("core.services.hosted_gateway.iyzico_request")
    def test_verified_callback_is_idempotent_without_browser_session(self, api):
        session = self.session()
        api.return_value = self.signed_iyzico_result(session)
        self.client.logout()
        url = reverse("hosted_payment_callback", args=[session.pk])
        for _ in range(2):
            response = self.client.post(url, {"token": "test-token"})
            self.assertEqual(response.status_code, 200)
        session.payment.refresh_from_db()
        self.assertEqual(session.payment.status, "completed")
        self.assertEqual(PaymentTransaction.objects.filter(payment=session.payment).count(), 1)
        self.assertEqual(Invoice.objects.filter(user=self.user).count(), 1)
        self.assertFalse(self.user.subscriptions.get(plan=self.plan).auto_renew)

    @patch("core.services.hosted_gateway.iyzico_request")
    def test_bad_signature_wrong_amount_wrong_order_and_fraud_never_activate(self, api):
        for overrides in [{"paidPrice": 1}, {"basketId": "wrong"}, {"fraudStatus": 0}, {"currency": "USD"}, {"paymentStatus": "FAILURE"}]:
            session = self.session()
            api.return_value = self.signed_iyzico_result(session, **overrides)
            with self.assertRaises(hosted_gateway.GatewayError):
                hosted_gateway.verify_iyzico(session, json.loads(session.configuration), {"token": "test-token"})
            self.assertEqual(session.payment.status, "pending")
        session = self.session()
        data = self.signed_iyzico_result(session)
        data["signature"] = "forged"
        api.return_value = data
        response = self.client.post(reverse("hosted_payment_callback", args=[session.pk]), {"token": "test-token"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Invoice.objects.filter(user=self.user).exists())

    def test_garanti_rejects_unsigned_or_partial_signed_callback(self):
        session = self.session("garanti")
        config = json.loads(session.configuration)
        for values in [{}, {"hashparams": "oid:", "oid": session.pk.hex, "hash": hosted_gateway.garanti_hash(session.pk.hex + config["garanti_store_key"])}]:
            data = QueryDict("", mutable=True)
            data.update(values)
            with self.assertRaises(hosted_gateway.GatewayError):
                hosted_gateway.verify_garanti(session, config, data)

    @patch("core.services.hosted_gateway.requests.post")
    def test_garanti_checks_server_amount_after_signed_callback(self, post):
        session = self.session("garanti")
        config = json.loads(session.configuration)
        data = QueryDict("", mutable=True)
        fields = {"clientid": config["garanti_merchant_id"], "oid": session.pk.hex, "authcode": "AUTH1", "procreturncode": "00", "response": "Approved", "mdstatus": "1"}
        data.update(fields)
        data["hashparams"] = ":".join(fields) + ":"
        data["hash"] = hosted_gateway.garanti_hash("".join(fields.values()) + config["garanti_store_key"])
        def xml(amount):
            return f'<GVPSResponse><Terminal><ID>12345678</ID></Terminal><Order><OrderID>{session.pk.hex}</OrderID><OrderInqResult><Code>00</Code><AuthCode>AUTH1</AuthCode><AuthAmount>{amount}</AuthAmount><RetrefNum>REF1</RetrefNum></OrderInqResult></Order><Transaction><Response><Code>00</Code></Response></Transaction></GVPSResponse>'.encode()
        response = Mock(content=xml(100))
        post.return_value = response
        with self.assertRaises(hosted_gateway.GatewayError):
            hosted_gateway.verify_garanti(session, config, data)
        response.content = xml(12000)
        self.assertEqual(hosted_gateway.verify_garanti(session, config, data)["reference"], "REF1")
        session.refresh_from_db()
        self.assertEqual(hosted_gateway.recheck(session)["reference"], "REF1")

    def test_recheck_action_is_superuser_only(self):
        from django.test import RequestFactory
        model_admin = admin.site._registry[HostedPaymentSession]
        request = RequestFactory().get("/admin/")
        request.user = self.user
        self.user.is_staff = True
        self.assertFalse(model_admin.has_recheck_permission(request))
        self.user.is_superuser = True
        self.assertTrue(model_admin.has_recheck_permission(request))

    def test_settings_encrypt_keys_and_blank_admin_fields_preserve_them(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT iyzico_secret_key FROM core_paymentgatewaysettings WHERE id = %s", [self.config.pk])
            stored = cursor.fetchone()[0]
        self.assertTrue(stored.startswith("enc:v1:"))
        self.assertNotIn("test-secret-only", stored)
        form = PaymentGatewaySettingsForm(instance=self.config)
        self.assertNotIn("test-secret-only", form.as_p())
        data = {field.name: getattr(self.config, field.name) for field in self.config._meta.fields if field.editable}
        for field in form.secret_fields:
            data[field] = ""
        bound = PaymentGatewaySettingsForm(data=data, instance=self.config)
        self.assertTrue(bound.is_valid(), bound.errors)
        bound.save()
        self.config.refresh_from_db()
        self.assertEqual(self.config.iyzico_secret_key, "test-secret-only")

    def test_settings_validate_required_fields_and_superuser_access(self):
        self.config.iyzico_secret_key = ""
        with self.assertRaises(ValidationError):
            self.config.full_clean()
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(reverse("admin:core_paymentgatewaysettings_change", args=[self.config.pk]))
        self.assertEqual(response.status_code, 403)

    def test_automatic_renewal_cannot_create_fake_charge(self):
        result = renew_subscription(Mock(id=999))
        self.assertFalse(result["success"])
        self.assertFalse(Payment.objects.filter(user=self.user).exists())

    def test_company_admin_values_propagate_and_iban_is_validated(self):
        company = LegalSiteSettings.load()
        company.company_name = "Test Firma Yeni Unvan"
        company.address = "Yeni Test Adresi"
        company.support_email = "support@example.com"
        company.bank_transfer_days = 3
        company.save()
        for url in ["/", "/contact/", "/teslimat-ve-aktivasyon/", "/hukuk/mesafeli-satis-sozlesmesi/"]:
            response = self.client.get(url)
            self.assertContains(response, company.company_name)
            self.assertNotContains(response, "HZR Yazılım Danışmanlık Dijital Paz.")
        self.assertContains(self.client.get("/teslimat-ve-aktivasyon/"), "3 takvim günü")
        company.bank_iban = "TR00" + "0" * 22
        with self.assertRaises(ValidationError):
            company.full_clean()

    def test_invoice_html_and_pdf_use_company_configuration(self):
        from core.views.payment import _build_invoice_pdf
        company = LegalSiteSettings.load()
        company.company_name = "Admin Test Company"
        company.address = "Admin Test Address"
        company.save()
        session = self.session()
        complete_card_payment(session.pk, {"reference": "invoice-test"})
        invoice = Invoice.objects.get(user=self.user)
        response = self.client.get(reverse("invoice_detail", args=[invoice.pk]))
        self.assertContains(response, company.company_name)
        self.assertContains(response, company.address)
        self.assertNotContains(response, "1234567890")
        self.assertNotContains(response, "reklamanaliz.com")
        self.assertTrue(_build_invoice_pdf(invoice).startswith(b"%PDF"))

    def test_admin_pages_expose_configuration_and_hide_secrets(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        response = self.client.get(reverse("admin:core_paymentgatewaysettings_change", args=[self.config.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="garanti_store_key"')
        self.assertNotContains(response, "test-secret-only")
        response = self.client.get(reverse("admin:core_legalsitesettings_change", args=[LegalSiteSettings.load().pk]))
        self.assertContains(response, 'name="trade_registry_number"')
        self.assertContains(response, 'name="bank_iban"')
