from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse


class AdminMFAMiddleware:
    """Require staff to set up two-factor authentication before using the admin panel.

    Admin logins go through allauth (see config/urls.py), which asks for the
    authenticator code; this middleware makes sure every staff account has one.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.ADMIN_REQUIRE_MFA
            and request.path.startswith("/" + settings.ADMIN_URL)
            and request.user.is_authenticated
            and request.user.is_staff
            and not self._has_mfa(request.user)
        ):
            messages.warning(request, "برای ورود به پنل مدیریت، ابتدا ورود دومرحله‌ای را فعال کنید.")
            return redirect(f"{reverse('mfa_activate_totp')}?next={request.path}")
        return self.get_response(request)

    @staticmethod
    def _has_mfa(user):
        from allauth.mfa.models import Authenticator

        return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()


class MaintenanceModeMiddleware:
    """With MAINTENANCE_MODE on, visitors get the 503 page; staff, login and admin keep working."""

    EXEMPT_PREFIXES = ("/accounts/", "/static/", "/media/", "/healthz")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.MAINTENANCE_MODE
            and not request.path.startswith((*self.EXEMPT_PREFIXES, "/" + settings.ADMIN_URL))
            and not (request.user.is_authenticated and request.user.is_staff)
        ):
            response = HttpResponse(render_to_string("503.html"), status=503)
            response["Retry-After"] = "600"
            return response
        return self.get_response(request)


class ApiCorsMiddleware:
    """Read-only CORS for /api/ so the magazine's pages can fetch courses from the browser."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        origin = request.headers.get("Origin")
        if (
            request.path.startswith("/api/")
            and request.method in ("GET", "HEAD", "OPTIONS")
            and origin
            and origin in settings.API_CORS_ALLOWED_ORIGINS
        ):
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
        return response
