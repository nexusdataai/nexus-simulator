"""Telco Sources plugin admin (seed/status)."""

from __future__ import annotations

from ._plugin_admin import make_admin_router

router = make_admin_router("telco_sources", "telco_sources", "Telco Sources Simulator")
