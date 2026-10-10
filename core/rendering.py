"""Markdown -> safe HTML rendering with a table of contents and code highlighting."""

import re

import bleach
import markdown
from markdown.extensions.toc import slugify_unicode

MARKDOWN_EXTENSIONS = ["extra", "sane_lists", "codehilite", "toc"]
MARKDOWN_CONFIG = {
    "codehilite": {"css_class": "highlight", "guess_lang": False},
    # Unicode-aware slugs so Persian headings get usable anchors.
    "toc": {"slugify": slugify_unicode, "toc_depth": "2-4"},
}

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "br", "hr", "pre", "span", "div", "img", "figure", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6", "table", "thead", "tbody", "tr", "th", "td",
    "del", "sup", "sub", "dl", "dt", "dd",
}
ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "dir"],
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "th": ["align"],
    "td": ["align"],
}

WORDS_PER_MINUTE = 200
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def render_markdown(text):
    """Return ``(html, toc)`` where toc is a flat list of ``{level, id, name}``."""
    md = markdown.Markdown(extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_CONFIG)
    html = md.convert(text or "")
    html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    return html, list(_flatten_toc(md.toc_tokens))


def _flatten_toc(tokens):
    for token in tokens:
        yield {"level": token["level"], "id": token["id"], "name": token["name"]}
        yield from _flatten_toc(token.get("children", []))


def estimate_reading_time(text):
    words = len(_WORD_RE.findall(text or ""))
    return max(1, round(words / WORDS_PER_MINUTE))
