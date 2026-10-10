// Markdown editor for the admin: toolbar shortcuts, image upload, live preview.
(function () {
  "use strict";

  function csrf() {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value;
  }

  function surround(ta, before, after, placeholder) {
    const { selectionStart: s, selectionEnd: e, value } = ta;
    const selected = value.slice(s, e) || placeholder;
    ta.setRangeText(before + selected + after, s, e, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input"));
  }

  function insertLine(ta, text) {
    const s = ta.selectionStart;
    const prefix = s > 0 && ta.value[s - 1] !== "\n" ? "\n" : "";
    ta.setRangeText(prefix + text, s, ta.selectionEnd, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input"));
  }

  const ACTIONS = {
    heading: (ta) => insertLine(ta, "## "),
    bold: (ta) => surround(ta, "**", "**", "متن پررنگ"),
    italic: (ta) => surround(ta, "*", "*", "متن کج"),
    link: (ta) => surround(ta, "[", "](https://)", "عنوان لینک"),
    code: (ta) => surround(ta, "\n```python\n", "\n```\n", "print('hello')"),
    list: (ta) => insertLine(ta, "- "),
    quote: (ta) => insertLine(ta, "> "),
    table: (ta) => insertLine(ta, "| ستون ۱ | ستون ۲ |\n|---|---|\n| مقدار | مقدار |\n"),
  };

  function init(root) {
    const ta = root.querySelector("textarea");
    const preview = root.querySelector(".md-preview");
    const panes = root.querySelector(".md-panes");
    const status = root.querySelector(".md-status");
    let timer = null;

    async function render() {
      const body = new FormData();
      body.append("text", ta.value);
      try {
        const res = await fetch(root.dataset.previewUrl, { method: "POST", body, headers: { "X-CSRFToken": csrf() } });
        preview.innerHTML = res.ok ? await res.text() : "<p>خطا در پیش‌نمایش</p>";
      } catch (e) {
        preview.innerHTML = "<p>خطا در اتصال</p>";
      }
    }

    root.querySelectorAll("[data-md]").forEach((btn) =>
      btn.addEventListener("click", () => ACTIONS[btn.dataset.md](ta)));

    root.querySelector("[data-md-toggle]").addEventListener("click", () => {
      const open = preview.hidden;
      preview.hidden = !open;
      panes.classList.toggle("split", open);
      if (open) render();
    });

    ta.addEventListener("input", () => {
      if (preview.hidden) return;
      clearTimeout(timer);
      timer = setTimeout(render, 400);
    });

    ta.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "b") { e.preventDefault(); ACTIONS.bold(ta); }
      if ((e.ctrlKey || e.metaKey) && e.key === "i") { e.preventDefault(); ACTIONS.italic(ta); }
    });

    async function upload(file) {
      status.textContent = "در حال آپلود...";
      const body = new FormData();
      body.append("image", file);
      const articleId = (location.pathname.match(/\/article\/(\d+)\/change/) || [])[1];
      if (articleId) body.append("article", articleId);
      try {
        const res = await fetch(root.dataset.uploadUrl, { method: "POST", body, headers: { "X-CSRFToken": csrf() } });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "upload failed");
        insertLine(ta, data.markdown + "\n");
        status.textContent = "✓ آپلود شد";
      } catch (e) {
        status.textContent = "خطا: " + e.message;
      }
    }

    root.querySelector("[data-md-upload]").addEventListener("change", (e) => {
      if (e.target.files[0]) upload(e.target.files[0]);
      e.target.value = "";
    });
    // Paste or drop images straight into the editor.
    ta.addEventListener("paste", (e) => {
      const file = [...(e.clipboardData || {}).files || []].find((f) => f.type.startsWith("image/"));
      if (file) { e.preventDefault(); upload(file); }
    });
    ta.addEventListener("drop", (e) => {
      const file = [...e.dataTransfer.files].find((f) => f.type.startsWith("image/"));
      if (file) { e.preventDefault(); upload(file); }
    });
  }

  document.addEventListener("DOMContentLoaded", () => document.querySelectorAll(".md-editor").forEach(init));
})();
