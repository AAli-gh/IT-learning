import datetime

import jdatetime
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone

register = template.Library()

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def fa_digits(value):
    """Convert Latin digits to Persian digits."""
    return str(value).translate(PERSIAN_DIGITS)


@register.filter
def toman(value):
    """1500000 -> ۱٬۵۰۰٬۰۰۰ تومان (0 -> رایگان)."""
    if not value:
        return "رایگان"
    return f"{int(value):,}".replace(",", "٬").translate(PERSIAN_DIGITS) + " تومان"


@register.filter
def money(value):
    """Like ``toman`` but zero stays "۰ تومان" (for amounts received/owed, where "free" would be wrong)."""
    return f"{int(value or 0):,}".replace(",", "٬").translate(PERSIAN_DIGITS) + " تومان"


@register.filter
def jdate(value, fmt="%d %B %Y"):
    """Render a date/datetime as a Jalali (Shamsi) date with Persian digits."""
    if not value:
        return ""
    if not isinstance(value, datetime.datetime):
        jd = jdatetime.date.fromgregorian(date=value, locale="fa_IR")
        return jd.strftime(fmt).translate(PERSIAN_DIGITS)
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    jd = jdatetime.datetime.fromgregorian(datetime=value, locale="fa_IR")
    return jd.strftime(fmt).translate(PERSIAN_DIGITS)


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Rebuild the current query string with some params replaced (for pagination)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        params[key] = value
    return params.urlencode()


# Two-tone inline SVG icons for the header (24x24). Drawn here so the site needs no icon font or CDN.
_ICONS = {
    "home": '<path d="M12 3 2 12h3v8h5v-5h4v5h5v-8h3L12 3z" fill="#2563eb"/>',
    "layers": ('<path d="M12 2 1 8l11 6 11-6L12 2z" fill="#60a5fa"/>'
               '<path d="m1 12 11 6 11-6M1 16l11 6 11-6" fill="none" stroke="#2563eb" stroke-width="2" stroke-linejoin="round"/>'),
    "laptop": '<rect x="4" y="5" width="16" height="11" rx="2" fill="#60a5fa"/><path d="M2 18h20l-2 2H4l-2-2z" fill="#2563eb"/>',
    "globe": ('<circle cx="12" cy="12" r="10" fill="#60a5fa"/>'
              '<path d="M2 12h20M12 2c3 3 3 17 0 20M12 2c-3 3-3 17 0 20" fill="none" stroke="#fff" stroke-width="1.5"/>'),
    "plug": ('<path d="M8 2v6M16 2v6M12 18v4" stroke="#7c3aed" stroke-width="2.5" stroke-linecap="round"/>'
             '<path d="M5 8h14v3a7 7 0 0 1-14 0V8z" fill="#8b5cf6"/>'),
    "shield": ('<path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z" fill="#3b82f6"/>'
               '<path d="M12 2v20c4.6-1.6 8-6 8-11V5l-8-3z" fill="#1d4ed8" opacity=".55"/>'),
    "penguin": ('<ellipse cx="12" cy="13" rx="7" ry="9" fill="#334155" stroke="#94a3b8" stroke-width=".8"/><ellipse cx="12" cy="15" rx="4.5" ry="6" fill="#f8fafc"/>'
                '<circle cx="10" cy="8" r="1.2" fill="#fff"/><circle cx="14" cy="8" r="1.2" fill="#fff"/>'
                '<path d="M10.5 10.5h3L12 12.4z" fill="#f59e0b"/><path d="M7 21h4M13 21h4" stroke="#f59e0b" stroke-width="2" stroke-linecap="round"/>'),
    "robot": ('<rect x="4" y="7" width="16" height="12" rx="4" fill="#8b5cf6"/><circle cx="9" cy="13" r="2" fill="#fff"/>'
              '<circle cx="15" cy="13" r="2" fill="#fff"/><path d="M12 7V3" stroke="#6d28d9" stroke-width="2"/><circle cx="12" cy="3" r="1.5" fill="#6d28d9"/>'),
    "cap": ('<path d="M12 4 1 9l11 5 9-4.1V16h2V9L12 4z" fill="#1d4ed8"/>'
            '<path d="M5 13v4c0 1.5 3.1 3 7 3s7-1.5 7-3v-4l-7 3.2L5 13z" fill="#60a5fa"/>'),
    "user": '<circle cx="12" cy="8" r="4.5" fill="currentColor"/><path d="M3.5 21c0-4.5 3.8-7 8.5-7s8.5 2.5 8.5 7z" fill="currentColor"/>',
    "search": ('<circle cx="10.5" cy="10.5" r="6.5" fill="#dbeafe" stroke="#4f46e5" stroke-width="2.5"/>'
               '<path d="m15.5 15.5 5.5 5.5" stroke="#4f46e5" stroke-width="3" stroke-linecap="round"/>'),
    "theme": '<circle cx="12" cy="12" r="9" fill="#1e1b4b" stroke="#a5b4fc" stroke-width="1"/><path d="M12 3a9 9 0 0 1 0 18z" fill="#fbbf24"/>',
    "gear": ('<circle cx="12" cy="12" r="3.2" fill="#fff"/><path d="M12 2.5l1.6 2.6 3-.6.6 3 2.6 1.6-1.4 2.7 1.4 2.7-2.6 1.6-.6 3-3-.6L12 21.5l-1.6-2.6-3 .6-.6-3-2.6-1.6L5.6 12 4.2 9.3l2.6-1.6.6-3 3 .6L12 2.5z" fill="#fff" opacity=".9"/>'
             '<circle cx="12" cy="12" r="3" fill="#6d28d9"/>'),
}

# Category slug -> icon name; any other category falls back to its own emoji.
_CATEGORY_ICONS = {"programming": "laptop", "web": "globe", "network": "plug", "security": "shield",
                   "linux": "penguin", "ai": "robot"}


@register.simple_tag
def icon(name, size=20, css=""):
    body = _ICONS[name]  # unknown names are a programming error, not user input
    return format_html('<svg viewBox="0 0 24 24" width="{0}" height="{0}" class="shrink-0 {1}" aria-hidden="true">{2}</svg>',
                       size, css, mark_safe(body))


@register.simple_tag
def category_icon(category, size=20):
    name = _CATEGORY_ICONS.get(category.slug)
    if name:
        return icon(name, size)
    return format_html('<span class="shrink-0 leading-none" style="font-size:{}px" aria-hidden="true">{}</span>',
                       size - 2, category.icon or "🎓")
