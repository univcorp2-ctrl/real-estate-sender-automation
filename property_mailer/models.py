from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Property:
    property_id: str
    title: str
    price: float
    area: float
    address: str
    status: str
    updated_at: datetime
    detail_url: str
    brochure_url: str | None = None
    station: str | None = None
    layout: str | None = None
    notes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Recipient:
    email: str
    name: str | None = None
    consent: bool = True
    segment: str | None = None


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    code: str
    message: str
    subject_id: str | None = None


@dataclass(frozen=True)
class CampaignPlan:
    title: str
    subject: str
    preheader: str
    html: str
    text: str
    properties: list[Property]
    audience_key: str
    fingerprints: dict[str, str]
