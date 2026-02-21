from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

# These imports MUST match your project.
# If imports fail, see the "If imports fail" section below.
from app.db.session import get_session
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/mjass", tags=["mjass"])


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DraftCreate(BaseModel):
    # Optional link to a match record (we don't assume any match table schema)
    match_id: int | None = None
    candidate_id: int | None = None

    job_url: str | None = None
    job_title: str | None = None
    company: str | None = None
    location: str | None = None
    source: str | None = None  # linkedin/indeed/company_site/etc

    application_mode: str = Field(
        default="review_required", pattern="^(review_required|auto_apply_limited)$"
    )

    # What will be submitted (keep flexible JSON)
    draft_payload: dict[str, Any] = Field(default_factory=dict)

    # Explainability payload: why matched, what signals, what will be used
    explain: dict[str, Any] = Field(default_factory=dict)


class DraftDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject|request_changes)$")
    note: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/drafts")
def list_drafts(
    status: str | None = None,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    params: dict[str, Any] = {"uid": user.id}
    where = "WHERE user_id = :uid"
    if status:
        where += " AND status = :status"
        params["status"] = status

    rows = (
        session.execute(
            text(
                f"""
            SELECT
              id, match_id, candidate_id,
              job_title, company, location, job_url, source,
              status, application_mode,
              created_at, updated_at, decided_at, submitted_at
            FROM mjass_application_drafts
            {where}
            ORDER BY created_at DESC
            LIMIT 200
            """
            ),
            params,
        )
        .mappings()
        .all()
    )

    return {"items": [dict(r) for r in rows]}


@router.post("/drafts")
def create_draft(
    body: DraftCreate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    now = _utcnow()

    # Insert draft
    draft_row = session.execute(
        text(
            """
            INSERT INTO mjass_application_drafts
              (user_id, candidate_id, match_id,
               job_url, job_title, company, location, source,
               status, application_mode,
               draft_payload, explain,
               created_at, updated_at)
            VALUES
              (:uid, :candidate_id, :match_id,
               :job_url, :job_title, :company, :location, :source,
               'draft', :application_mode,
               CAST(:draft_payload AS jsonb), CAST(:explain AS jsonb),
               :now, :now)
            RETURNING id
            """
        ),
        {
            "uid": user.id,
            "candidate_id": body.candidate_id,
            "match_id": body.match_id,
            "job_url": body.job_url,
            "job_title": body.job_title,
            "company": body.company,
            "location": body.location,
            "source": body.source,
            "application_mode": body.application_mode,
            "draft_payload": json.dumps(body.draft_payload),
            "explain": json.dumps(body.explain),
            "now": now,
        },
    ).scalar_one()

    # Insert audit event
    session.execute(
        text(
            """
            INSERT INTO mjass_application_events
              (draft_id, event_type, actor_type, actor_user_id, payload, created_at)
            VALUES
              (:draft_id, 'created', 'candidate', :uid, CAST(:payload AS jsonb), :now)
            """
        ),
        {
            "draft_id": int(draft_row),
            "uid": user.id,
            "payload": json.dumps({"note": "Draft created"}),
            "now": now,
        },
    )

    session.commit()
    return {"id": int(draft_row)}


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    draft = (
        session.execute(
            text(
                """
            SELECT
              id, user_id, candidate_id, match_id,
              job_url, job_title, company, location, source,
              status, application_mode,
              draft_payload, explain,
              created_at, updated_at, decided_at, submitted_at
            FROM mjass_application_drafts
            WHERE id = :id AND user_id = :uid
            """
            ),
            {"id": draft_id, "uid": user.id},
        )
        .mappings()
        .first()
    )

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    events = (
        session.execute(
            text(
                """
            SELECT id, draft_id, event_type, actor_type,
                   actor_user_id, payload, created_at
            FROM mjass_application_events
            WHERE draft_id = :id
            ORDER BY created_at ASC
            """
            ),
            {"id": draft_id},
        )
        .mappings()
        .all()
    )

    session.commit()
    return {"draft": dict(draft), "events": [dict(e) for e in events]}


@router.post("/drafts/{draft_id}/decision")
def decide_draft(
    draft_id: int,
    body: DraftDecision,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    # Ensure draft belongs to current user
    draft = (
        session.execute(
            text(
                "SELECT id, status FROM mjass_application_drafts"
                " WHERE id = :id AND user_id = :uid"
            ),
            {"id": draft_id, "uid": user.id},
        )
        .mappings()
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    # Basic state machine rules
    if draft["status"] in ("submitted",):
        raise HTTPException(status_code=400, detail="Cannot decide a submitted draft")

    now = _utcnow()

    if body.decision == "approve":
        new_status = "approved"
        event_type = "approved"
    elif body.decision == "reject":
        new_status = "rejected"
        event_type = "rejected"
    else:
        new_status = "changes_requested"
        event_type = "changes_requested"

    session.execute(
        text(
            """
            UPDATE mjass_application_drafts
            SET status = :status, decided_at = :now, updated_at = :now
            WHERE id = :id AND user_id = :uid
            """
        ),
        {"status": new_status, "now": now, "id": draft_id, "uid": user.id},
    )

    payload = dict(body.payload or {})
    if body.note:
        payload["note"] = body.note

    session.execute(
        text(
            """
            INSERT INTO mjass_application_events
              (draft_id, event_type, actor_type, actor_user_id, payload, created_at)
            VALUES
              (:draft_id, :event_type, 'candidate', :uid,
               CAST(:payload AS jsonb), :now)
            """
        ),
        {
            "draft_id": draft_id,
            "event_type": event_type,
            "uid": user.id,
            "payload": json.dumps(payload),
            "now": now,
        },
    )

    session.commit()
    return {"ok": True, "status": new_status}
