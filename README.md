# آموزشگاه فناوری | IT Academy

سایت آموزشگاه IT، خواهرِ [مجله IT](https://github.com/AAli-gh/IT-magazine) و هم‌معماری با آن:

**استک:** Python · Django 5.2 · Django REST Framework · PostgreSQL · Redis · Tailwind CSS · HTMX · django-allauth (+2FA)

## امکانات
- دوره‌ها با دسته‌بندی، سطح، شهریه، سرفصل، مدرس و **دوره‌های برگزاری** (تاریخ، ظرفیت، حضوری/آنلاین)
- ثبت‌نام و مشاوره با HTMX (honeypot، محدودیت نرخ، اعتبارسنجی موبایل، ظرفیت)، مدیریت در پنل ادمین
- جستجو و فیلتر (با پیشنهاد زنده)، صفحه مدرسان، سؤالات متداول، فرم تماس، نظرات و امتیاز دانشجویان
- **پنل دانشجو** (`/panel/`): داشبورد، دوره‌های من با نوار پیشرفت، درس‌ها (ویدئو، متن، فایل ضمیمه خصوصی)، علامت‌گذاری درس انجام‌شده، برنامه کلاس‌ها، اطلاعیه‌ها (عمومی یا مخصوص یک دوره برگزاری)، ثبت‌نام‌ها با امکان لغو. محتوا فقط برای دانشجوی **تأییدشده** باز است؛ فایل‌ها خارج از `MEDIA_ROOT` (پوشه `private_media/`، قابل تغییر با `PRIVATE_MEDIA_ROOT`) نگه‌داری و فقط پس از بررسی دسترسی ارسال می‌شوند.
- ایمیل به آموزشگاه و دانشجو هنگام ثبت‌نام، و ایمیل تأیید وقتی ادمین ثبت‌نام را تأیید می‌کند
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
