"""Pydantic/dataclass models for telco source profiles and artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Layer = Literal["BSS", "OSS", "NSS"]
Delivery = Literal["Table", "File", "API", "Stream"]


@dataclass
class TelcoProductOffer:
    offer_id: str
    name: str
    layer: str = "bss"
    offer_type: str = "plan"
    price_sar: float = 0.0
    recurrence: str = "monthly"
    data_gb: Optional[float] = None
    linked_systems: List[str] = field(default_factory=list)


@dataclass
class SystemConfig:
    layer: Layer
    system_key: str
    enabled: bool = True
    vendor: str = "H"
    deliveries: List[Delivery] = field(default_factory=list)


@dataclass
class TelcoSourceProfile:
    profile_id: str = "default"
    vendor_defaults: Dict[str, str] = field(
        default_factory=lambda: {"bss": "H", "oss": "E", "nss": "H"}
    )
    systems: List[SystemConfig] = field(default_factory=list)
    products: List[TelcoProductOffer] = field(default_factory=list)
    preset: Optional[str] = None  # e.g. "zain"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "vendor_defaults": dict(self.vendor_defaults),
            "preset": self.preset,
            "systems": [
                {
                    "layer": s.layer,
                    "system_key": s.system_key,
                    "enabled": s.enabled,
                    "vendor": s.vendor,
                    "deliveries": list(s.deliveries),
                }
                for s in self.systems
            ],
            "products": [
                {
                    "offer_id": p.offer_id,
                    "name": p.name,
                    "layer": p.layer,
                    "offer_type": p.offer_type,
                    "price_sar": p.price_sar,
                    "recurrence": p.recurrence,
                    "data_gb": p.data_gb,
                    "linked_systems": list(p.linked_systems),
                }
                for p in self.products
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelcoSourceProfile:
        systems = [
            SystemConfig(
                layer=s["layer"],
                system_key=s["system_key"],
                enabled=s.get("enabled", True),
                vendor=s.get("vendor", "H"),
                deliveries=list(s.get("deliveries") or []),
            )
            for s in data.get("systems") or []
        ]
        products = [
            TelcoProductOffer(
                offer_id=p["offer_id"],
                name=p["name"],
                layer=p.get("layer", "bss"),
                offer_type=p.get("offer_type", "plan"),
                price_sar=float(p.get("price_sar") or 0),
                recurrence=p.get("recurrence", "monthly"),
                data_gb=p.get("data_gb"),
                linked_systems=list(p.get("linked_systems") or []),
            )
            for p in data.get("products") or []
        ]
        return cls(
            profile_id=data.get("profile_id") or "default",
            vendor_defaults=dict(data.get("vendor_defaults") or {"bss": "H", "oss": "E", "nss": "H"}),
            systems=systems,
            products=products,
            preset=data.get("preset"),
        )


@dataclass
class Artifact:
    system_key: str
    layer: Layer
    delivery: Delivery
    name: str
    mime: str = "text/plain"
    content: str | None = None
    table_name: str | None = None
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    api_method: str | None = None
    api_path: str | None = None
    api_body: dict[str, Any] | None = None
    stream_topic: str | None = None
    stream_events: List[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_key": self.system_key,
            "layer": self.layer,
            "delivery": self.delivery,
            "name": self.name,
            "mime": self.mime,
            "content": self.content,
            "table_name": self.table_name,
            "columns": self.columns,
            "rows": self.rows,
            "api_method": self.api_method,
            "api_path": self.api_path,
            "api_body": self.api_body,
            "stream_topic": self.stream_topic,
            "stream_events": self.stream_events,
            "metadata": self.metadata,
            "file_path": self.file_path,
        }


@dataclass
class ArtifactBundle:
    generated_at: str
    profile_id: str
    artifacts: List[Artifact] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "profile_id": self.profile_id,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "lineage": self.lineage,
        }
