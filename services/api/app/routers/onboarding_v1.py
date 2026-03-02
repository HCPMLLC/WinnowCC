from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.services.auth import get_current_user
from app.services.location_utils import normalize_city, normalize_state

router = APIRouter(prefix="/api/onboarding", tags=["onboarding-v1"])


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_state(session: Session, user_id: int) -> None:
    # Create onboarding_state row if missing
    session.execute(
        text(
            """
            INSERT INTO onboarding_state (user_id, current_step)
            VALUES (:uid, 'welcome')
            ON CONFLICT (user_id) DO NOTHING
            """
        ),
        {"uid": user_id},
    )


def _active_pref(session: Session, user_id: int) -> dict[str, Any] | None:
    row = (
        session.execute(
            text(
                """
            SELECT id, roles, locations, work_mode,
                   salary_min, salary_max, salary_currency,
                   employment_types, travel_percent_max,
                   active, created_at
            FROM candidate_preferences_v1
            WHERE user_id = :uid AND active = true
            ORDER BY id DESC
            LIMIT 1
            """
            ),
            {"uid": user_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _active_consent(session: Session, user_id: int) -> dict[str, Any] | None:
    row = (
        session.execute(
            text(
                """
            SELECT id, terms_version, terms_accepted_at,
                   mjass_consent, mjass_consent_at,
                   data_processing_consent,
                   data_processing_consent_at,
                   sms_consent, sms_consent_at,
                   application_mode,
                   active, created_at
            FROM consents
            WHERE user_id = :uid AND active = true
            ORDER BY id DESC
            LIMIT 1
            """
            ),
            {"uid": user_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


@router.get("/status")
def status(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _ensure_state(session, user.id)

    prefs = _active_pref(session, user.id)
    consent = _active_consent(session, user.id)

    missing = []
    if prefs is None:
        missing.append("preferences")
    if consent is None:
        missing.append("consent")

    st = (
        session.execute(
            text(
                "SELECT current_step, completed_at "
                "FROM onboarding_state "
                "WHERE user_id = :uid"
            ),
            {"uid": user.id},
        )
        .mappings()
        .first()
    )

    completed = bool(st and st["completed_at"]) and len(missing) == 0

    # Backfill: sync onboarding_completed_at on the user record if missing
    if completed:
        user_record = session.get(User, user.id)
        if user_record and not user_record.onboarding_completed_at:
            user_record.onboarding_completed_at = st["completed_at"]

    # Normalize step for UI
    current_step = (
        "done"
        if completed
        else (
            "preferences"
            if "preferences" in missing
            else (
                "consent"
                if "consent" in missing
                else (st["current_step"] if st else "welcome")
            )
        )
    )

    session.commit()
    return {"completed": completed, "current_step": current_step, "missing": missing}


@router.put("/preferences")
def put_preferences(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    """
    Expected JSON body (example):
    {
      "roles": ["DevOps Engineer"],
      "locations": [{"city":"Chicago","state":"IL","country":"US","radius_miles":50}],
      "work_mode": "hybrid",
      "salary_min": 130000,
      "salary_max": 180000,
      "salary_currency": "USD",
      "employment_types": ["full_time"],
      "travel_percent_max": 10
    }
    """
    _ensure_state(session, user.id)

    roles = payload.get("roles")
    locations = payload.get("locations")
    employment_types = payload.get("employment_types")
    work_mode = payload.get("work_mode", "any")

    if not isinstance(roles, list) or len([r for r in roles if str(r).strip()]) == 0:
        raise HTTPException(
            status_code=400, detail="roles must be a non-empty list of strings"
        )
    if not isinstance(locations, list) or len(locations) == 0:
        raise HTTPException(
            status_code=400, detail="locations must be a non-empty list"
        )
    if not isinstance(employment_types, list) or len(employment_types) == 0:
        raise HTTPException(
            status_code=400, detail="employment_types must be a non-empty list"
        )

    salary_min = payload.get("salary_min")
    salary_max = payload.get("salary_max")
    if (
        salary_min is not None
        and salary_max is not None
        and int(salary_min) > int(salary_max)
    ):
        raise HTTPException(
            status_code=400, detail="salary_min cannot be greater than salary_max"
        )

    # Normalize city/state in each location entry
    for loc in locations:
        if isinstance(loc, dict):
            if loc.get("city"):
                loc["city"] = normalize_city(loc["city"])
            if loc.get("state"):
                loc["state"] = normalize_state(loc["state"]) or loc["state"]

    # Deactivate old active row(s)
    session.execute(
        text(
            """
            UPDATE candidate_preferences_v1
            SET active = false
            WHERE user_id = :uid AND active = true
            """
        ),
        {"uid": user.id},
    )

    # Insert new preferences (store JSONB as string cast)
    session.execute(
        text(
            """
            INSERT INTO candidate_preferences_v1
              (user_id, roles, locations, work_mode,
               salary_min, salary_max, salary_currency,
               employment_types, travel_percent_max,
               active)
            VALUES
              (:uid, CAST(:roles AS jsonb),
               CAST(:locations AS jsonb), :work_mode,
               :salary_min, :salary_max,
               :salary_currency,
               CAST(:employment_types AS jsonb),
               :travel_percent_max, true)
            """
        ),
        {
            "uid": user.id,
            "roles": json.dumps(roles),
            "locations": json.dumps(locations),
            "work_mode": work_mode,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": payload.get("salary_currency", "USD"),
            "employment_types": json.dumps(employment_types),
            "travel_percent_max": payload.get("travel_percent_max"),
        },
    )

    # Advance onboarding step
    session.execute(
        text(
            """
            UPDATE onboarding_state
            SET current_step = 'consent', updated_at = now()
            WHERE user_id = :uid
            """
        ),
        {"uid": user.id},
    )

    session.commit()
    return {"ok": True}


@router.put("/consent")
def put_consent(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    """
    Expected JSON body (example):
    {
      "terms_version": "2026-01-30-v1",
      "accept_terms": true,
      "mjass_consent": true,
      "data_processing_consent": true,
      "application_mode": "review_required",
      "phone": "(210) 555-1234",
      "sms_consent": false
    }
    """
    _ensure_state(session, user.id)

    # Require preferences first
    prefs = _active_pref(session, user.id)
    if prefs is None:
        raise HTTPException(
            status_code=400, detail="Preferences must be completed before consent."
        )

    terms_version = payload.get("terms_version")
    accept_terms = payload.get("accept_terms")
    mjass_consent = payload.get("mjass_consent")
    data_processing_consent = payload.get("data_processing_consent")
    application_mode = payload.get("application_mode")

    # SMS opt-in fields
    raw_phone = payload.get("phone")
    sms_consent = bool(payload.get("sms_consent", False))
    phone_e164: str | None = None

    if raw_phone and str(raw_phone).strip():
        digits = re.sub(r"\D", "", str(raw_phone).strip())
        if len(digits) == 10:
            digits = "1" + digits
        if len(digits) == 11 and digits.startswith("1"):
            phone_e164 = "+" + digits
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number. Please enter a valid US phone number.",
            )

    if sms_consent and not phone_e164:
        raise HTTPException(
            status_code=400,
            detail="A phone number is required to opt in to SMS notifications.",
        )

    if not terms_version or not isinstance(terms_version, str):
        raise HTTPException(status_code=400, detail="terms_version is required")
    if accept_terms is not True:
        raise HTTPException(status_code=400, detail="accept_terms must be true")
    if data_processing_consent is not True:
        raise HTTPException(
            status_code=400, detail="data_processing_consent must be true"
        )
    if mjass_consent is not True:
        raise HTTPException(status_code=400, detail="mjass_consent must be true")
    if application_mode not in ("review_required", "auto_apply_limited"):
        raise HTTPException(
            status_code=400,
            detail="application_mode must be 'review_required' or 'auto_apply_limited'",
        )

    # Deactivate old active consent(s)
    session.execute(
        text(
            "UPDATE consents SET active = false WHERE user_id = :uid AND active = true"
        ),
        {"uid": user.id},
    )

    now = _utcnow()

    session.execute(
        text(
            """
            INSERT INTO consents
              (user_id, terms_version, terms_accepted_at,
               mjass_consent, mjass_consent_at,
               data_processing_consent, data_processing_consent_at,
               sms_consent, sms_consent_at,
               application_mode, active)
            VALUES
              (:uid, :terms_version, :terms_accepted_at,
               :mjass_consent, :mjass_consent_at,
               :data_processing_consent, :data_processing_consent_at,
               :sms_consent, :sms_consent_at,
               :application_mode, true)
            """
        ),
        {
            "uid": user.id,
            "terms_version": terms_version,
            "terms_accepted_at": now,
            "mjass_consent": True,
            "mjass_consent_at": now,
            "data_processing_consent": True,
            "data_processing_consent_at": now,
            "sms_consent": sms_consent,
            "sms_consent_at": now if sms_consent else None,
            "application_mode": application_mode,
        },
    )

    # Complete onboarding
    session.execute(
        text(
            """
            UPDATE onboarding_state
            SET current_step = 'done', completed_at = :completed_at, updated_at = now()
            WHERE user_id = :uid
            """
        ),
        {"uid": user.id, "completed_at": now},
    )

    # Also mark the user record so auth/me returns onboarding_complete=true
    user_record = session.get(User, user.id)
    if user_record and not user_record.onboarding_completed_at:
        user_record.onboarding_completed_at = now

    # Save phone number if provided
    if phone_e164 and user_record:
        user_record.phone = phone_e164

    session.commit()

    # Send 10DLC opt-in confirmation SMS (fire-and-forget, after commit)
    if sms_consent and phone_e164:
        try:
            from app.services.sms_service import send_opt_in_confirmation

            send_opt_in_confirmation(phone_e164)
        except Exception:
            pass  # Don't block onboarding if SMS fails

    return {"ok": True}


@router.get("/sms-consent-status")
def sms_consent_status(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    """Return current phone and SMS consent state for the authenticated user."""
    user_record = session.get(User, user.id)
    consent = _active_consent(session, user.id)

    session.commit()
    return {
        "phone": user_record.phone if user_record else None,
        "sms_consent": bool(consent and consent.get("sms_consent")),
        "sms_consent_at": consent.get("sms_consent_at") if consent else None,
    }


@router.put("/sms-consent")
def update_sms_consent(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    """Update phone + SMS consent from Settings without re-submitting all consents."""
    raw_phone = payload.get("phone")
    sms_consent = bool(payload.get("sms_consent", False))
    phone_e164: str | None = None

    if raw_phone and str(raw_phone).strip():
        digits = re.sub(r"\D", "", str(raw_phone).strip())
        if len(digits) == 10:
            digits = "1" + digits
        if len(digits) == 11 and digits.startswith("1"):
            phone_e164 = "+" + digits
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid phone number. Please enter a valid US phone number.",
            )

    if sms_consent and not phone_e164:
        raise HTTPException(
            status_code=400,
            detail="A phone number is required to opt in to SMS notifications.",
        )

    # If phone is cleared, force sms_consent off
    if not phone_e164:
        sms_consent = False

    now = _utcnow()

    # Update phone on user record
    user_record = session.get(User, user.id)
    if user_record:
        user_record.phone = phone_e164

    # Update sms_consent on active consent row
    session.execute(
        text(
            """
            UPDATE consents
            SET sms_consent = :sms_consent,
                sms_consent_at = :sms_consent_at
            WHERE user_id = :uid AND active = true
            """
        ),
        {
            "uid": user.id,
            "sms_consent": sms_consent,
            "sms_consent_at": now if sms_consent else None,
        },
    )

    session.commit()

    # Send 10DLC opt-in confirmation SMS (fire-and-forget, after commit)
    if sms_consent and phone_e164:
        try:
            from app.services.sms_service import send_opt_in_confirmation

            send_opt_in_confirmation(phone_e164)
        except Exception:
            pass  # Don't block settings save if SMS fails

    return {
        "ok": True,
        "phone": phone_e164,
        "sms_consent": sms_consent,
    }


@router.get("/summary")
def summary(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    _ensure_state(session, user.id)
    prefs = _active_pref(session, user.id)
    consent = _active_consent(session, user.id)

    st = (
        session.execute(
            text(
                "SELECT current_step, completed_at "
                "FROM onboarding_state "
                "WHERE user_id = :uid"
            ),
            {"uid": user.id},
        )
        .mappings()
        .first()
    )

    completed = (
        bool(st and st["completed_at"]) and prefs is not None and consent is not None
    )
    current_step = "done" if completed else (st["current_step"] if st else "welcome")

    session.commit()
    return {
        "completed": completed,
        "current_step": current_step,
        "preferences": prefs,
        "consent": consent,
        "trust_status": None,
    }
