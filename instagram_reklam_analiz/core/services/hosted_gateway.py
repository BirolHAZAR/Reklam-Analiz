"""Hosted card checkout. No PAN/CVV enters this service or application storage."""
import base64
import hashlib
import hmac
import json
import secrets
from decimal import Decimal
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import requests
from django.urls import reverse
from django.utils import timezone


class GatewayError(Exception):
    pass


def configuration(settings):
    fields = ("provider", "sandbox", "public_origin", "iyzico_api_key", "iyzico_secret_key", "garanti_merchant_id", "garanti_terminal_id", "garanti_user_id", "garanti_prov_user", "garanti_prov_password", "garanti_store_key")
    return {field: getattr(settings, field) for field in fields}


def callback_url(session, config):
    return config["public_origin"].rstrip("/") + reverse("hosted_payment_callback", kwargs={"session_id": session.pk})


def money(value):
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def signature(config, response, fields):
    values = []
    for field in fields:
        value = str(response.get(field, ""))
        if field in {"price", "paidPrice"}:
            value = format(Decimal(value).normalize(), "f")
        values.append(value)
    expected = hmac.new(config["iyzico_secret_key"].encode(), ":".join(values).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(response.get("signature", ""))):
        raise GatewayError("Ödeme yanıtı doğrulanamadı.")


def iyzico_request(config, path, payload):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    nonce = secrets.token_hex(16)
    digest = hmac.new(config["iyzico_secret_key"].encode(), (nonce + path + body).encode(), hashlib.sha256).hexdigest()
    authorization = base64.b64encode(f"apiKey:{config['iyzico_api_key']}&randomKey:{nonce}&signature:{digest}".encode()).decode()
    origin = "https://sandbox-api.iyzipay.com" if config["sandbox"] else "https://api.iyzipay.com"
    try:
        response = requests.post(origin + path, data=body.encode(), headers={"Authorization": "IYZWSv2 " + authorization, "Content-Type": "application/json", "x-iyzi-rnd": nonce}, timeout=(5, 25), allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("status") != "success":
            raise GatewayError("Ödeme kuruluşu işlemi onaylamadı.")
        return data
    except (requests.RequestException, ValueError) as exc:
        raise GatewayError("Ödeme kuruluşuna şu anda ulaşılamıyor. İşlem durumunu hesabınızdan kontrol edin.") from exc


def initialize_iyzico(session, config, ip):
    payment = session.payment
    bill = payment.billing_info
    amount = money(payment.amount)
    address = {"contactName": f"{bill.first_name} {bill.last_name}", "city": bill.city, "country": "Turkey", "address": bill.address, "zipCode": bill.zip_code}
    payload = {
        "locale": "tr", "conversationId": session.pk.hex, "basketId": session.pk.hex,
        "price": amount, "paidPrice": amount, "currency": "TRY", "paymentGroup": "SUBSCRIPTION" if payment.plan_id else "PRODUCT",
        "callbackUrl": callback_url(session, config), "enabledInstallments": [1],
        "buyer": {"id": str(payment.user_id), "name": bill.first_name, "surname": bill.last_name, "gsmNumber": bill.phone, "email": bill.email,
                  "identityNumber": bill.tc_kimlik or bill.tax_number, "registrationAddress": bill.address, "ip": ip, "city": bill.city, "country": "Turkey", "zipCode": bill.zip_code},
        "shippingAddress": address, "billingAddress": address,
        "basketItems": [{"id": str(payment.pk), "name": payment.purchase_label, "category1": "Dijital hizmet", "itemType": "VIRTUAL", "price": amount}],
    }
    data = iyzico_request(config, "/payment/iyzipos/checkoutform/initialize/auth/ecom", payload)
    signature(config, data, ("conversationId", "token"))
    if data.get("conversationId") != session.pk.hex or not data.get("token"):
        raise GatewayError("Ödeme oturumu eşleşmedi.")
    url = data.get("paymentPageUrl", "")
    parsed = urlsplit(url)
    hosts = {"sandbox-api.iyzipay.com", "sandbox-cpp.iyzipay.com"} if config["sandbox"] else {"api.iyzipay.com", "cpp.iyzipay.com"}
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.port:
        raise GatewayError("Geçersiz ödeme sayfası adresi.")
    session.token = data["token"]
    session.save(update_fields=["token"])
    return {"redirect": url}


def verify_iyzico(session, config, posted):
    token = posted.get("token", "")
    if not session.token or not hmac.compare_digest(session.token, token):
        raise GatewayError("Ödeme oturumu doğrulanamadı.")
    data = iyzico_request(config, "/payment/iyzipos/checkoutform/auth/ecom/detail", {"locale": "tr", "conversationId": session.pk.hex, "token": session.token})
    signature(config, data, ("paymentStatus", "paymentId", "currency", "basketId", "conversationId", "paidPrice", "price", "token"))
    if (data.get("paymentStatus") != "SUCCESS" or data.get("fraudStatus") != 1 or
        data.get("currency") != "TRY" or data.get("basketId") != session.pk.hex or data.get("conversationId") != session.pk.hex or data.get("token") != session.token or
        Decimal(str(data.get("paidPrice", 0))) != session.payment.amount or Decimal(str(data.get("price", 0))) != session.payment.amount or not data.get("paymentId")):
        raise GatewayError("Ödeme henüz onaylanmadı veya sipariş bilgileri eşleşmedi.")
    # Keep only accounting references, never the provider's raw card/buyer payload.
    return {"reference": str(data["paymentId"]), "items": [{key: row.get(key) for key in ("itemId", "paymentTransactionId", "paidPrice")} for row in data.get("itemTransactions", [])]}


def garanti_hash(value, algorithm="sha512"):
    return hashlib.new(algorithm, value.encode("iso-8859-9")).hexdigest().upper()


def initialize_garanti(session, config, ip):
    from core.models import LegalSiteSettings
    terminal = config["garanti_terminal_id"]
    order = session.pk.hex
    amount = str(int(session.payment.amount * 100))
    callback = callback_url(session, config)
    password = garanti_hash(config["garanti_prov_password"] + "0" + terminal, "sha1")
    digest = garanti_hash(terminal + order + amount + "949" + callback + callback + "sales" + "" + config["garanti_store_key"] + password)
    fields = {
        "mode": "TEST" if config["sandbox"] else "PROD", "apiversion": "512", "secure3dsecuritylevel": "3D_OOS_PAY",
        "terminalprovuserid": config["garanti_prov_user"], "terminaluserid": config["garanti_user_id"], "terminalmerchantid": config["garanti_merchant_id"], "terminalid": terminal,
        "orderid": order, "successurl": callback, "errorurl": callback, "customeremailaddress": session.payment.billing_info.email, "customeripaddress": ip,
        "companyname": LegalSiteSettings.load().company_name, "lang": "tr", "txntimestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "refreshtime": "1", "secure3dhash": digest, "txnamount": amount, "txntype": "sales", "txncurrencycode": "949", "txninstallmentcount": "",
    }
    origin = "https://sanalposprovtest.garantibbva.com.tr" if config["sandbox"] else "https://sanalposprov.garanti.com.tr"
    return {"action": origin + "/servlet/gt3dengine", "fields": fields}


def verify_garanti(session, config, posted):
    names = posted.get("hashparams", "").split(":")
    required = {"clientid", "oid", "authcode", "procreturncode", "response", "mdstatus"}
    if not required.issubset(names) or any(len(posted.getlist(name)) != 1 for name in names if name):
        raise GatewayError("Banka yanıtının imza alanları eksik.")
    digest = garanti_hash("".join(posted.get(name, "") for name in names if name) + config["garanti_store_key"])
    if not hmac.compare_digest(digest, posted.get("hash", "")):
        raise GatewayError("Banka yanıtı doğrulanamadı.")
    if posted.get("oid") != session.pk.hex or posted.get("clientid") != config["garanti_merchant_id"] or posted.get("procreturncode") != "00" or posted.get("mdstatus") != "1" or posted.get("response") != "Approved":
        raise GatewayError("Banka ödemeyi onaylamadı.")
    # Preserve only the authenticated fields, encrypted, so an interrupted bank
    # inquiry can be retried by an administrator without asking the buyer to pay again.
    session.token = json.dumps({name: posted.get(name, "") for name in set(names) | {"hashparams", "hash"} if name})
    session.save(update_fields=["token"])
    # The browser callback does not sign the amount. Verify it server-to-server.
    terminal = config["garanti_terminal_id"]
    amount = str(int(session.payment.amount * 100))
    password = garanti_hash(config["garanti_prov_password"] + "0" + terminal, "sha1")
    root = ET.Element("GVPSRequest")
    def add(parent, name, value):
        ET.SubElement(parent, name).text = value
    add(root, "Mode", "TEST" if config["sandbox"] else "PROD")
    add(root, "Version", "512")
    term = ET.SubElement(root, "Terminal")
    for key, value in {"ProvUserID": config["garanti_prov_user"], "UserID": config["garanti_user_id"], "ID": terminal, "MerchantID": config["garanti_merchant_id"], "HashData": garanti_hash(session.pk.hex + terminal + amount + "949" + password)}.items():
        add(term, key, value)
    customer = ET.SubElement(root, "Customer")
    add(customer, "IPAddress", session.purchase_data["ip"])
    add(customer, "EmailAddress", session.payment.billing_info.email)
    order = ET.SubElement(root, "Order")
    add(order, "OrderID", session.pk.hex)
    txn = ET.SubElement(root, "Transaction")
    for key, value in {"Type": "orderinq", "ListPageNum": "0", "Amount": amount, "CurrencyCode": "949", "MotoInd": "N"}.items():
        add(txn, key, value)
    origin = "https://sanalposprovtest.garantibbva.com.tr" if config["sandbox"] else "https://sanalposprov.garanti.com.tr"
    try:
        response = requests.post(origin + "/VPServlet", data={"data": ET.tostring(root, encoding="unicode")}, timeout=(5, 25), allow_redirects=False)
        response.raise_for_status()
        if b"<!DOCTYPE" in response.content.upper() or len(response.content) > 1000000:
            raise GatewayError("Geçersiz banka sorgu yanıtı.")
        result = ET.fromstring(response.content)
        if (result.findtext("Order/OrderID") != session.pk.hex or result.findtext("Terminal/ID") != terminal or
            result.findtext("Transaction/Response/Code") != "00" or result.findtext("Order/OrderInqResult/Code") != "00" or
            result.findtext("Order/OrderInqResult/AuthCode") != posted.get("authcode") or
            Decimal(result.findtext("Order/OrderInqResult/AuthAmount", "0")) != Decimal(amount)):
            raise GatewayError("Banka sorgusunda sipariş veya tutar doğrulanamadı.")
        reference = result.findtext("Order/OrderInqResult/RetrefNum")
        if not reference:
            raise GatewayError("Banka işlem referansı eksik.")
        return {"reference": reference}
    except (requests.RequestException, ET.ParseError, ValueError) as exc:
        raise GatewayError("Banka sorgusu tamamlanamadı; işlem onayı bekleniyor.") from exc


def initialize(session):
    config = json.loads(session.configuration)
    return (initialize_iyzico if session.provider == "iyzico" else initialize_garanti)(session, config, session.purchase_data["ip"])


def verify(session, posted):
    config = json.loads(session.configuration)
    return (verify_iyzico if session.provider == "iyzico" else verify_garanti)(session, config, posted)


def recheck(session):
    from django.http import QueryDict
    if not session.token:
        raise GatewayError("Henüz yeniden sorgulanabilecek ödeme yanıtı yok.")
    posted = QueryDict("", mutable=True)
    posted.update({"token": session.token} if session.provider == "iyzico" else json.loads(session.token))
    return verify(session, posted)
