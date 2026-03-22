from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    # Anonymous / lowest tier (no JWT or explicit public token).
    PUBLIC = "public"
    # Department JWT roles — peer visibility is enforced in adapters.
    DEPT_PUBLIC_HEALTH = "dept_public_health"
    DEPT_ENGINEERING = "dept_engineering"
    DEPT_PLANNING = "dept_planning"


class TokenRequest(BaseModel):
    """`role` is a string so clients are not blocked by stale OpenAPI enum caches."""

    role: str = "public"
    sub: str = "demo-user"


class CatalogEntry(BaseModel):
    dataset_id: str
    department: str
    title: str
    description: str
    endpoint: str
    access_levels: list[str]
    common_schema_fields: list[str]
    update_cadence: str


class AuditEntry(BaseModel):
    ts: str
    role: str
    action: str
    resource: str
    detail: str | None = None


class UnifiedEvent(BaseModel):
    """NGSI-LD–inspired municipal interchange record (demo subset)."""

    id: str
    event_type: str = Field(..., description="medical | infra | zone")
    source_department: str
    temporal: dict[str, Any] = Field(default_factory=dict)
    spatial: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    access_level: str
    pii_stripped: bool = True
