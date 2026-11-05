"""Telco Golden Simulator admin REST API."""

from __future__ import annotations

from ._plugin_admin import make_admin_router

router = make_admin_router("telco_golden", "telco_golden", "Telco Golden Simulator")
