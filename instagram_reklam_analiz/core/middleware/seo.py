from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.cache import patch_vary_headers

from core.seo import ORIGIN, PUBLIC_PAGES, is_public, route_name


class SeoMiddleware:
    """Keep authentication/callback hosts intact; default application routes to noindex."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        discovery = route_name(request) in {"robots_txt", "sitemap_xml"}
        if response.status_code >= 400 or (not is_public(request) and not discovery and not request.path.startswith(settings.STATIC_URL)):
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # A small allowlist avoids moving OAuth state, CSRF or host-only sessions.
        safe_query = all(key.startswith("utm_") or key in {"gclid", "fbclid"} for key in request.GET)
        if (
            request.get_host().lower() == "www.reklamanaliz.net"
            and request.method in {"GET", "HEAD"}
            and route_name(request) in set(PUBLIC_PAGES) | {"robots_txt", "sitemap_xml"}
            and safe_query
            and not request.COOKIES.get(settings.SESSION_COOKIE_NAME)
            and not request.COOKIES.get(settings.CSRF_COOKIE_NAME)
            and not request.headers.get("Authorization")
        ):
            response = HttpResponsePermanentRedirect(ORIGIN + request.get_full_path())
            # Do not reuse an anonymous redirect for an existing www session.
            response["Cache-Control"] = "private, no-store"
            patch_vary_headers(response, ("Cookie", "Authorization"))
            return response
        return None
