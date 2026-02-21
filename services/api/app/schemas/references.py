"""Schemas for candidate professional references."""

from typing import Literal

from pydantic import BaseModel

RelationshipType = Literal[
    "Peer",
    "Co-Worker",
    "Supervisor",
    "Customer",
    "End-User",
    "Subordinate",
    "Manager",
    "Mentor",
    "Direct Report",
    "Other",
]


class ReferenceCreate(BaseModel):
    name: str
    title: str | None = None
    company: str
    phone: str
    email: str | None = None
    relationship: RelationshipType
    years_known: int | None = None
    notes: str | None = None


class ReferenceUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    relationship: RelationshipType | None = None
    years_known: int | None = None
    notes: str | None = None


class ReferenceResponse(BaseModel):
    id: str
    name: str
    title: str | None = None
    company: str
    phone: str
    email: str | None = None
    relationship: str
    years_known: int | None = None
    notes: str | None = None
    is_active: bool = True
