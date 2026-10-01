"""Share the same exact browser origin allowlist across CORS and CSRF checks."""
import os
from urllib.parse import urlsplit


def allowed_origins():
    candidates = [os.getenv("FRONTEND_URL", "http://localhost:3000"),
                  os.getenv("FRONTEND_URL_PRODUCTION", ""),
                  *os.getenv("ALLOWED_ORIGINS", "").split(","),
                  "http://127.0.0.1:3000"]
    origins = []
    for candidate in candidates:
        origin = candidate.strip().rstrip("/")
        if not origin:
            continue
        parts = urlsplit(origin)
        if (parts.scheme not in {"http", "https"} or not parts.netloc or "*" in parts.netloc
                or parts.username or parts.password or parts.path or parts.query or parts.fragment):
            raise ValueError("Frontend origins must be exact HTTP(S) origins without paths, credentials, or wildcards.")
        if origin not in origins:
            origins.append(origin)
    return origins
