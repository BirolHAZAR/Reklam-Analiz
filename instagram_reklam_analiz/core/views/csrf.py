from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views.csrf import csrf_failure as django_csrf_failure
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode


def csrf_failure(request, reason=""):
    """Recover safely from a stale login form after an app/server restart."""
    if request.method == "POST" and request.path == reverse("admin:login"):
        params = {"csrf_refreshed": "1"}
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            params["next"] = next_url
        # Reject the original POST. A fresh GET renders a new masked token using
        # the current cookie, without invalidating forms in other open tabs.
        response = redirect(reverse("admin:login") + "?" + urlencode(params))
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        return response
    if request.method == "POST" and request.path == reverse("account_login"):
        response = redirect(f"{reverse('account_login')}?csrf_refreshed=1")
        response.delete_cookie(
            settings.CSRF_COOKIE_NAME,
            path=settings.CSRF_COOKIE_PATH,
            domain=settings.CSRF_COOKIE_DOMAIN,
            samesite=settings.CSRF_COOKIE_SAMESITE,
        )
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        return response

    return django_csrf_failure(request, reason=reason)
