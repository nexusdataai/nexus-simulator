"""SimulatorConfig — application-provided settings for the simulator library.

The library never reads environment variables or SSM/Secrets by itself. Host
applications build a ``SimulatorConfig`` from whichever source they prefer and
pass it to ``nexus_simulator.factory.build_simulator``.

Each plugin has its own dataclass. ``None`` for a plugin field means that
plugin is disabled and will not be instantiated by ``build_simulator``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WXCCPluginConfig:
    """WXCC simulator settings.

    Mirrors the env-var contract used today by
    ``nexus-backend/src/services/wxcc_simulator_service.py``.
    """

    bucket: str = ""
    prefix: str = "wxcc-simulator"
    org_id: str = "sim-org-001"
    base_url: str = "http://localhost:8000"
    bearer_token: str = "test-token-12345"
    enabled: bool = True


@dataclass(frozen=True)
class SFDCPluginConfig:
    """Salesforce simulator settings (FDW-style)."""

    bucket: str = ""
    prefix: str = "sfdc-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class OracleERPPluginConfig:
    """Oracle ERP simulator settings (FDW-style)."""

    bucket: str = ""
    prefix: str = "oracle-erp-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class SAPPluginConfig:
    """SAP simulator settings (FDW-style)."""

    bucket: str = ""
    prefix: str = "sap-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class ExternalSourcePluginConfig:
    """External Source simulator settings (Google Drive / Social Listening / Uploads)."""

    bucket: str = ""
    prefix: str = "external-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class TPMPluginConfig:
    """Trade CPQ (sell-side) simulator settings."""

    bucket: str = ""
    prefix: str = "tpm-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class SourcingPluginConfig:
    """Sourcing CPQ (buy-side) simulator settings."""

    bucket: str = ""
    prefix: str = "sourcing-simulator"
    enabled: bool = True


@dataclass(frozen=True)
class SimulatorConfig:
    """Runtime settings required to assemble the simulator.

    Per-plugin configs default to ``None``; passing a plugin config enables it.
    Adapter-specific settings (e.g. region, role ARN, Redis URL) are top-level
    so they can be shared across all enabled plugins.
    """

    region: str | None = None
    role_arn: str | None = None
    redis_url: str | None = None

    wxcc: WXCCPluginConfig | None = None
    sfdc: SFDCPluginConfig | None = None
    oracle_erp: OracleERPPluginConfig | None = None
    sap: SAPPluginConfig | None = None
    external_source: ExternalSourcePluginConfig | None = None
    tpm: TPMPluginConfig | None = None
    sourcing: SourcingPluginConfig | None = None

    extras: dict = field(default_factory=dict)
