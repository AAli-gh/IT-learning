"""
Django settings for the IT school project (آموزشگاه فناوری), the sister site of IT Magazine.

Configuration is read from environment variables so the same code runs in
development (SQLite fallback) and production (PostgreSQL via DATABASE_URL).
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Hosts without a process manager (e.g. PythonAnywhere) keep settings in BASE_DIR/.env;
# variables already set in the environment win.
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    pass
else:
    load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.google",
    "accounts",
    "courses",
    "panel",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.AdminMFAMiddleware",
    "core.middleware.MaintenanceModeMiddleware",
    "core.middleware.ApiCorsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL in production: DATABASE_URL=postgres://user:pass@host:5432/itmag
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "panel:dashboard"
LOGOUT_REDIRECT_URL = "courses:home"

# --- django-allauth: signup/login, email verification, password reset, social login ---
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = os.environ.get("ACCOUNT_EMAIL_VERIFICATION", "optional")
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https" if not env_bool("DJANGO_DEBUG", True) else "http"
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m/ip,5/5m/key", "signup": "10/h/ip"}
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_LOGIN_ON_GET = False

# Two-factor authentication (authenticator app + recovery codes).
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = os.environ.get("SITE_NAME", "IT Academy")
# Staff must enable 2FA before using the admin panel (on by default in production).
ADMIN_REQUIRE_MFA = env_bool("ADMIN_REQUIRE_MFA", not DEBUG)
# Show visitors the 503 "under maintenance" page (staff and the admin keep working).
MAINTENANCE_MODE = env_bool("MAINTENANCE_MODE", False)
# Path of the admin panel. Set a hard-to-guess value in production; /admin/ then shows the 404 page.
ADMIN_URL = os.environ.get("ADMIN_URL", "admin/").strip("/") + "/"

# OAuth apps are configured from the environment; a provider without credentials is hidden.
SOCIALACCOUNT_PROVIDERS = {}
if os.environ.get("GITHUB_CLIENT_ID"):
    SOCIALACCOUNT_PROVIDERS["github"] = {
        "APPS": [{"client_id": os.environ["GITHUB_CLIENT_ID"],
                  "secret": os.environ.get("GITHUB_CLIENT_SECRET", ""), "key": ""}],
        "SCOPE": ["user:email"],
    }
if os.environ.get("GOOGLE_CLIENT_ID"):
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APPS": [{"client_id": os.environ["GOOGLE_CLIENT_ID"],
                  "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""), "key": ""}],
        "SCOPE": ["profile", "email"],
    }

# --- Email: console in development, SMTP when EMAIL_HOST is set ---
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "آموزشگاه فناوری <no-reply@itacademy.local>")
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Cache: Redis when REDIS_URL is set, otherwise in-process memory ---
if os.environ.get("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                          "LOCATION": os.environ["REDIS_URL"], "TIMEOUT": 600}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "TIMEOUT": 600}}

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Student-only files (lesson attachments); never exposed through MEDIA_URL.
PRIVATE_MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}

# Site-wide branding / SEO defaults (exposed to templates via core.context_processors.site)
SITE_NAME = os.environ.get("SITE_NAME", "آموزشگاه فناوری")
SITE_NAME_EN = "IT Academy"
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")
SITE_DESCRIPTION = os.environ.get(
    "SITE_DESCRIPTION",
    "آموزشگاه فناوری؛ دوره‌های کاربردی برنامه‌نویسی، توسعه وب، شبکه، امنیت و هوش مصنوعی با پروژه عملی و مدرسان باتجربه",
)

# --- Uploads ---
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
MAX_IMAGE_UPLOAD_MB = int(os.environ.get("MAX_IMAGE_UPLOAD_MB", 10))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

# --- Error reporting ---
# Unhandled errors are emailed to ADMINS (e.g. "Ali:ali@example.com,ops@example.com")...
ADMINS = [
    tuple(item.split(":", 1)) if ":" in item else (item, item)
    for item in env_list("DJANGO_ADMINS")
]
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# ...and sent to Sentry (or a self-hosted GlitchTip) when SENTRY_DSN is set.
if os.environ.get("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
    )

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # HSTS preload is a long-term commitment; opt in deliberately, not by default.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Link to the sister site (IT Magazine) ---
# The school reads articles from the magazine's public API and exposes /api/courses/ for the magazine.
MAGAZINE_URL = os.environ.get("MAGAZINE_URL", "https://magazine.example.com").rstrip("/")
MAGAZINE_API_URL = os.environ.get("MAGAZINE_API_URL", MAGAZINE_URL + "/api").rstrip("/")
MAGAZINE_NAME = os.environ.get("MAGAZINE_NAME", "مجله فناوری")
MAGAZINE_TIMEOUT = float(os.environ.get("MAGAZINE_TIMEOUT", "3"))
MAGAZINE_CACHE_SECONDS = int(os.environ.get("MAGAZINE_CACHE_SECONDS", "600"))
# Origins allowed to call /api/ from a browser (the magazine's origin, for the "related courses" widget).
API_CORS_ALLOWED_ORIGINS = env_list("API_CORS_ALLOWED_ORIGINS", MAGAZINE_URL)
