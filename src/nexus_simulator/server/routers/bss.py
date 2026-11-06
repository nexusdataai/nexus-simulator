"""BSS Simulator admin REST API."""

from __future__ import annotations

from ._plugin_admin import make_admin_router
from .telco_backbone_layer import make_backbone_router

router = make_admin_router("bss", "bss", "BSS Simulator")
router.include_router(make_backbone_router("bss", "bss", "BSS Simulator"), tags=["BSS Simulator"])
