"""Telco Customer Golden table — rolled up from BSS / NSS / OSS builders."""

from __future__ import annotations

import os
from typing import Any, Dict

from loguru import logger

from nexus_simulator.base.simulator import BaseSimulator as BaseSimulatorService
from nexus_simulator.plugins.bss.tables import build_bss_tables
from nexus_simulator.plugins.nss.tables import build_nss_tables
from nexus_simulator.plugins.oss.tables import build_oss_tables
from nexus_simulator.plugins.telco_seed_pools import get_telco_pools
from nexus_simulator.telco_golden.rollup import (
    SCHEMA_NAME,
    SERVER_NAME,
    TABLE_NAME,
    rollup_golden,
)

sim_logger = logger.bind(component="telco-golden-simulator")


class TelcoGoldenSimulatorService(BaseSimulatorService):
    SERVICE_NAME = "telco_golden"
    PRIORITY_TABLES = [TABLE_NAME]

    def __init__(self, bucket: str = "", prefix: str = ""):
        super().__init__(bucket, prefix)
        if not self.prefix:
            self.prefix = os.getenv("TELCO_GOLDEN_SIMULATOR_PREFIX", "telco-golden-simulator")
        if not self.bucket:
            self.bucket = os.getenv("TELCO_GOLDEN_SIMULATOR_BUCKET", "")

    async def seed_data(self) -> Dict[str, Any]:
        pools = get_telco_pools()
        sim_logger.info(
            "Seeding telco golden from BSS/NSS/OSS builders customers={}",
            len(pools.customer_ids),
        )
        # Deterministic rebuild (same pools) so golden does not depend on
        # sibling plugins already being loaded into Redis.
        bss = build_bss_tables(pools)
        nss = build_nss_tables(pools)
        oss = build_oss_tables(pools)
        rows = rollup_golden(bss, nss, oss)
        data_map = {TABLE_NAME: rows}

        if os.environ.get("TELCO_GOLDEN_WRITE_DUMPS", "false").lower() in ("1", "true", "yes"):
            try:
                from pathlib import Path

                from nexus_simulator.telco_golden.dump_writer import write_table_dump

                dumps = Path(os.environ.get("TELCO_DUMPS_DIR", "data/dumps"))
                write_table_dump(
                    dumps,
                    prefix=self.prefix or "telco-golden-simulator",
                    schema=SCHEMA_NAME,
                    server=SERVER_NAME,
                    tables=data_map,
                )
            except Exception:
                sim_logger.exception("Failed to write telco golden dumps")

        return await self._finalize_seed(SCHEMA_NAME, SERVER_NAME, data_map)
