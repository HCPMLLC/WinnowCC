from fastapi import APIRouter

from app.db.session import check_connection

router = APIRouter()


@router.get("/ready")
def ready() -> dict:
    try:
        check_connection()
    except Exception as exc:
        return {"status": "degraded", "reason": str(exc)}
    return {"status": "ok"}
