import datetime

import jdatetime
from django import template
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
