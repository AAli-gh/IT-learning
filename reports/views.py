import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q, Sum, Value
from django.db.models.functions import Greatest, TruncDate
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from courses.models import Certificate, Course, Enrollment, Review, WaitlistEntry

PERIODS = (30, 90, 365)


def _allowed(user):
    return user.is_superuser or (user.is_staff and user.has_perm("courses.view_enrollment"))


def _week_start(day):
    """Persian weeks start on Saturday."""
    return day - datetime.timedelta(days=(day.weekday() + 2) % 7)


def _trend(days, since):
    """Enrollments per day (per week for long periods) as [{day, count, height%}] for a simple bar chart."""
    per_day = {row["day"]: row["n"] for row in Enrollment.objects.filter(created_at__gte=since)
               .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id"))}
    weekly = days > 90
    counts = {}
    for day, n in per_day.items():
        key = _week_start(day) if weekly else day
        counts[key] = counts.get(key, 0) + n
    today = timezone.localdate()
    day = _week_start(timezone.localdate(since)) if weekly else timezone.localdate(since)
    buckets = []
    while day <= today:
        buckets.append({"day": day, "count": counts.get(day, 0)})
        day += datetime.timedelta(days=7 if weekly else 1)
    peak = max((b["count"] for b in buckets), default=0) or 1
    for b in buckets:
        b["height"] = max(4, round(100 * b["count"] / peak)) if b["count"] else 2
    return buckets, sum(b["count"] for b in buckets)


@login_required
def dashboard(request):
    if not _allowed(request.user):
        raise Http404
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in PERIODS else 30
    since = timezone.now() - datetime.timedelta(days=days)
    live = Enrollment.objects.exclude(status=Enrollment.Status.CANCELLED)
    confirmed = Enrollment.objects.filter(status=Enrollment.Status.CONFIRMED)

    money = confirmed.aggregate(expected=Sum("price"), collected=Sum("paid_amount"),
                                outstanding=Sum(Greatest(F("price") - F("paid_amount"), Value(0))))
    trend, trend_total = _trend(days, since)

    new_in_period = dict(Enrollment.objects.filter(created_at__gte=since).exclude(status=Enrollment.Status.CANCELLED)
                         .values_list("course_id").annotate(n=Count("id")))
    confirmed_by = dict(confirmed.values_list("course_id").annotate(n=Count("id")))
    collected_by = dict(live.values_list("course_id").annotate(s=Sum("paid_amount")))
    certs_by = dict(Certificate.objects.filter(is_revoked=False).values_list("course_id").annotate(n=Count("id")))
    rating_by = dict(Review.objects.filter(is_approved=True).values_list("course_id").annotate(a=Avg("rating")))
    rows = []
    for course in Course.objects.select_related("category"):
        students = confirmed_by.get(course.pk, 0)
        rows.append({"course": course, "new": new_in_period.get(course.pk, 0), "confirmed": students,
                     "collected": collected_by.get(course.pk) or 0, "certificates": certs_by.get(course.pk, 0),
                     "completion": round(100 * certs_by.get(course.pk, 0) / students) if students else None,
                     "rating": round(rating_by[course.pk], 1) if course.pk in rating_by else None})
    peak = max((r["new"] for r in rows), default=0) or 1
    for r in rows:
        r["bar"] = round(100 * r["new"] / peak)
    rows.sort(key=lambda r: (-r["new"], -r["confirmed"]))

    return render(request, "reports/dashboard.html", {
        "days": days, "periods": PERIODS, "trend": trend, "trend_total": trend_total, "rows": rows,
        "kpi": {
            "students": confirmed.exclude(user=None).values("user").distinct().count(),
            "pending": Enrollment.objects.filter(status=Enrollment.Status.PENDING).count(),
            "confirmed": confirmed.count(),
            "new": sum(new_in_period.values()),
            "waiting": WaitlistEntry.objects.filter(status=WaitlistEntry.Status.WAITING).count(),
            "certificates": Certificate.objects.filter(is_revoked=False).count(),
            "expected": money["expected"] or 0, "collected": money["collected"] or 0,
            "outstanding": money["outstanding"] or 0,
        }})
