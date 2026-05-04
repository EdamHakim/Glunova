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
    "monitoring",
    "psychology",
    "screening",
    "nutrition",
    "kids",
    "carecircle",
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
# AI Service Integration — URL Django uses to call FastAPI (Groq, wellness plan, etc.)
_ai_url = (os.getenv("AI_SERVICE_URL") or "http://127.0.0.1:8001").strip().rstrip("/")
# backend/.env often uses http://fastapi_ai:8001 for Docker; that host does not resolve
# when Django runs on your machine (e.g. runserver + uvicorn). Inside a container,
# `/.dockerenv` exists — keep the Docker hostname in that case.
if "fastapi_ai" in _ai_url and not Path("/.dockerenv").exists():
    _ai_url = "http://127.0.0.1:8001"
AI_SERVICE_URL = _ai_url
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
FASTAPI_BASE_URL = (os.getenv("FASTAPI_BASE_URL") or AI_SERVICE_URL).strip().rstrip("/")
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
    "AUTH_COOKIE_SECURE": False,
    "REFRESH_COOKIE": "refresh_token",
    "REFRESH_COOKIE_HTTP_ONLY": True,
    "REFRESH_COOKIE_PATH": "/",
    "REFRESH_COOKIE_SAMESITE": "Lax",
    "REFRESH_COOKIE_SECURE": False,
}

CORS_ALLOWED_ORIGINS = _parse_frontend_origins()
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["content-type", "x-voice-clone-provider", "x-voice-id"]
CSRF_TRUSTED_ORIGINS = _parse_frontend_origins()
