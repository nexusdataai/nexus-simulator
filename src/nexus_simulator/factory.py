"""Composition root for the Nexus Simulator.

``build_simulator`` returns a fully-wired ``Simulator`` object. Adapters are
selected by inspecting ``SimulatorConfig``:

- ``redis_url`` set      → ``RedisCacheBackend(url)`` shared across all plugins
- ``redis_url`` unset    → ``InMemoryCacheBackend`` shared across all plugins
- per-plugin ``bucket``  set → ``S3StorageBackend`` for that plugin
- per-plugin ``bucket``  unset → ``InMemoryStorageBackend`` for that plugin

Plugins themselves land in phases 5–8; until then ``build_simulator`` wires
the adapters and returns a ``Simulator`` whose plugin attributes are all
``None`` and whose registry is empty (apart from any out-of-tree factories
registered via ``nexus_simulator.register_simulator``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .adapters import (
    InMemoryCacheBackend,
    InMemoryStorageBackend,
    RedisCacheBackend,
    S3StorageBackend,
)
from .config import SimulatorConfig
from .registry import SimulatorRegistry, get_registered_factories

if TYPE_CHECKING:
    from typing import Any

    from .contracts import CacheBackend, StorageBackend


@dataclass
class Simulator:
    """Composite returned from ``build_simulator``.

    Attributes are populated only for plugins enabled in the ``SimulatorConfig``
    that produced this instance; disabled plugins remain ``None``.

    The ``registry`` attribute is the authoritative way to look plugins up by
    name; the typed attributes are convenience for the common in-tree case.

    Plugin attributes are typed ``Any`` because the WXCC plugin
    (``WXCCSimulatorService``) does not inherit from ``BaseSimulator`` — its
    surface is task/recording oriented, not FDW oriented.
    """

    config: SimulatorConfig
    registry: SimulatorRegistry
    cache: CacheBackend

    wxcc: Any | None = None
    sfdc: Any | None = None
    oracle_erp: Any | None = None
    sap: Any | None = None
    external_source: Any | None = None
    tpm: Any | None = None
    sourcing: Any | None = None
    bss: Any | None = None
    nss: Any | None = None
    oss: Any | None = None
    telco_golden: Any | None = None
    telco_sources: Any | None = None


def _build_cache(config: SimulatorConfig) -> CacheBackend:
    if config.redis_url:
        return RedisCacheBackend(config.redis_url)
    return InMemoryCacheBackend()


def _build_storage(bucket: str, prefix: str, region: str | None) -> StorageBackend:
    if bucket:
        return S3StorageBackend(bucket=bucket, prefix=prefix, region=region)
    return InMemoryStorageBackend(bucket="memory", prefix=prefix)


def build_simulator(config: SimulatorConfig) -> Simulator:
    """Assemble and return the simulator.

    Args:
        config: Application-provided ``SimulatorConfig``. Each non-``None``
            per-plugin field activates that plugin (plugins land per phase
            5–8; today the registry is populated from any out-of-tree
            factories registered via ``register_simulator``).

    Returns:
        A ``Simulator`` whose ``registry`` holds one entry per enabled plugin
        and whose ``cache`` is the shared cache backend.
    """
    cache = _build_cache(config)
    registry = SimulatorRegistry()
    sim = Simulator(config=config, registry=registry, cache=cache)

    # In-tree plugins (Phases 5–8). Plugins are instantiated only when their
    # config is non-None; FDW-style plugins inherit BaseSimulator and need
    # the shared cache + a per-plugin StorageBackend wired in post-construction.

    if config.wxcc is not None:
        from .plugins.wxcc import WXCCSimulatorService

        wxcc = WXCCSimulatorService(
            bucket=config.wxcc.bucket,
            prefix=config.wxcc.prefix,
            region=config.region,
            org_id=config.wxcc.org_id,
            base_url=config.wxcc.base_url,
        )
        sim.wxcc = wxcc
        registry.register("wxcc", wxcc)

    if config.sfdc is not None:
        from .plugins.sfdc import SFDCSimulatorService

        sfdc = SFDCSimulatorService(bucket=config.sfdc.bucket, prefix=config.sfdc.prefix)
        sfdc._cache = cache
        sfdc._storage = _build_storage(config.sfdc.bucket, config.sfdc.prefix, config.region)
        sim.sfdc = sfdc
        registry.register("sfdc", sfdc)
        registry.register("simulator", sfdc)

    if config.oracle_erp is not None:
        from .plugins.oracle_erp import OracleERPSimulatorService

        oracle = OracleERPSimulatorService(
            bucket=config.oracle_erp.bucket, prefix=config.oracle_erp.prefix
        )
        oracle._cache = cache
        oracle._storage = _build_storage(
            config.oracle_erp.bucket, config.oracle_erp.prefix, config.region
        )
        sim.oracle_erp = oracle
        registry.register("oracle_erp", oracle)
        registry.register("oracle", oracle)

    if config.sap is not None:
        from .plugins.sap import SAPSimulatorService

        sap = SAPSimulatorService(bucket=config.sap.bucket, prefix=config.sap.prefix)
        sap._cache = cache
        sap._storage = _build_storage(config.sap.bucket, config.sap.prefix, config.region)
        sim.sap = sap
        registry.register("sap", sap)

    if config.external_source is not None:
        from .plugins.external_source import ExternalSourceSimulatorService

        ext = ExternalSourceSimulatorService(
            bucket=config.external_source.bucket, prefix=config.external_source.prefix
        )
        ext._cache = cache
        ext._storage = _build_storage(
            config.external_source.bucket,
            config.external_source.prefix,
            config.region,
        )
        sim.external_source = ext
        registry.register("external_source", ext)
        registry.register("external", ext)

    if config.tpm is not None:
        from .plugins.tpm import TPMSimulatorService

        tpm = TPMSimulatorService(bucket=config.tpm.bucket, prefix=config.tpm.prefix)
        tpm._cache = cache
        tpm._storage = _build_storage(config.tpm.bucket, config.tpm.prefix, config.region)
        sim.tpm = tpm
        registry.register("tpm", tpm)

    if config.sourcing is not None:
        from .plugins.sourcing import SourcingSimulatorService

        sourcing = SourcingSimulatorService(
            bucket=config.sourcing.bucket, prefix=config.sourcing.prefix
        )
        sourcing._cache = cache
        sourcing._storage = _build_storage(
            config.sourcing.bucket, config.sourcing.prefix, config.region
        )
        sim.sourcing = sourcing
        registry.register("sourcing", sourcing)

    if config.bss is not None:
        from .plugins.bss import BSSSimulatorService

        bss = BSSSimulatorService(bucket=config.bss.bucket, prefix=config.bss.prefix)
        bss._cache = cache
        bss._storage = _build_storage(config.bss.bucket, config.bss.prefix, config.region)
        sim.bss = bss
        registry.register("bss", bss)

    if config.nss is not None:
        from .plugins.nss import NSSSimulatorService

        nss = NSSSimulatorService(bucket=config.nss.bucket, prefix=config.nss.prefix)
        nss._cache = cache
        nss._storage = _build_storage(config.nss.bucket, config.nss.prefix, config.region)
        sim.nss = nss
        registry.register("nss", nss)

    if config.oss is not None:
        from .plugins.oss import OSSSimulatorService

        oss = OSSSimulatorService(bucket=config.oss.bucket, prefix=config.oss.prefix)
        oss._cache = cache
        oss._storage = _build_storage(config.oss.bucket, config.oss.prefix, config.region)
        sim.oss = oss
        registry.register("oss", oss)

    if config.telco_golden is not None:
        from .plugins.telco_golden import TelcoGoldenSimulatorService

        golden = TelcoGoldenSimulatorService(
            bucket=config.telco_golden.bucket, prefix=config.telco_golden.prefix
        )
        golden._cache = cache
        golden._storage = _build_storage(
            config.telco_golden.bucket, config.telco_golden.prefix, config.region
        )
        sim.telco_golden = golden
        registry.register("telco_golden", golden)

    if config.telco_sources is not None:
        from .plugins.telco_sources import TelcoSourcesSimulatorService

        ts = TelcoSourcesSimulatorService(
            bucket=config.telco_sources.bucket, prefix=config.telco_sources.prefix
        )
        ts._cache = cache
        ts._storage = _build_storage(
            config.telco_sources.bucket, config.telco_sources.prefix, config.region
        )
        sim.telco_sources = ts
        registry.register("telco_sources", ts)

    # Out-of-tree plugins registered via register_simulator() are wired last
    # so they cannot accidentally collide with the in-tree set on the same
    # iteration; ``SimulatorRegistry.register`` overwrites silently.
    for name, factory in get_registered_factories().items():
        instance = factory(config)
        if instance is not None:
            registry.register(name, instance)

    return sim
