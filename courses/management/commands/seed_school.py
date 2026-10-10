"""Create categories, static pages and (with --demo) sample courses. Safe to run repeatedly."""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from core.models import Page
from courses.models import Announcement, Batch, Category, ClassSession, Course, Faq, Lesson, Topic

CATEGORIES = [
    ("برنامه‌نویسی", "programming", "💻"), ("توسعه وب", "web", "🌐"), ("شبکه", "network", "🔌"),
    ("امنیت", "security", "🛡️"), ("لینوکس و DevOps", "linux", "🐧"), ("هوش مصنوعی", "ai", "🤖"),
]

PAGES = [
    ("درباره ما", "about", "## آموزشگاه فناوری\n\nآموزش کاربردی و پروژه‌محور فناوری اطلاعات، همراه با مجله تخصصی IT."),
    ("قوانین و مقررات", "terms", "## قوانین ثبت‌نام\n\nشرایط پرداخت، انصراف و حضور در کلاس‌ها در این صفحه توضیح داده می‌شود."),
]

# (title, slug, category slug, level, price, hours, magazine tag, summary, topics)
DEMO = [
    ("برنامه‌نویسی پایتون", "python", "programming", "beginner", 4800000, 40, "python",
     "از صفر تا نوشتن برنامه‌های واقعی، اتوماسیون و کار با داده.",
     ["مبانی زبان و ساختار داده", "توابع و ماژول‌ها", "کار با فایل و API", "پروژه پایانی"]),
    ("طراحی و توسعه وب", "web-development", "web", "beginner", 6500000, 60, "web",
     "HTML، CSS، جاوااسکریپت و ساخت سایت واکنش‌گرا.",
     ["HTML و CSS مدرن", "جاوااسکریپت", "طراحی واکنش‌گرا", "انتشار روی هاست"]),
    ("شبکه و +Network", "network-plus", "network", "beginner", 5500000, 50, "network",
     "مفاهیم شبکه، آدرس‌دهی، سوئیچینگ و مسیریابی.",
     ["مدل OSI و TCP/IP", "IP و Subnetting", "سوئیچ و روتر", "عیب‌یابی شبکه"]),
    ("امنیت و +Security", "security-plus", "security", "intermediate", 6000000, 45, "security",
     "مبانی امنیت اطلاعات، تهدیدها و روش‌های دفاعی.",
     ["تهدیدها و آسیب‌پذیری‌ها", "رمزنگاری پایه", "امن‌سازی سیستم‌ها", "پاسخ به رخداد"]),
    ("لینوکس و مدیریت سرور", "linux-server", "linux", "intermediate", 5000000, 40, "linux",
     "کار با ترمینال، مدیریت سرویس‌ها و راه‌اندازی سرور.",
     ["دستورات پایه", "کاربران و دسترسی‌ها", "وب‌سرور و سرویس‌ها", "شل‌اسکریپت"]),
]


FAQS = [
    ("آیا برای شروع دوره‌ها به پیش‌زمینه نیاز است؟", "دوره‌های مقدماتی نیاز به پیش‌زمینه ندارند؛ پیش‌نیاز هر دوره در صفحهٔ آن آمده است."),
    ("کلاس‌ها حضوری است یا آنلاین؟", "بسته به دورهٔ برگزاری، حضوری، آنلاین یا ترکیبی است؛ در صفحهٔ هر دوره مشخص شده."),
    ("گواهی پایان دوره صادر می‌شود؟", "بله، پس از گذراندن دوره و پروژهٔ پایانی گواهی پایان دوره صادر می‌شود."),
    ("روش پرداخت شهریه چگونه است؟", "پس از ثبت‌نام، همکاران ما برای هماهنگی پرداخت (نقدی یا اقساطی) با شما تماس می‌گیرند."),
]


class Command(BaseCommand):
    help = "Seed categories and pages; add sample courses with --demo."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="also create sample courses and an instructor")

    def handle(self, *args, **options):
        for order, (name, slug, icon) in enumerate(CATEGORIES):
            Category.objects.get_or_create(slug=slug, defaults={"name": name, "icon": icon, "order": order})
        for order, (title, slug, body) in enumerate(PAGES):
            Page.objects.get_or_create(slug=slug, defaults={"title": title, "body": body, "order": order})
        for order, (q, a) in enumerate(FAQS):
            Faq.objects.get_or_create(question=q, defaults={"answer": a, "order": order})
        if options["demo"]:
            teacher, _ = User.objects.get_or_create(
                username="teacher", defaults={"first_name": "مدرس", "last_name": "نمونه", "is_instructor": True})
            start = timezone.localdate() + datetime.timedelta(days=21)
            for title, slug, cat, level, price, hours, tag, summary, topics in DEMO:
                course, created = Course.objects.get_or_create(slug=slug, defaults={
                    "title": title, "category": Category.objects.get(slug=cat), "level": level,
                    "price": price, "duration_hours": hours, "magazine_tag": tag, "summary": summary,
                    "instructor": teacher, "is_published": True, "is_featured": slug == "python"})
                if created:
                    for i, t in enumerate(topics):
                        Topic.objects.create(course=course, title=t, order=i)
                    batch = Batch.objects.create(course=course, title="دوره بعدی", start_date=start,
                                                 schedule="شنبه و دوشنبه ۱۸ تا ۲۰")
                    for i, t in enumerate(topics):
                        Lesson.objects.create(course=course, title=f"جلسه {i + 1}: {t}", order=i, duration_minutes=90,
                                              body="محتوای این درس به‌زودی تکمیل می‌شود.")
                        when = timezone.make_aware(datetime.datetime.combine(start, datetime.time(18)) +
                                                   datetime.timedelta(days=7 * i))
                        ClassSession.objects.create(batch=batch, title=t, starts_at=when, place="کلاس ۱")
                    Announcement.objects.create(course=course, title="خوش آمدید", body="به دوره خوش آمدید! جزئیات برگزاری در همین بخش اطلاع‌رسانی می‌شود.")
        self.stdout.write(self.style.SUCCESS("Seeded."))
