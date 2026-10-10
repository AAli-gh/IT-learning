# اتصال آموزشگاه به مجله IT

دو سایت هم‌معماری هستند (Django 5.2 · DRF · Tailwind · HTMX · allauth) و فقط از طریق API عمومی و فقط‌خواندنیِ هم با هم حرف می‌زنند؛ پایگاه داده جداست.

| جهت | چه چیزی | کجا |
|---|---|---|
| آموزشگاه ← مجله | مطالب مرتبط هر دوره و آخرین مطالب (در صفحه اصلی) | `core/magazine.py` ← `GET {MAGAZINE_API_URL}/articles/?tag=<slug>` |
| مجله ← آموزشگاه | دوره‌های مرتبط زیر هر مقاله | `docs/magazine-side/` ← `GET {SCHOOL_URL}/api/courses/?tag=<slug>` |
| ناوبری | لینک مجله در هدر/فوتر آموزشگاه | `templates/partials/{header,footer}.html` |

**کلید اتصال، تگ مشترک است:** فیلد «برچسب مجله» (`magazine_tag`) هر دوره باید با اسلاگ یک `Tag` در مجله یکی باشد (مثلاً `python`).

## راه‌اندازی سمت آموزشگاه
در `.env`: `MAGAZINE_URL` (و در صورت نیاز `MAGAZINE_API_URL`) و `API_CORS_ALLOWED_ORIGINS`.
اگر مجله در دسترس نباشد، کادرهای مجله خالی می‌شوند و بقیه صفحه سالم می‌ماند (خطا ۶۰ ثانیه کش می‌شود).

## راه‌اندازی سمت مجله (باید در ریپوی مجله انجام شود)
1. `docs/magazine-side/related_courses.py` را به `magazine/school.py` کپی کنید و `SCHOOL_URL` / `SCHOOL_API_URL` را به settings اضافه کنید (`requests` در requirements مجله نیست؛ اضافه‌اش کنید).
2. `related_courses.html` را به `templates/partials/` کپی کنید و طبق توضیح داخل فایل در `article_detail` اضافه کنید.
3. اختیاری: لینک «آموزشگاه» را به هدر مجله اضافه کنید.

## ورود یکسان (در این مرحله انجام نشده)
حساب‌ها جدا هستند. اگر بعداً SSO خواستید، ساده‌ترین راه: هر دو سایت را با یک OAuth provider مشترک (مثلاً گوگل/گیت‌هاب که allauth از قبل دارد) وصل کنید.
