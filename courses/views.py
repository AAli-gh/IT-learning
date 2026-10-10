from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from core import magazine
from core.notify import notify_staff, notify_student

from .forms import EnrollmentForm, ReviewForm
from .models import Batch, Category, Certificate, Course, Enrollment, Faq, Review

SORTS = {"new": "-published_at", "price": "price", "price_desc": "-price", "duration": "duration_hours"}
ENROLL_LIMIT = (5, 3600)  # at most 5 enrollments per hour per IP


def home(request):
    courses = Course.objects.published().with_relations()
    return render(request, "courses/home.html", {
        "featured": courses.filter(is_featured=True)[:3] or courses[:3],
        "latest": courses.order_by("-published_at")[:6],
        "home_categories": Category.objects.filter(show_on_home=True),
        "articles": magazine.latest_articles(3),
        "stats": {
            "courses": Course.objects.published().count(),
            "students": Enrollment.objects.filter(status=Enrollment.Status.CONFIRMED).count(),
            "instructors": User.objects.filter(is_instructor=True).count(),
        },
        "testimonials": Review.objects.filter(is_approved=True, is_featured=True).select_related("user", "course")[:3],
        "faqs": Faq.objects.filter(is_published=True, course__isnull=True)[:5],
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
    can_review, my_review = False, None
    if request.user.is_authenticated:
        my_review = Review.objects.filter(course=course, user=request.user).first()
        can_review = my_review is None and Enrollment.objects.filter(
            course=course, user=request.user, status=Enrollment.Status.CONFIRMED).exists()
    related = Course.objects.published().with_relations().filter(category=course.category).exclude(pk=course.pk)[:3]
    return render(request, "courses/detail.html", {
        "course": course,
        "form": EnrollmentForm(course=course, initial=initial),
        "related_courses": related,
        "reviews": Review.objects.filter(course=course, is_approved=True).select_related("user"),
        "review_form": ReviewForm() if can_review else None,
        "my_review": my_review,
        "faqs": Faq.objects.filter(is_published=True, course=course),
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
        notify_staff(f"ثبت‌نام جدید: {course.title}",
                     f"{enrollment.full_name}\nتلفن: {enrollment.phone}\nایمیل: {enrollment.email}\n"
                     f"دوره برگزاری: {enrollment.batch or '—'}\n\n{enrollment.note}")
        notify_student(enrollment.email, f"ثبت‌نام شما در «{course.title}»",
                       f"{enrollment.full_name} عزیز،\nثبت‌نام شما دریافت شد و همکاران ما به‌زودی با شماره "
                       f"{enrollment.phone} تماس می‌گیرند.")
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


@login_required
@require_POST
def review(request, slug):
    course = get_object_or_404(Course.objects.published(), slug=slug)
    confirmed = Enrollment.objects.filter(course=course, user=request.user,
                                          status=Enrollment.Status.CONFIRMED).exists()
    if not confirmed:
        messages.error(request, "فقط دانشجویانِ تأییدشدهٔ این دوره می‌توانند نظر بدهند.")
    elif Review.objects.filter(course=course, user=request.user).exists():
        messages.info(request, "شما قبلاً برای این دوره نظر داده‌اید.")
    else:
        form = ReviewForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.course, obj.user = course, request.user
            obj.save()
            notify_staff(f"نظر جدید برای {course.title}", f"{obj.rating}/5\n{obj.text}")
            messages.success(request, "نظر شما ثبت شد و پس از تأیید نمایش داده می‌شود.")
        else:
            messages.error(request, "امتیاز و متن نظر را وارد کنید.")
    return redirect(course)


def instructors(request):
    people = User.objects.filter(is_instructor=True).prefetch_related("courses")
    return render(request, "courses/instructors.html", {"people": people})


def faq(request):
    return render(request, "courses/faq.html", {"faqs": Faq.objects.filter(is_published=True, course__isnull=True)})


def suggest(request):
    """Live search suggestions for the header search box (HTMX)."""
    q = request.GET.get("q", "").strip()
    results = Course.objects.published().search(q).select_related("category")[:6] if len(q) >= 2 else []
    return render(request, "courses/partials/suggest.html", {"results": results, "q": q})


def certificate(request, code):
    """Public verification + printable certificate (anyone with the code can check it)."""
    cert = get_object_or_404(Certificate.objects.select_related("course", "course__instructor"), code=code.upper())
    return render(request, "courses/certificate.html", {"cert": cert,
                  "verify_url": request.build_absolute_uri(cert.get_absolute_url())})
