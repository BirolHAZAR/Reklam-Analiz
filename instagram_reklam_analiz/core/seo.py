"""Public SEO policy; unknown/application routes are private by default."""
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, tostring

from django.http import HttpResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.decorators.http import require_safe

ORIGIN = "https://reklamanaliz.net"
PUBLIC_PAGES = {
    "delivery_terms": ("Teslimat ve Aktivasyon | ReklamAnaliz.net", "Dijital abonelik ve kullanım haklarının aktivasyonunu, havale kontrol süresini, yenileme ve destek koşullarını inceleyin."),
    "index": ("ReklamAnaliz.net | Akıllı Reklam Analizi", "Reklam performansınızı tek merkezden izleyin. ReklamAnaliz.net ile kampanya, bütçe, rakip ve sosyal medya analizlerini keşfedin."),
    "about": ("Hakkımızda | ReklamAnaliz.net", "ReklamAnaliz.net'in reklam analizi, kampanya yönetimi ve veriye dayalı dijital pazarlama yaklaşımını tanıyın."),
    "contact": ("İletişim | ReklamAnaliz.net", "ReklamAnaliz.net ekibine ulaşın. Reklam analizi, platform entegrasyonları ve hizmetlerimiz hakkında sorularınızı iletin."),
    "demo_request": ("Demo Talebi | ReklamAnaliz.net", "ReklamAnaliz.net için demo talep edin; reklam analizi, raporlama ve kampanya yönetimi özelliklerini işletmeniz için keşfedin."),
    "pricing": ("Paketler ve Fiyatlar | ReklamAnaliz.net", "ReklamAnaliz.net abonelik paketlerini ve özelliklerini karşılaştırın. İşletmenizin reklam analizi ihtiyaçlarına uygun planı seçin."),
    "legal_document_index": ("Hukuki Metinler | ReklamAnaliz.net", "ReklamAnaliz.net kullanım koşulları, gizlilik politikaları ve yayımlanmış hukuki belgelerine ulaşın."),
    "influencer_discovery": ("Influencer Keşfi | ReklamAnaliz.net", "Influencer profillerini keşfedin; platform, kategori, takipçi ve etkileşim bilgileriyle markanıza uygun içerik üreticilerini inceleyin."),
}
DYNAMIC_PUBLIC = {"legal_document_detail", "influencer_detail"}
DISCOVERY_PARAMETERS = {"q", "platform", "category", "country", "min_followers", "min_engagement", "page"}


def route_name(request):
    return getattr(getattr(request, "resolver_match", None), "view_name", "")


def is_public(request):
    name = route_name(request)
    if request.GET.get("preview") or request.method not in ("GET", "HEAD"):
        return False
    if name == "influencer_discovery" and any(request.GET.get(key) for key in DISCOVERY_PARAMETERS):
        return False
    return name in PUBLIC_PAGES or name in DYNAMIC_PUBLIC


def metadata(context):
    request = context.get("request")
    name = route_name(request) if request else ""
    title, description = PUBLIC_PAGES.get(name, ("Hesap ve Yönetim | ReklamAnaliz.net", "ReklamAnaliz.net hesabınızı ve reklam yönetimi araçlarınızı güvenli oturumunuz üzerinden kullanın."))
    public = bool(request and is_public(request))
    if name == "legal_document_detail":
        document = context.get("document")
        public = public and bool(document and document.status == "published")
        if document:
            title = f"{document.title} | ReklamAnaliz.net"
            description = document.summary or f"ReklamAnaliz.net {document.title} belgesini ve hizmet koşullarını inceleyin."
    elif name == "influencer_detail":
        influencer = context.get("influencer")
        public = public and bool(influencer and influencer.is_active)
        if influencer:
            title = f"{influencer.display_name} | Influencer | ReklamAnaliz.net"
            platform = influencer.platform.name if influencer.platform else "sosyal medya"
            description = f"{influencer.display_name} adlı içerik üreticisinin {platform} profilini, takipçi ve etkileşim verilerini inceleyin."
    path = request.path if request else "/"
    # No query strings: OAuth codes, state, reset tokens and filters must not leak.
    return {
        "title": title,
        "description": " ".join(strip_tags(description).split())[:170],
        "canonical": ORIGIN + path if public else "",
        "robots": "index, follow" if public else "noindex, nofollow",
        "image": urljoin(ORIGIN, static("images/logo2.png")),
    }


@require_safe
def robots_txt(request):
    # Crawlers must be able to read the noindex response on private routes.
    return HttpResponse(f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n", content_type="text/plain; charset=utf-8")


@require_safe
def sitemap_xml(request):
    from core.models import Influencer, LegalDocument

    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    def add(path, modified=None):
        node = SubElement(root, "url")
        SubElement(node, "loc").text = ORIGIN + path
        if modified:
            SubElement(node, "lastmod").text = modified.date().isoformat()

    for name in PUBLIC_PAGES:
        add(reverse(name))
    for document in LegalDocument.objects.filter(status=LegalDocument.STATUS_PUBLISHED).only("slug", "updated_at").iterator():
        add(document.get_absolute_url(), document.updated_at)
    for influencer in Influencer.objects.filter(is_active=True).only("pk").iterator():
        add(reverse("influencer_detail", kwargs={"influencer_id": influencer.pk}))
    return HttpResponse(tostring(root, encoding="utf-8", xml_declaration=True), content_type="application/xml; charset=utf-8")
