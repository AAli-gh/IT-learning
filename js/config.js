// تنظیمات اتصال آموزشگاه به مجله IT — فقط همین فایل را ویرایش کنید.
window.SITE_CONFIG = {
  schoolName: "آموزشگاه آی‌تی",
  magazine: {
    name: "مجله IT",
    // آدرس سایت مجله
    url: "https://example.com/magazine",
    // آدرس دریافت آخرین مطالب. برای وردپرس:
    //   https://YOUR-MAGAZINE/wp-json/wp/v2/posts?per_page=3&_embed
    // اگر خالی باشد یا در دسترس نباشد، مطالب نمونه نمایش داده می‌شود.
    feedUrl: "",
    // الگوی لینک مطالب یک موضوع در مجله ({tag} با برچسب دوره جایگزین می‌شود)
    tagUrl: "https://example.com/magazine/tag/{tag}"
  }
};
