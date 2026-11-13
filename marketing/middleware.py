from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponsePermanentRedirect


class MarketingHostMiddleware:
    """Select public routes only for explicitly configured, validated hosts."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = urlsplit("//" + request.get_host()).hostname
        request.is_marketing = False
        if host in (*settings.MARKETING_HOSTS, *settings.MARKETING_PREVIEW_HOSTS):
            if settings.APP_ROLE != "cloud":
                return HttpResponseNotFound()
            if host == "www.washdayph.com" and request.method in ("GET", "HEAD"):
                return HttpResponsePermanentRedirect(
                    "https://washdayph.com" + request.get_full_path()
                )
            request.is_marketing = True
            request.urlconf = "marketing.urls"
        return self.get_response(request)
