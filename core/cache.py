"""A single "content version" number used to invalidate cached pages and indexes.

Any change to published content bumps the version, so every cache key that
includes it becomes stale at once (no need to track individual keys).
"""

from django.core.cache import cache

KEY = "content_version"


def content_version():
    version = cache.get(KEY)
    if version is None:
        version = 1
        cache.add(KEY, version, None)
    return version


def bump_content_version(*args, **kwargs):
    try:
        cache.incr(KEY)
    except ValueError:
        cache.set(KEY, 2, None)
    cache.delete("site_settings")
