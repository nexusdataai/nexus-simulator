"""Normalize fixture API paths for vendor-api HTTP surface (strip /tmf-api prefix)."""

from __future__ import annotations


def normalize_vendor_route_path(path: str) -> str:
    """Return route suffix for ``/vendor-api/{path}`` (no leading slash).

    Fixture samples use ``/tmf-api/...`` for documentation; simulator serves
    the same payload under ``/api/v1/{{layer}}-simulator/vendor-api/...``.
    """
    if not path:
        return ""
    p = path.split("?")[0].strip()
    if p.startswith("/tmf-api"):
        p = p[len("/tmf-api") :].lstrip("/")
    else:
        p = p.lstrip("/")
    return p


def vendor_lookup_key(method: str, full_path: str) -> str:
    m = (method or "GET").upper()
    fp = full_path.lstrip("/")
    return f"{m} {fp}"
