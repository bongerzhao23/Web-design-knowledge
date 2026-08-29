from __future__ import annotations

import posixpath
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_KEYS = {"gclid", "fbclid"}


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL credentials are not allowed")

    host = parsed.hostname.rstrip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        raise ValueError("URL host is empty")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL port is invalid") from exc
    netloc = host if port in {None, 80, 443} else f"{host}:{port}"

    raw_path = parsed.path or "/"
    path = posixpath.normpath(raw_path)
    if not path.startswith("/"):
        path = "/" + path
    if raw_path.endswith("/") and path != "/":
        path += "/"

    query_pairs = []
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in _TRACKING_KEYS:
            continue
        query_pairs.append((key, item))
    query = urlencode(sorted(query_pairs))
    return urlunsplit(("https", netloc, path, query, ""))


def domain_slug(value: str) -> str:
    host = urlsplit(canonicalize_url(value)).hostname
    if host is None:
        raise ValueError("URL host is empty")
    slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    if not slug:
        raise ValueError("URL host cannot produce a slug")
    return slug
