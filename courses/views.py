from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import magazine

from .forms import EnrollmentForm
from .models import Batch, Category, Course, Enrollment

SORTS = {"new": "-published_at", "price": "price", "price_desc": "-price", "duration": "duration_hours"}
ENROLL_LIMIT = (5, 3600)  # at most 5 enrollments per hour per IP


def home(request):
    courses = Course.objects.published().with_relations()
    return render(request, "courses/home.html", {
        "featured": courses.filter(is_featured=True)[:3] or courses[:3],
        "latest": courses.order_by("-published_at")[:6],
        "home_categories": Category.objects.filter(show_on_home=True),
        "articles": magazine.latest_articles(3),
    })


def course_list(request, category=None):
    params = request.GET
    qs = Course.objects.published().with_relations().search(params.get("q", "").strip())
    cat = get_object_or_404(Category, slug=category) if category else None
    if cat:
        qs = qs.filter(category=cat)
    if params.get("level") in Course.Level.values:
        qs = qs.filter(level=params["level"])
    if params.get("mode") in Batch.Mode.values:
        qs = qs.filter(batches__mode=params["mode"], batches__is_open=True).distinct()
    sort = params.get("sort", "")
    qs = qs.order_by(SORTS[sort]) if sort in SORTS else qs
    page_obj = Paginator(qs, 12).get_page(params.get("page"))
    return render(request, "courses/list.html", {
        "page_obj": page_obj, "category": cat, "q": params.get("q", ""),
        "levels": Course.Level.choices, "modes": Batch.Mode.choices,
        "current": {"level": params.get("level", ""), "mode": params.get("mode", ""), "sort": sort},
    })


def course_detail(request, slug):
    course = get_object_or_404(Course.objects.published().with_relations(), slug=slug)
    initial = {}
    if request.user.is_authenticated:
        initial = {"full_name": request.user.get_full_name(), "email": request.user.email,
                   "phone": request.user.phone}
    related = Course.objects.published().with_relations().filter(category=course.category).exclude(pk=course.pk)[:3]
    return render(request, "courses/detail.html", {
        "course": course,
        "form": EnrollmentForm(course=course, initial=initial),
        "related_courses": related,
        "articles": magazine.articles_for_tag(course.magazine_tag, 3),
        "magazine_tag_url": magazine.tag_url(course.magazine_tag),
    })


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "")


@require_POST
def enroll(request, slug):
    course = get_object_or_404(Course.objects.published(), slug=slug)
    key = f"enroll:{_client_ip(request)}"
    limit, window = ENROLL_LIMIT
    count = cache.get(key, 0)
    if count >= limit:
        return render(request, "429.html", status=429)
    form = EnrollmentForm(request.POST, course=course)
    if form.is_valid():
        enrollment = form.save(commit=False)
        enrollment.course = course
        if request.user.is_authenticated:
            enrollment.user = request.user
        enrollment.save()
        cache.set(key, count + 1, window)
        if request.headers.get("HX-Request"):
            return render(request, "courses/partials/enroll_done.html", {"course": course})
        messages.success(request, "ثبت‌نام شما انجام شد؛ به‌زودی با شما تماس می‌گیریم.")
        return redirect(course)
    template = "courses/partials/enroll_form.html" if request.headers.get("HX-Request") else "courses/detail.html"
    context = {"course": course, "form": form}
    if template == "courses/detail.html":
        context.update(related_courses=[], articles=magazine.articles_for_tag(course.magazine_tag, 3),
                       magazine_tag_url=magazine.tag_url(course.magazine_tag))
    return render(request, template, context, status=422 if request.headers.get("HX-Request") else 200)
