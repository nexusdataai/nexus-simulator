"""OSS Simulator admin REST API."""

from __future__ import annotations

from ._plugin_admin import make_admin_router
from .telco_backbone_layer import make_backbone_router

router = make_admin_router("oss", "oss", "OSS Simulator")
router.include_router(make_backbone_router("oss", "oss", "OSS Simulator"), tags=["OSS Simulator"])
