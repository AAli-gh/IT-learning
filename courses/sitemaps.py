from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from core.models import Page

from .models import Category, Course


class CourseSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Course.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.all()


class PageSitemap(Sitemap):
    priority = 0.4

    def items(self):
        return Page.objects.filter(is_published=True)


class StaticSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["courses:home", "courses:list"]

    def location(self, item):
        return reverse(item)


sitemaps = {"static": StaticSitemap, "courses": CourseSitemap, "categories": CategorySitemap, "pages": PageSitemap}
