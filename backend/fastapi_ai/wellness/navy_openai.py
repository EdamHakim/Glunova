"""OpenAI client for Navy — optional TLS overrides for corporate proxies."""
from __future__ import annotations

import os

import httpx
from openai import OpenAI

DEFAULT_NAVY_BASE_URL = "https://api.navy/v1"


def navy_base_url() -> str:
    return os.environ.get("OPENAI_BASE_URL", DEFAULT_NAVY_BASE_URL).rstrip("/")


def navy_http_verify() -> bool | str:
    raw = os.environ.get("OPENAI_SSL_VERIFY", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    bundle = (os.environ.get("OPENAI_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or "").strip()
    return bundle if bundle else True


def create_navy_openai_client(*, api_key: str | None = None) -> OpenAI:
    key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    verify = navy_http_verify()
    timeout_s = float(os.environ.get("OPENAI_HTTP_TIMEOUT", "120"))
    http_client = httpx.Client(verify=verify, timeout=timeout_s)
    return OpenAI(api_key=key, base_url=navy_base_url(), http_client=http_client)
