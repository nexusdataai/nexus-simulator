"""NSS (Network Switching Subsystem) FDW simulator."""

from __future__ import annotations

import os
from typing import Any, Dict

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService
from nexus_simulator.plugins.telco_backbone_mixin import TelcoBackboneMixin
from nexus_simulator.plugins.telco_seed_pools import get_telco_pools

sim_logger = logger.bind(component="nss-simulator")

SCHEMA = "nss_core"
SERVER = "nss_simulator"


class NSSSimulatorService(TelcoBackboneMixin, BaseSimulatorService):
    SERVICE_NAME = "nss"
    backbone_layer = "NSS"
    SERVER_NAME = SERVER
    LEGACY_SCHEMA = SCHEMA
    PRIORITY_TABLES = [
        "Usage_Daily_Agg",
        "Subscriber_QoE_Daily",
        "Location_Daily",
        "Policy_Throttle_Event",
        "Subscriber_Network_Profile",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        if not self.prefix:
            self.prefix = os.getenv("NSS_SIMULATOR_PREFIX", "nss-simulator")
        if not self.bucket:
            self.bucket = os.getenv("NSS_SIMULATOR_BUCKET", "")

    async def seed_data(self) -> Dict[str, Any]:
        pools = get_telco_pools()
        sim_logger.info(
            "Seeding NSS simulator customers={} history_days={}",
            len(pools.customer_ids),
            pools.history_days,
        )
        return await self.generate_backbone(pools=pools, include_legacy_tables=True)
