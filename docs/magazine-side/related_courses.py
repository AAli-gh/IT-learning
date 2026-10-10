"""Drop-in helper for the IT Magazine repo: courses of the school related to an article.

Copy to ``magazine/school.py``. Settings needed in the magazine's config/settings.py:

    SCHOOL_URL = os.environ.get("SCHOOL_URL", "https://academy.example.com").rstrip("/")
    SCHOOL_API_URL = os.environ.get("SCHOOL_API_URL", SCHOOL_URL + "/api").rstrip("/")

It uses the school's ``GET /api/courses/?tag=<slug>``: a course is related to an article when the
course's ``magazine_tag`` equals one of the article's tag slugs. Failures are cached briefly and
return an empty list, so a down school site never breaks article pages.
"""

import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def courses_for_tags(tag_slugs, limit=3):
    found, seen = [], set()
    for slug in tag_slugs:
        key = f"school:courses:{slug}"
        courses = cache.get(key)
        if courses is None:
            try:
                resp = requests.get(f"{settings.SCHOOL_API_URL}/courses/", params={"tag": slug}, timeout=3)
                resp.raise_for_status()
                courses = resp.json().get("results", [])
                cache.set(key, courses, 600)
            except (requests.RequestException, ValueError) as exc:
                logger.warning("School API unavailable: %s", exc)
                cache.set(key, [], 60)
                courses = []
        for course in courses:
            if course["slug"] not in seen:
                seen.add(course["slug"])
                found.append(course)
    return found[:limit]
