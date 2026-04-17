import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Force project-local env values (backend/.env) to win over stale machine-level variables.
load_dotenv(BASE_DIR.parent / ".env", override=True)


def _parse_frontend_origins():
    origins = []
    raw = os.getenv("FRONTEND_ORIGINS", "")
    if raw:
        origins.extend([origin.strip() for origin in raw.split(",") if origin.strip()])

    legacy_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
    if legacy_origin:
        origins.append(legacy_origin)

    if not origins:
        origins = ["http://localhost:3000", "http://172.19.32.1:3000"]

    # Keep order stable while removing duplicates.
    return list(dict.fromkeys(origins))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"

_cookie_secure_raw = os.getenv("DJANGO_COOKIE_SECURE", "").strip().lower()
if _cookie_secure_raw in ("1", "true", "yes", "on"):
    COOKIE_SECURE = True
elif _cookie_secure_raw in ("0", "false", "no", "off"):
    COOKIE_SECURE = False
else:
    COOKIE_SECURE = not DEBUG

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "users",
    "clinical",
    "documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"
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
    "default": dj_database_url.parse(
        os.getenv("DATABASE_URL", "postgresql://glunova:glunova@localhost:5432/glunova"),
        conn_max_age=600,
    )
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# Documents OCR / storage (see documents_ocr_system_plan.md)
UPLOAD_MAX_MB = int(os.getenv("UPLOAD_MAX_MB", "10"))
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "medical-documents")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'\"")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_CHARS = int(os.getenv("LLM_MAX_CHARS", "50000"))
RXNORM_BASE_URL = os.getenv("RXNORM_BASE_URL", "https://rxnav.nlm.nih.gov/REST")
MEDICATION_VERIFY_TIMEOUT_SECONDS = int(os.getenv("MEDICATION_VERIFY_TIMEOUT_SECONDS", "5"))
MEDICATION_VERIFY_MIN_SCORE = int(os.getenv("MEDICATION_VERIFY_MIN_SCORE", "70"))
MEDICATION_VERIFY_AMBIGUITY_GAP = int(os.getenv("MEDICATION_VERIFY_AMBIGUITY_GAP", "8"))
MEDICATION_VERIFY_MAX_CANDIDATES = int(os.getenv("MEDICATION_VERIFY_MAX_CANDIDATES", "5"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.auth_authenticator.JWTCookieAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SHARED_SECRET", SECRET_KEY),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_PATH": "/",
    "AUTH_COOKIE_SAMESITE": "Lax",
    "AUTH_COOKIE_SECURE": COOKIE_SECURE,
    "REFRESH_COOKIE": "refresh_token",
    "REFRESH_COOKIE_HTTP_ONLY": True,
    "REFRESH_COOKIE_PATH": "/",
    "REFRESH_COOKIE_SAMESITE": "Lax",
    "REFRESH_COOKIE_SECURE": COOKIE_SECURE,
}

CORS_ALLOWED_ORIGINS = _parse_frontend_origins()
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = _parse_frontend_origins()
