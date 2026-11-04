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
    "backups",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        }
    }
LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Manila"
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
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
GOOGLE_DRIVE_CLIENT_ID = os.environ.get("GOOGLE_DRIVE_CLIENT_ID", GOOGLE_CLIENT_ID)
GOOGLE_DRIVE_CLIENT_SECRET = os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
GOOGLE_DRIVE_REDIRECT_URI = os.environ.get("GOOGLE_DRIVE_REDIRECT_URI", "")
GOOGLE_DRIVE_PICKER_API_KEY = os.environ.get("GOOGLE_DRIVE_PICKER_API_KEY", "")
GOOGLE_DRIVE_APP_ID = os.environ.get("GOOGLE_DRIVE_APP_ID", "")
# A separate stable Fernet key, shared by the web app and scheduled worker.
GOOGLE_DRIVE_TOKEN_KEY = os.environ.get("GOOGLE_DRIVE_TOKEN_KEY", "")
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
