# آموزشگاه فناوری | IT Academy

سایت آموزشگاه IT، خواهرِ [مجله IT](https://github.com/AAli-gh/IT-magazine) و هم‌معماری با آن:

**استک:** Python · Django 5.2 · Django REST Framework · PostgreSQL · Redis · Tailwind CSS · HTMX · django-allauth (+2FA)

## امکانات
- دوره‌ها با دسته‌بندی، سطح، شهریه، سرفصل، مدرس و **دوره‌های برگزاری** (تاریخ، ظرفیت، حضوری/آنلاین)
- ثبت‌نام و مشاوره با HTMX (honeypot، محدودیت نرخ، اعتبارسنجی موبایل، ظرفیت)، مدیریت در پنل ادمین
- جستجو و فیلتر، پروفایل «ثبت‌نام‌های من»، صفحه مدرس
- **اتصال به مجله:** مطالب مرتبط هر دوره، آخرین مطالب مجله، و API دوره‌ها برای مجله (جزئیات: [docs/MAGAZINE_INTEGRATION.md](docs/MAGAZINE_INTEGRATION.md))
- API: `/api/courses/` (فیلتر `q`, `category`, `level`, `tag`)، `/api/categories/`
- SEO (sitemap، robots، OG)، تم تیره/روشن، پنل ادمین با 2FA، صفحات خطای اختصاصی، Sentry، Docker، CI

## راه‌اندازی (توسعه)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm ci && npm run build          # Tailwind + فونت/HTMX محلی (خروجی در static/ کامیت می‌شود)
python manage.py migrate
python manage.py seed_school --demo
python manage.py createsuperuser
MAGAZINE_URL=http://localhost:8000 python manage.py runserver 8001
```
یا `docker compose up` (آموزشگاه روی پورت 8001، مجله روی 8000).

تست: `python manage.py test` — تنظیمات: `.env.example`.
