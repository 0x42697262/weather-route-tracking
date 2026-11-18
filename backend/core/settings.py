"""Django settings, built only from the validated environment in `core.env`."""

from pathlib import Path

from core.env import load_env
from core.keys import STATIC_ROOT_DIRNAME, STATIC_URL_PATH

APP_ENV = load_env()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = APP_ENV.django_secret_key.get_secret_value()
DEBUG = APP_ENV.django_debug
ALLOWED_HOSTS = [APP_ENV.public_host]
CSRF_TRUSTED_ORIGINS = [f"https://{APP_ENV.public_host}"]
ADMIN_URL = APP_ENV.admin_url

if APP_ENV.behind_proxy:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "rulesets",
]

MIDDLEWARE = [
    "core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "core.urls"
ASGI_APPLICATION = "core.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": APP_ENV.postgres_host,
        "PORT": APP_ENV.postgres_port,
        "NAME": APP_ENV.postgres_db,
        "USER": APP_ENV.postgres_user,
        "PASSWORD": APP_ENV.postgres_password.get_secret_value(),
        "OPTIONS": {"connect_timeout": APP_ENV.postgres_connect_timeout_seconds},
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": str(APP_ENV.redis_url),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = STATIC_URL_PATH
STATIC_ROOT = BASE_DIR / STATIC_ROOT_DIRNAME
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.json_logs.JsonFormatter"}},
    "filters": {"request_id": {"()": "core.request_context.RequestIdFilter"}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["stdout"], "level": APP_ENV.log_level},
    "loggers": {
        "uvicorn": {"handlers": ["stdout"], "level": APP_ENV.log_level, "propagate": False},
        "uvicorn.access": {"handlers": ["stdout"], "level": APP_ENV.log_level, "propagate": False},
        "httpx": {"level": "WARNING"},
    },
}
