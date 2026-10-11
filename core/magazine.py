"""Client for the sister site, the IT Magazine (its public REST API).

The magazine exposes ``/api/articles/?tag=<slug>`` and ``/api/categories/``. Every call here is
cached and fails soft: if the magazine is down or slow, pages render without the magazine boxes.
"""

import logging
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _get(path, params=None):
    if not settings.MAGAZINE_API_URL:  # link to the magazine not configured
        return []
    key = "mag:" + path + ":" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(f"{settings.MAGAZINE_API_URL}/{path.lstrip('/')}", params=params,
                            timeout=settings.MAGAZINE_TIMEOUT, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Magazine API unavailable (%s): %s", path, exc)
        # Cache the failure briefly so a dead magazine doesn't slow down every request.
        cache.set(key, [], 60)
        return []
    results = data.get("results", data) if isinstance(data, dict) else data
    cache.set(key, results, settings.MAGAZINE_CACHE_SECONDS)
    return results


def latest_articles(limit=3):
    return _get("articles/", {"page_size": limit})[:limit]


def articles_for_tag(tag, limit=3):
    """Articles of the magazine tagged ``tag``; empty when the course has no tag."""
    if not tag:
        return []
    return _get("articles/", {"tag": tag})[:limit]


def tag_url(tag):
    if not settings.MAGAZINE_URL:
        return ""
    return f"{settings.MAGAZINE_URL}/tag/{quote(tag)}/" if tag else settings.MAGAZINE_URL
