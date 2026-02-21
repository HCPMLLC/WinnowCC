from pydantic import BaseModel, Field


class SieveHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class SieveChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: list[SieveHistoryItem] = Field(
        default_factory=list, max_length=20
    )


class SieveChatResponse(BaseModel):
    response: str
    conversation_id: str
    suggested_actions: list[str] = Field(default_factory=list)


class SieveTrigger(BaseModel):
    id: str
    message: str
    priority: int = 5
    action_label: str = ""
    action_type: str = ""  # "navigate" | "chat" | "dismiss"
    action_target: str = ""  # URL path or chat prefill text


class SieveTriggersRequest(BaseModel):
    dismissed_ids: list[str] = Field(default_factory=list)


class SieveTriggersResponse(BaseModel):
    triggers: list[SieveTrigger]
