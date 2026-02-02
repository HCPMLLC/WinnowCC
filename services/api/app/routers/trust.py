from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.trust import TrustReviewRequestResponse, TrustStatusResponse
from app.services.auth import get_current_user, require_onboarded_user
from app.services.trust_scoring import create_audit_entry, get_latest_trust

router = APIRouter(
    prefix="/api/trust",
    tags=["trust"],
    dependencies=[Depends(require_onboarded_user)],
)


@router.get("/me", response_model=TrustStatusResponse)
def get_my_trust_status(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrustStatusResponse:
    trust = get_latest_trust(session, user.id)
    if trust is None:
        return TrustStatusResponse(
            trust_status="allowed",
            score=0,
            user_message="Upload a resume to begin verification.",
        )
    return TrustStatusResponse(
        trust_status=trust.status, score=trust.score, user_message=trust.user_message
    )


@router.post("/me/request-review", response_model=TrustReviewRequestResponse)
def request_review(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrustReviewRequestResponse:
    trust = get_latest_trust(session, user.id)
    if trust is None:
        raise HTTPException(status_code=404, detail="No trust record found.")
    create_audit_entry(
        session,
        trust,
        actor_type="candidate",
        action="request_review",
        prev_status=trust.status,
        new_status=trust.status,
        details={"note": "Candidate requested review."},
    )
    return TrustReviewRequestResponse(status="received")
