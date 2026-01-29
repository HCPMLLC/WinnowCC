from fastapi import APIRouter, Depends

from app.services.auth import require_onboarded_user
from app.services.trust_gate import require_allowed_trust

router = APIRouter(prefix="/api/match", tags=["match"])


@router.post(
    "/run",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def run_match() -> dict:
    return {"status": "queued"}
