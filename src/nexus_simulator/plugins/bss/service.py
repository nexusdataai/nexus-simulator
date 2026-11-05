"""BSS (Business Support Systems) FDW simulator."""

from __future__ import annotations

import os
from typing import Any, Dict

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService
from nexus_simulator.plugins.bss.tables import build_bss_tables
from nexus_simulator.plugins.telco_seed_pools import get_telco_pools

sim_logger = logger.bind(component="bss-simulator")

SCHEMA = "bss_crm"
SERVER = "bss_simulator"


class BSSSimulatorService(BaseSimulatorService):
    SERVICE_NAME = "bss"
    PRIORITY_TABLES = [
        "Subscriber_Profile",
        "Invoice",
        "Payment",
        "Care_Interaction",
        "Campaign_Offer",
        "MNP_Port_Out_Request",
    ]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        if not self.prefix:
            self.prefix = os.getenv("BSS_SIMULATOR_PREFIX", "bss-simulator")
        if not self.bucket:
            self.bucket = os.getenv("BSS_SIMULATOR_BUCKET", "")

    async def seed_data(self) -> Dict[str, Any]:
        pools = get_telco_pools()
        sim_logger.info(
            "Seeding BSS simulator customers={} seed={}",
            len(pools.customer_ids),
            pools.seed,
        )
        data_map = build_bss_tables(pools)
        return await self._finalize_seed(SCHEMA, SERVER, data_map)
