from django.db import models
from django.urls import reverse

from .rendering import render_markdown


class SEOFields(models.Model):
    meta_title = models.CharField("عنوان SEO", max_length=70, blank=True)
    meta_description = models.CharField("توضیحات SEO", max_length=160, blank=True)

    class Meta:
        abstract = True


class Page(SEOFields):
    """Static site pages: about us, contact, terms, ..."""

    title = models.CharField("عنوان", max_length=200)
    slug = models.SlugField("اسلاگ", unique=True, allow_unicode=True)
    body = models.TextField("متن (Markdown)")
    is_published = models.BooleanField("منتشر شده", default=True)
    show_in_footer = models.BooleanField("نمایش در فوتر", default=True)
    order = models.PositiveIntegerField("ترتیب", default=0)

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "صفحه"
        verbose_name_plural = "صفحات سایت"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:page", args=[self.slug])

    @property
    def body_html(self):
        return render_markdown(self.body)[0]


class SiteSettings(models.Model):
    """Singleton with site-wide settings editable from the admin panel."""

    site_name = models.CharField("نام سایت", max_length=100, blank=True,
                                 help_text="خالی = مقدار پیش‌فرض از تنظیمات سرور")
    site_description = models.CharField("توضیحات سایت (SEO)", max_length=300, blank=True)
    default_og_image = models.ImageField("تصویر پیش‌فرض اشتراک‌گذاری (OG)", upload_to="site/", blank=True)
    contact_email = models.EmailField("ایمیل تماس", blank=True)
    contact_phone = models.CharField("تلفن تماس", max_length=30, blank=True)
    address = models.CharField("آدرس آموزشگاه", max_length=300, blank=True)
    telegram_url = models.URLField("تلگرام", blank=True)
    instagram_url = models.URLField("اینستاگرام", blank=True)
    twitter_url = models.URLField("ایکس (توییتر)", blank=True)
    linkedin_url = models.URLField("لینکدین", blank=True)
    github_url = models.URLField("گیت‌هاب", blank=True)
    head_scripts = models.TextField(
        "کدهای head (آنالیتیکس)", blank=True,
        help_text="فقط کد مورد اعتماد وارد کنید؛ بدون تغییر در head همه صفحات قرار می‌گیرد.",
    )

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return "تنظیمات سایت"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        from django.core.cache import cache

        obj = cache.get("site_settings")
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set("site_settings", obj, 3600)
        return obj
