"""OSS (Operations Support Systems) FDW simulator."""

from __future__ import annotations

import os
from typing import Any, Dict

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService
from nexus_simulator.plugins.telco_backbone_mixin import TelcoBackboneMixin
from nexus_simulator.plugins.telco_seed_pools import get_telco_pools

sim_logger = logger.bind(component="oss-simulator")

SCHEMA = "oss_network"
SERVER = "oss_simulator"


class OSSSimulatorService(TelcoBackboneMixin, BaseSimulatorService):
    SERVICE_NAME = "oss"
    backbone_layer = "OSS"
    SERVER_NAME = SERVER
    LEGACY_SCHEMA = SCHEMA
    PRIORITY_TABLES = [
        "Cell_Site",
        "Network_Alarm",
        "Cell_KPI_Daily",
        "Trouble_Ticket",
        "Planned_Maintenance",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        if not self.prefix:
            self.prefix = os.getenv("OSS_SIMULATOR_PREFIX", "oss-simulator")
        if not self.bucket:
            self.bucket = os.getenv("OSS_SIMULATOR_BUCKET", "")

    async def seed_data(self) -> Dict[str, Any]:
        pools = get_telco_pools()
        sim_logger.info(
            "Seeding OSS simulator cells={}",
            len(pools.cell_ids),
        )
        return await self.generate_backbone(pools=pools, include_legacy_tables=True)
