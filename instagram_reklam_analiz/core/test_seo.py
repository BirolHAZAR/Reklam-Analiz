from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from django.conf import settings
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from core.middleware.seo import SeoMiddleware
from core.seo import ORIGIN, PUBLIC_PAGES, metadata, robots_txt, sitemap_xml


@override_settings(ALLOWED_HOSTS=["testserver", "reklamanaliz.net", "www.reklamanaliz.net"],
                   STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SeoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, path, method="get", host="www.reklamanaliz.net", **kwargs):
        request = getattr(self.factory, method)(path, HTTP_HOST=host, secure=True, **kwargs)
        request.resolver_match = resolve(request.path)
        return request

    def redirect_response(self, request):
        middleware = SeoMiddleware(lambda request: HttpResponse("ok"))
        return middleware.process_view(request, request.resolver_match.func, (), {})

    def test_public_metadata_has_distinct_descriptions_and_clean_canonical(self):
        descriptions = set()
        for name in PUBLIC_PAGES:
            with self.subTest(name=name):
                request = self.request(reverse(name) + "?utm_source=test")
                seo = metadata({"request": request})
                self.assertEqual(seo["canonical"], ORIGIN + reverse(name))
                self.assertEqual(seo["robots"], "index, follow")
                descriptions.add(seo["description"])
        self.assertEqual(len(descriptions), len(PUBLIC_PAGES))

    def test_template_renders_one_set_of_tags_and_escapes_dynamic_content(self):
        request = self.request("/influencers/1/?code=secret")
        influencer = SimpleNamespace(display_name='Example "<script>"', is_active=True,
                                     platform=SimpleNamespace(name="Instagram"))
        html = Template('{% load seo_tags %}{% seo_meta %}').render(Context({"request": request, "influencer": influencer}))
        for tag in ['name="description"', 'rel="canonical"', 'property="og:title"', 'name="twitter:card"']:
            self.assertEqual(html.count(tag), 1)
        self.assertNotIn("<script>", html)
        self.assertNotIn("secret", html)
        self.assertIn('content="https://reklamanaliz.net/static/images/logo2.png"', html)

    def test_login_account_admin_api_and_panels_are_noindex(self):
        for path in ["/accounts/login/", "/accounts/signup/", "/accounts/password/reset/", "/login/", "/account/", "/profile/", "/account/invoices/", "/checkout/1/", "/dashboard/", "/admin/", "/api/alerts/check/", "/connect/facebook/callback/"]:
            with self.subTest(path=path):
                request = self.request(path)
                self.assertEqual(metadata({"request": request})["robots"], "noindex, nofollow")
                self.assertEqual(metadata({"request": request})["canonical"], "")
                response = SeoMiddleware(lambda request: HttpResponse("ok"))(request)
                self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
                self.assertIsNone(self.redirect_response(request))

    def test_filtered_discovery_and_legal_previews_are_noindex(self):
        for path in ["/influencers/?q=abc", "/influencers/?page=2", "/hukuk/?preview=1"]:
            self.assertEqual(metadata({"request": self.request(path)})["robots"], "noindex, nofollow")
        document = SimpleNamespace(title="Gizlilik", summary="Özel açıklama", status="draft")
        context = {"request": self.request("/hukuk/gizlilik/"), "document": document}
        self.assertEqual(metadata(context)["robots"], "noindex, nofollow")
        document.status = "published"
        self.assertEqual(metadata(context)["description"], "Özel açıklama")
        self.assertEqual(metadata(context)["robots"], "index, follow")

    def test_www_redirect_preserves_tracking_query_and_has_no_shared_cache(self):
        for method in ["get", "head"]:
            request = self.request("/about/?utm_source=x%2By&fbclid=123", method=method)
            response = self.redirect_response(request)
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response["Location"], ORIGIN + "/about/?utm_source=x%2By&fbclid=123")
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("Cookie", response["Vary"])

    def test_existing_sessions_csrf_posts_auth_and_unknown_queries_stay_on_host(self):
        for cookie in [settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME]:
            request = self.request("/about/")
            request.COOKIES[cookie] = "existing"
            self.assertIsNone(self.redirect_response(request))
        for path in ["/?state=oauth&code=secret", "/pricing/?ref=PARTNER", "/?next=/account/", "/?error=denied"]:
            self.assertIsNone(self.redirect_response(self.request(path)))
        self.assertIsNone(self.redirect_response(self.request("/contact/", method="post", data={"message": "test"})))
        self.assertIsNone(self.redirect_response(self.request("/", HTTP_AUTHORIZATION="Bearer test")))
        self.assertIsNone(self.redirect_response(self.request("/about/", host="reklamanaliz.net")))

    def test_error_responses_are_noindex(self):
        response = SeoMiddleware(lambda request: HttpResponse(status=404))(self.request("/about/"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_robots_allows_reading_noindex_and_points_to_canonical_sitemap(self):
        response = robots_txt(self.factory.get("/robots.txt"))
        self.assertIn("text/plain", response["Content-Type"])
        self.assertIn(f"Sitemap: {ORIGIN}/sitemap.xml", response.content.decode())
        self.assertNotIn("Disallow: /accounts", response.content.decode())

    @patch("core.models.Influencer.objects.filter")
    @patch("core.models.LegalDocument.objects.filter")
    def test_sitemap_lists_only_public_active_published_urls(self, documents, influencers):
        from datetime import datetime, timezone
        document = SimpleNamespace(get_absolute_url=lambda: "/hukuk/gizlilik/", updated_at=datetime(2026, 9, 25, tzinfo=timezone.utc))
        documents.return_value.only.return_value.iterator.return_value = [document]
        influencers.return_value.only.return_value.iterator.return_value = [SimpleNamespace(pk=7)]
        response = sitemap_xml(self.factory.get("/sitemap.xml"))
        root = ElementTree.fromstring(response.content)
        urls = [node.text for node in root.findall("{*}url/{*}loc")]
        self.assertEqual(len(urls), len(PUBLIC_PAGES) + 2)
        self.assertTrue(all(url.startswith(ORIGIN + "/") for url in urls))
        self.assertIn(ORIGIN + "/influencers/7/", urls)
        self.assertNotIn(ORIGIN + "/accounts/login/", urls)
        documents.assert_called_once_with(status="published")
        influencers.assert_called_once_with(is_active=True)

    def test_discovery_endpoints_resolve(self):
        self.assertEqual(resolve("/robots.txt").func, robots_txt)
        self.assertEqual(resolve("/sitemap.xml").func, sitemap_xml)


@override_settings(ALLOWED_HOSTS=["testserver", "reklamanaliz.net", "www.reklamanaliz.net"])
class SeoIntegrationTests(TestCase):
    def test_public_pages_and_login_render_through_real_middleware(self):
        for name in PUBLIC_PAGES:
            with self.subTest(name=name):
                response = self.client.get(reverse(name), secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="description"', count=1)
                self.assertContains(response, 'rel="canonical"', count=1)
                self.assertContains(response, 'name="twitter:card"', count=1)
                self.assertNotIn("X-Robots-Tag", response)
        response = self.client.get("/accounts/login/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex, nofollow"')
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_dynamic_pages_and_sitemap_use_real_public_records(self):
        from core.models import Influencer, LegalDocument
        document = LegalDocument.objects.first()
        document.publish()
        influencer = Influencer.objects.create(handle="seo-test", display_name="SEO Test", is_active=True)
        inactive = Influencer.objects.create(handle="hidden-seo", display_name="Hidden", is_active=False)
        for path in [document.get_absolute_url(), f"/influencers/{influencer.pk}/"]:
            response = self.client.get(path, secure=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'href="{ORIGIN}{path}"')
        response = self.client.get("/sitemap.xml", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, document.get_absolute_url())
        self.assertContains(response, f"/influencers/{influencer.pk}/")
        self.assertNotContains(response, f"/influencers/{inactive.pk}/")
        response = self.client.get("/influencers/?q=seo", secure=True)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_www_redirect_and_login_flow_through_real_stack(self):
        response = self.client.get("/about/?utm_source=test", HTTP_HOST="www.reklamanaliz.net", secure=True)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], ORIGIN + "/about/?utm_source=test")
        response = self.client.get("/accounts/login/?next=/account/", HTTP_HOST="www.reklamanaliz.net", secure=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/accounts/login/", {"login": "nobody@example.com", "password": "invalid"}, HTTP_HOST="www.reklamanaliz.net", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
