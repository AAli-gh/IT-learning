(function () {
  const cfg = window.SITE_CONFIG;
  const mag = cfg.magazine;
  const $ = (s) => document.querySelector(s);
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // لینک‌های مجله در سراسر سایت
  document.querySelectorAll("[data-magazine-link]").forEach((a) => (a.href = mag.url));
  document.querySelectorAll("[data-school-name]").forEach((e) => (e.textContent = cfg.schoolName));
  document.querySelectorAll("[data-year]").forEach((e) => (e.textContent = new Date().getFullYear()));

  const sampleArticles = [
    { title: "نقشه راه یادگیری برنامه‌نویسی در سال جدید", link: mag.url, excerpt: "از کجا شروع کنیم و چه مهارت‌هایی بازار کار را می‌سازند." },
    { title: "۵ اشتباه رایج در امنیت شبکه‌های کوچک", link: mag.url, excerpt: "مواردی که با چند تنظیم ساده قابل رفع هستند." },
    { title: "لینوکس برای مبتدیان: اولین سرور شما", link: mag.url, excerpt: "راه‌اندازی یک سرور ساده قدم‌به‌قدم." }
  ];

  async function loadArticles(url) {
    if (!url) return sampleArticles;
    try {
      const r = await fetch(url);
      if (!r.ok) throw 0;
      const posts = await r.json();
      // ساختار وردپرس
      return posts.map((p) => ({
        title: (p.title && p.title.rendered) || p.title,
        link: p.link,
        excerpt: ((p.excerpt && p.excerpt.rendered) || p.excerpt || "").replace(/<[^>]+>/g, "").slice(0, 140)
      }));
    } catch (e) {
      return sampleArticles;
    }
  }
  function articleCards(list) {
    return list.map((a) => `<a class="card" href="${esc(a.link)}" target="_blank" rel="noopener"><h3>${a.title}</h3><p>${esc(a.excerpt)}</p></a>`).join("");
  }

  // آخرین مطالب مجله (صفحه اصلی)
  const latest = $("#magazine-latest");
  if (latest) loadArticles(mag.feedUrl).then((l) => (latest.innerHTML = articleCards(l.slice(0, 3))));

  const getCourses = () => fetch("data/courses.json").then((r) => r.json());
  const courseCard = (c) => `<a class="card" href="course.html?id=${c.id}"><h3>${esc(c.title)}</h3><p>${esc(c.summary)}</p><div class="meta"><span class="tag">${esc(c.level)}</span><span>${esc(c.duration)}</span></div></a>`;

  // لیست دوره‌ها
  const list = $("#courses");
  if (list) getCourses().then((cs) => {
    const n = +list.dataset.limit || cs.length;
    list.innerHTML = cs.slice(0, n).map(courseCard).join("");
  });

  // صفحه جزئیات دوره + مطالب مرتبط مجله
  const detail = $("#course-detail");
  if (detail) getCourses().then(async (cs) => {
    const c = cs.find((x) => x.id === new URLSearchParams(location.search).get("id"));
    if (!c) { detail.innerHTML = "<p>دوره پیدا نشد.</p>"; return; }
    document.title = c.title + " | " + cfg.schoolName;
    const tagUrl = mag.tagUrl.replace("{tag}", encodeURIComponent(c.magazineTag));
    detail.innerHTML = `<h1>${esc(c.title)}</h1><p class="muted">${esc(c.summary)}</p>
      <div class="meta"><span class="tag">${esc(c.level)}</span><span>مدت: ${esc(c.duration)}</span><span>شهریه: ${esc(c.price)}</span></div>
      <h2 style="margin-top:28px">سرفصل‌ها</h2><ul class="topics">${c.topics.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
      <p><a class="btn alt" href="index.html#contact">ثبت‌نام / مشاوره</a></p>`;
    const rel = $("#related");
    if (rel) {
      const feed = mag.feedUrl ? mag.feedUrl + (mag.feedUrl.includes("?") ? "&" : "?") + "search=" + encodeURIComponent(c.magazineTag) : "";
      rel.innerHTML = articleCards((await loadArticles(feed)).slice(0, 3));
      $("#related-all").href = tagUrl;
    }
  });
})();
