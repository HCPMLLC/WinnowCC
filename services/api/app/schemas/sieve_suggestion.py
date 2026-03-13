from datetime import datetime

from pydantic import BaseModel, Field

# --- Create ---

class SuggestionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1)
    category: str = Field(
        default="feature", pattern="^(feature|improvement|bug|ux|performance)$"
    )


# --- List / Detail ---

class SuggestionResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    source: str
    source_user_id: int | None = None
    conversation_snippet: str | None = None
    alignment_score: float | None = None
    value_score: float | None = None
    cost_estimate: str | None = None
    cost_score: float | None = None
    priority_score: float | None = None
    priority_label: str | None = None
    scoring_rationale: str | None = None
    implementation_prompt: str | None = None
    prompt_file_path: str | None = None
    status: str
    admin_notes: str | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SuggestionListResponse(BaseModel):
    suggestions: list[SuggestionResponse]
    total: int
    high_priority_count: int
    awaiting_approval_count: int


# --- Actions ---

class SuggestionApproveRequest(BaseModel):
    admin_notes: str | None = None


class SuggestionRejectRequest(BaseModel):
    admin_notes: str = Field(..., min_length=1)


class SuggestionActionResponse(BaseModel):
    id: int
    status: str
    message: str
