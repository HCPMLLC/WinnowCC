from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.services.auth import get_current_user
from app.services.trust_scoring import TRUST_ALLOWED, get_latest_trust


def require_allowed_trust(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    trust = get_latest_trust(session, user.id)
    if trust is None or trust.status != TRUST_ALLOWED:
        raise HTTPException(
            status_code=403,
            detail="Account verification required before matching.",
        )
