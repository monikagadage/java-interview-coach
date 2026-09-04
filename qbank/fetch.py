"""Download a URL, caching the body on disk so re-runs are fast and offline.

macOS' system Python often can't verify TLS without ``certifi``; use it when
present (it's already an indirect dependency), fall back to the default
context otherwise.
"""
from __future__ import annotations

import hashlib
import ssl
import urllib.request
from pathlib import Path

_CACHE = Path(__file__).resolve().parent / ".cache"

try:
    import certifi

    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - only when certifi is missing
    _CTX = ssl.create_default_context()


def fetch(url: str, *, refresh: bool = False, timeout: int = 30) -> str:
    _CACHE.mkdir(exist_ok=True)
    cache_file = _CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".txt")
    if cache_file.exists() and not refresh:
        return cache_file.read_text(encoding="utf-8")

    req = urllib.request.Request(url, headers={"User-Agent": "qbank-build/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
        body = resp.read().decode("utf-8", "replace")
    cache_file.write_text(body, encoding="utf-8")
    return body
