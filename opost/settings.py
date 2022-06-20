"""Django settings for the opost project."""
import environ
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(BASE_DIR / ".env")
env = environ.Env(
    DEBUG=(bool, False),
    TIME_ZONE=(str, "UTC"),
    LANGUAGE_CODE=(str, "en-us"),
    STATIC_ROOT=(str, "staticfiles"),
    ALLOWED_HOSTS=([str], []),
)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",  # admin UI
    "django.contrib.admindocs",  # makes model documentation available through admin UI
    "django.contrib.auth",  # basic authentication pages/middleware/back end
    "django.contrib.contenttypes",  # support for generic model references; used e.g. by admin and auth
    "django.contrib.sessions",  # provides session middleware and back-end support
    "django.contrib.messages",  # implements a flash message system
    "django.contrib.sites",  # for domain name awareness and full URLs
    "django.contrib.staticfiles",  # collects and serves static assets stored throughout the project
    "django_extensions",  # extra command-line plugins and features
    "rest_framework",  # Django REST framework tools
]

INSTALLED_APPS += [
    "postapi",  # opost API layer
    "postweb",  # opost web front-end
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # Various request validators
    "django.contrib.sessions.middleware.SessionMiddleware",  # Creates and loads session state as needed
    "django.middleware.common.CommonMiddleware",  # Tweaks for perfectionists
    "django.middleware.csrf.CsrfViewMiddleware",  # CSRF protection
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Authentication checks
    "django.contrib.messages.middleware.MessageMiddleware",  # Tracks the display/dismiss state of messages
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # Use X-Frame-Options to avoid clickjacking
]

ROOT_URLCONF = "opost.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",  # adds debug setting(s) to context
                "django.template.context_processors.request",  # adds request to context
                "django.contrib.auth.context_processors.auth",  # adds user & perms to context
                "django.contrib.messages.context_processors.messages",  # adds messages to context
            ],
        },
    },
]

WSGI_APPLICATION = "opost.wsgi.application"

DATABASES = {"default": env.db_url()}

_PASSWORD_VALIDATORS = [
    "UserAttributeSimilarity",
    "MinimumLength",
    "CommonPassword",
    "NumericPassword",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{v}Validator"}
    for v in _PASSWORD_VALIDATORS
]

LANGUAGE_CODE = env("LANGUAGE_CODE")
TIME_ZONE = env("TIME_ZONE")
USE_TZ = True  # all Django-internal datetimes will be tz-aware

STATIC_ROOT = env("STATIC_ROOT")
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["mail_admins", "console"],
            "level": "ERROR",
            "propagate": True,
        },
        "postweb.services": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "postweb.views": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

ADMINS = [
    ("Opost Admin", "ods94043@yahoo.com"),
]
MANAGERS = ADMINS

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/web/login"

SITE_ID = 1  # for sites app

# Requests with this HTTP header/value are considered secure.
# Assumed to be passed along by a reverse proxy that is handling TLS for us.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    # By default, allow write access for currently logged in users,
    # and read access otherwise. This still allows any logged-in
    # user to edit anything, however, so be careful!
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly"
    ],
}

SERVICES = {
    "postapi": {
        "endpoint": "http://localhost:5100/postapi/",
        "user": "udapost",
        "password": "admin123",
    }
}
