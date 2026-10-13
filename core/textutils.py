"""Persian-aware text normalisation and search helpers (no database-specific features, so it works on SQLite too)."""

import difflib
import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "ٱ": "ا",
                          "ؤ": "و"})
_STRIP = re.compile("[ً-ٰٟـ‌‍‎‏]")  # diacritics, tatweel, ZWNJ/ZWJ, bidi marks
_NON_WORD = re.compile(r"[^\w\s+#.]", re.UNICODE)

# Persian <-> English names of the same topic, so "پایتون" finds "Python" courses and vice versa.
SYNONYMS = [
    ("پایتون", "python"), ("جاوااسکریپت", "javascript"), ("جاوا اسکریپت", "javascript"), ("جاوا", "java"),
    ("لینوکس", "linux"), ("شبکه", "network"), ("امنیت", "security"), ("وب", "web"),
    ("هوش مصنوعی", "ai"), ("برنامه نویسی", "programming"), ("دواپس", "devops"), ("داکر", "docker"),
    ("دیتابیس", "database"), ("پایگاه داده", "database"), ("جنگو", "django"), ("ریکت", "react"),
]


def normalize(text):
    """Lower-case, unify Arabic/Persian letter variants and digits, drop diacritics and half-spaces."""
    text = (text or "").translate(_DIGITS).translate(_LETTERS)
    text = _STRIP.sub("", text).lower()
    text = _NON_WORD.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


_NORM_SYNONYMS = [(normalize(fa), normalize(en)) for fa, en in SYNONYMS]


def query_variants(query):
    """The normalised query plus versions with Persian/English synonyms swapped (at most a handful)."""
    base = normalize(query)
    variants = {base}
    for fa, en in _NORM_SYNONYMS:
        for variant in list(variants):
            if re.search(rf"(?<!\w){re.escape(fa)}(?!\w)", variant):
                variants.add(re.sub(rf"(?<!\w){re.escape(fa)}(?!\w)", en, variant))
            if re.search(rf"(?<!\w){re.escape(en)}(?!\w)", variant):
                variants.add(re.sub(rf"(?<!\w){re.escape(en)}(?!\w)", fa, variant))
    return sorted(v for v in variants if v)[:8]


def suggest_correction(query, vocabulary, cutoff=0.78):
    """Fix small typos ('pyton' -> 'python') word by word against a known vocabulary; ``None`` if nothing changes."""
    fixed, changed = [], False
    for word in normalize(query).split():
        if word in vocabulary or len(word) < 3:
            fixed.append(word)
            continue
        match = difflib.get_close_matches(word, vocabulary, n=1, cutoff=cutoff)
        fixed.append(match[0] if match else word)
        changed = changed or bool(match)
    return " ".join(fixed) if changed else None
