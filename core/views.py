from django.conf import settings
from django.core.exceptions import BadRequest, PermissionDenied
from django.db import connection
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET

from django.contrib import messages
from django.core.cache import cache

from .forms import ContactForm
from .models import Page
from .notify import notify_staff


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "core/page.html", {"page": page})


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {"name": request.user.get_full_name(), "email": request.user.email, "phone": request.user.phone}
    form = ContactForm(request.POST or None, initial=initial)
    key = f"contact:{request.META.get('REMOTE_ADDR', '')}"
    if request.method == "POST":
        if cache.get(key, 0) >= 5:
            return render(request, "429.html", status=429)
        if form.is_valid():
            msg = form.save()
            cache.set(key, cache.get(key, 0) + 1, 3600)
            notify_staff(f"پیام تماس جدید از {msg.name}",
                         f"{msg.subject}\n\n{msg.message}\n\nتلفن: {msg.phone}\nایمیل: {msg.email}")
            messages.success(request, "پیام شما ارسال شد؛ به‌زودی پاسخ می‌دهیم.")
            return redirect("core:contact")
    return render(request, "core/contact.html", {"form": form})


@require_GET
def favicon(request):
    """Browsers request /favicon.ico directly; point them at the static icon."""
    return redirect(static("brand/favicon.ico"), permanent=True)


def robots_txt(request):
    sitemap = settings.SITE_URL.rstrip("/") + reverse("django.contrib.sitemaps.views.sitemap")
    lines = [
        "User-agent: *",
        "Disallow: /accounts/",
        "Disallow: /courses/*/enroll/",
        f"Sitemap: {sitemap}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def admin_login(request):
    """Send the admin login form to allauth (which handles 2FA), then back to the admin."""
    from urllib.parse import urlencode

    next_url = request.GET.get("next") or reverse("admin:index")
    return redirect(f"{reverse('account_login')}?{urlencode({'next': next_url})}")


def healthz(request):
    """Liveness/readiness probe for Docker and load balancers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


PREVIEW_CODES = {400, 401, 403, 429, 500, 503, 504}


def error_preview(request, code):
    """Lets site admins preview the custom error pages; everyone else gets a 404."""
    if not request.user.is_superuser or code not in PREVIEW_CODES:
        raise Http404
    if code == 400:
        raise BadRequest
    if code == 403:
        raise PermissionDenied
    if code in (401, 429):
        return render(request, f"{code}.html", status=code)
    response = HttpResponse(render_to_string(f"{code}.html"), status=code)
    response._has_been_logged = True  # a preview is not a real server error
    return response
