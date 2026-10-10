// Small vanilla-JS enhancements: theme toggle, dropdown, reading progress,
// TOC highlighting, copy-code buttons and native sharing.
(function () {
  "use strict";

  // Theme toggle
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dark = document.documentElement.classList.toggle("dark");
      try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) {}
    });
  });

  // Dropdowns
  document.querySelectorAll("[data-dropdown]").forEach((root) => {
    const toggle = root.querySelector("[data-dropdown-toggle]");
    const menu = root.querySelector("[data-dropdown-menu]");
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = menu.classList.toggle("hidden") === false;
      toggle.setAttribute("aria-expanded", String(open));
    });
    const close = () => {
      menu.classList.add("hidden");
      toggle.setAttribute("aria-expanded", "false");
    };
    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  });

  // Close the header search suggestions when clicking elsewhere / pressing Escape
  const suggestForm = document.querySelector("[data-suggest]");
  if (suggestForm) {
    const box = suggestForm.querySelector("#search-suggest");
    document.addEventListener("click", (e) => { if (!suggestForm.contains(e.target)) box.innerHTML = ""; });
    suggestForm.addEventListener("keydown", (e) => { if (e.key === "Escape") box.innerHTML = ""; });
  }

  // Reading progress bar
  const progress = document.getElementById("reading-progress");
  const body = document.querySelector("[data-article-body]");
  if (progress && body) {
    const update = () => {
      const rect = body.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const pct = total > 0 ? Math.min(100, Math.max(0, (-rect.top / total) * 100)) : 100;
      progress.style.width = pct + "%";
    };
    document.addEventListener("scroll", update, { passive: true });
    update();
  }

  // Highlight current TOC entry
  const headings = document.querySelectorAll(".article-body h2[id], .article-body h3[id], .article-body h4[id]");
  if (headings.length && "IntersectionObserver" in window) {
    const links = document.querySelectorAll("[data-toc] a");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((a) => a.classList.toggle("active", decodeURIComponent(a.hash.slice(1)) === entry.target.id));
      });
    }, { rootMargin: "0px 0px -70% 0px" });
    headings.forEach((h) => observer.observe(h));
  }

  // Copy buttons for code blocks
  document.querySelectorAll(".article-body .highlight").forEach((block) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "Copy";
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(block.querySelector("pre").innerText);
        btn.textContent = "Copied ✓";
      } catch (e) {
        btn.textContent = "Error";
      }
      setTimeout(() => (btn.textContent = "Copy"), 1500);
    });
    block.appendChild(btn);
  });

  // Share: native share sheet when available, else copy the link.
  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const data = { title: btn.dataset.title, url: btn.dataset.url };
      try {
        if (navigator.share) {
          await navigator.share(data);
        } else {
          await navigator.clipboard.writeText(data.url);
          btn.textContent = "✓ لینک کپی شد";
        }
      } catch (e) { /* user cancelled */ }
    });
  });

  // Hero slider: autoplay every 6s, pauses on hover/focus and when the tab is hidden.
  document.querySelectorAll("[data-slider]").forEach((root) => {
    const slides = [...root.querySelectorAll("[data-slide]")];
    const dots = [...root.querySelectorAll("[data-dot]")];
    if (slides.length < 2) return;
    let index = 0, timer = null;
    const show = (i) => {
      index = (i + slides.length) % slides.length;
      slides.forEach((s, n) => { s.classList.toggle("is-active", n === index); s.toggleAttribute("inert", n !== index); });
      dots.forEach((d, n) => { d.classList.toggle("is-active", n === index); d.setAttribute("aria-current", String(n === index)); });
    };
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = () => { if (!reduced) { clearInterval(timer); timer = setInterval(() => !document.hidden && show(index + 1), 6000); } };
    const stop = () => clearInterval(timer);
    root.querySelector("[data-next]")?.addEventListener("click", () => { show(index + 1); start(); });
    root.querySelector("[data-prev]")?.addEventListener("click", () => { show(index - 1); start(); });
    dots.forEach((d, n) => d.addEventListener("click", () => { show(n); start(); }));
    root.addEventListener("mouseenter", stop);
    root.addEventListener("mouseleave", start);
    root.addEventListener("focusin", stop);
    show(0);
    start();
  });
})();
