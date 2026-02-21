"""Account deletion service — permanently removes all user data."""

from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.usage_counter import UsageCounter
from app.services.cascade_delete import cascade_delete_user

logger = logging.getLogger(__name__)


def delete_user_account(user_id: int, db: Session) -> dict:
    """Permanently delete all data for a user.

    Delegates to ``cascade_delete_user`` which handles the full
    FK-safe deletion order and file cleanup.  We additionally
    delete ``usage_counters`` which are not covered there.

    Returns a summary dict with the outcome.
    """
    # Usage counters (has CASCADE FK but delete explicitly to be safe)
    usage_count = db.execute(
        delete(UsageCounter).where(UsageCounter.user_id == user_id)
    ).rowcount

    existed = cascade_delete_user(db, user_id)

    db.commit()

    summary = {
        "user_deleted": existed,
        "usage_counters": usage_count,
    }
    logger.info("Deleted account for user_id=%s: %s", user_id, summary)
    return summary
