import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "development-only-never-deploy"
if not DEBUG and SECRET_KEY == "development-only-never-deploy":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY for production")
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver"
).split(",")
INSTALLED_APPS = [
    "rest_framework",
    "django.contrib.admin",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "core",
    "people",
    "customers",
    "catalog",
    "jobs",
    "machines",
    "supplies",
    "events",
    "owner",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "core.middleware.ShopMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "core.middleware.context",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
    }
}
if os.environ.get("PGDATABASE"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["PGDATABASE"],
            "HOST": os.environ.get("PGHOST", "localhost"),
            "PORT": os.environ.get("PGPORT", "5432"),
            "USER": os.environ.get("PGUSER", "washday"),
            "PASSWORD": os.environ.get("PGPASSWORD", ""),
            "OPTIONS": {"connect_timeout": 5},
        }
    }
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Manila"
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
WHITENOISE_USE_FINDERS = DEBUG
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DEV_BRANCH_ID = os.environ.get("DEV_BRANCH_ID", "") if DEBUG else ""
DEV_STAFF_ID = os.environ.get("DEV_STAFF_ID", "") if DEBUG else ""

# Owner authentication is Google-only; credentials stay in the process environment.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_OAUTH_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
SOCIALACCOUNT_PROVIDERS = {
    "google": {"SCOPE": ["openid", "email", "profile"], "OAUTH_PKCE_ENABLED": True}
}
if GOOGLE_OAUTH_CONFIGURED:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
        "client_id": GOOGLE_CLIENT_ID,
        "secret": GOOGLE_CLIENT_SECRET,
        "key": "",
    }
ACCOUNT_ADAPTER = "owner.adapters.OwnerAccountAdapter"
SOCIALACCOUNT_ADAPTER = "owner.adapters.OwnerSocialAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SESSION_REMEMBER = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
LOGIN_URL = "owner_login"
LOGIN_REDIRECT_URL = "/owner/"
LOGOUT_REDIRECT_URL = "/owner/login/"
DEVICE_COOKIE_NAME = "washday_device"
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60
DEVICE_SETUP_ALLOW_BROWSER = (
    DEBUG and os.environ.get("DEVICE_SETUP_ALLOW_BROWSER", "0") == "1"
)
ENABLE_DEV_BRANCH_SCOPE = (
    DEBUG and os.environ.get("ENABLE_DEV_BRANCH_SCOPE", "0") == "1"
)

APP_ROLE = os.environ.get('APP_ROLE', 'cloud')
if APP_ROLE not in ('cloud', 'hub'):
    raise ImproperlyConfigured('APP_ROLE must be cloud or hub')
HUB_BRANCH_ID = os.environ.get('HUB_BRANCH_ID', '')
HUB_CLOUD_URL = os.environ.get('HUB_CLOUD_URL', '')
HUB_KEY = os.environ.get('HUB_KEY', '')
if APP_ROLE == 'hub':
    import uuid
    try:
        uuid.UUID(HUB_BRANCH_ID)
    except (ValueError, TypeError):
        raise ImproperlyConfigured('Set HUB_BRANCH_ID to the assigned branch UUID')
    if DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
        raise ImproperlyConfigured('Hub role requires local SQLite storage')
if not DEBUG and APP_ROLE == 'cloud' and DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Cloud production role requires PostgreSQL')
if not DEBUG and APP_ROLE == "cloud":
    for name in ("DJANGO_ALLOWED_HOSTS", "PGHOST", "PGUSER", "PGPASSWORD"):
        if not os.environ.get(name, "").strip():
            raise ImproperlyConfigured(f"Set {name} for cloud production")
    ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS if host.strip()]
    if "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Use explicit DJANGO_ALLOWED_HOSTS for production")
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    # Only the trusted HTTPS edge may reach the cloud container.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 3600
