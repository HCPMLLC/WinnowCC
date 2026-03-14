from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.sieve_suggestion import (
    SuggestionActionResponse,
    SuggestionApproveRequest,
    SuggestionCreateRequest,
    SuggestionListResponse,
    SuggestionRejectRequest,
    SuggestionResponse,
)
from app.services.auth import require_admin_user
from app.services.sieve_suggestions import (
    approve_suggestion,
    create_suggestion,
    delete_suggestion,
    generate_prompt,
    get_suggestion,
    get_summary_counts,
    list_suggestions,
    reject_suggestion,
    score_suggestion,
)

router = APIRouter(prefix="/api/admin/suggestions", tags=["admin-suggestions"])


def _to_response(s) -> SuggestionResponse:
    return SuggestionResponse(
        id=s.id,
        title=s.title,
        description=s.description,
        category=s.category,
        source=s.source,
        source_user_id=s.source_user_id,
        conversation_snippet=s.conversation_snippet,
        alignment_score=s.alignment_score,
        value_score=s.value_score,
        cost_estimate=s.cost_estimate,
        cost_score=s.cost_score,
        priority_score=s.priority_score,
        priority_label=s.priority_label,
        scoring_rationale=s.scoring_rationale,
        implementation_prompt=s.implementation_prompt,
        prompt_file_path=s.prompt_file_path,
        status=s.status,
        admin_notes=s.admin_notes,
        approved_at=s.approved_at,
        rejected_at=s.rejected_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=SuggestionListResponse)
def list_all_suggestions(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionListResponse:
    suggestions = list_suggestions(
        session, status=status, priority=priority, category=category
    )
    counts = get_summary_counts(session)
    return SuggestionListResponse(
        suggestions=[_to_response(s) for s in suggestions],
        **counts,
    )


@router.post("", response_model=SuggestionResponse)
def create_new_suggestion(
    payload: SuggestionCreateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionResponse:
    s = create_suggestion(
        session=session,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        source="admin_manual",
    )
    return _to_response(s)


@router.get("/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion_detail(
    suggestion_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionResponse:
    s = get_suggestion(session, suggestion_id)
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return _to_response(s)


@router.post("/{suggestion_id}/score", response_model=SuggestionResponse)
def trigger_scoring(
    suggestion_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionResponse:
    s = score_suggestion(session, suggestion_id)
    if not s:
        raise HTTPException(status_code=400, detail="Could not score suggestion.")
    return _to_response(s)


@router.post("/{suggestion_id}/generate-prompt", response_model=SuggestionResponse)
def trigger_prompt_generation(
    suggestion_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionResponse:
    s = generate_prompt(session, suggestion_id)
    if not s:
        raise HTTPException(
            status_code=400,
            detail="Could not generate prompt. Suggestion must be scored first.",
        )
    return _to_response(s)


@router.post("/{suggestion_id}/approve", response_model=SuggestionActionResponse)
def approve(
    suggestion_id: int,
    payload: SuggestionApproveRequest | None = None,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionActionResponse:
    notes = payload.admin_notes if payload else None
    s = approve_suggestion(session, suggestion_id, admin_notes=notes)
    if not s:
        raise HTTPException(
            status_code=400,
            detail="Could not approve. Suggestion must be in prompt_ready status.",
        )
    return SuggestionActionResponse(
        id=s.id,
        status=s.status,
        message=f"Approved. Prompt saved to {s.prompt_file_path}",
    )


@router.post("/{suggestion_id}/reject", response_model=SuggestionActionResponse)
def reject(
    suggestion_id: int,
    payload: SuggestionRejectRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionActionResponse:
    s = reject_suggestion(session, suggestion_id, admin_notes=payload.admin_notes)
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found.")
    return SuggestionActionResponse(
        id=s.id, status=s.status, message="Suggestion rejected."
    )


@router.delete("/{suggestion_id}", response_model=SuggestionActionResponse)
def delete(
    suggestion_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> SuggestionActionResponse:
    if not delete_suggestion(session, suggestion_id):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete. Suggestion must be pending or rejected.",
        )
    return SuggestionActionResponse(
        id=suggestion_id, status="deleted", message="Suggestion deleted."
    )
