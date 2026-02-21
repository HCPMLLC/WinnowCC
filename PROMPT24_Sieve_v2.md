# PROMPT24_Sieve_v2.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and SIEVE-IMPLEMENTATION.md before making changes.

## Purpose

Upgrade Sieve from a demo-mode keyword chatbot to a fully functional LLM-powered AI concierge with proactive triggers, escalation flow, and deep user-context awareness. Per SIEVE-IMPLEMENTATION.md: "Future backend integration replaces a single `getDemoResponse()` function with a real API call." Per the kanban: "Sieve v2 — Proactive nudges (low profile completeness, stale applications), escalation flow, context-aware suggestions."

This prompt covers two major upgrades:
1. **Backend LLM Chat** — Replace demo responses with a real `POST /api/sieve/chat` endpoint powered by Claude, with full access to the user's profile, matches, tracking, and billing data.
2. **Proactive Trigger Engine** — A backend service that detects user situations (incomplete profile, new matches, stale applications, usage limits) and pushes contextual nudges to the frontend widget.

---

## Triggers — When to Use This Prompt

- Replacing Sieve demo mode with real LLM-powered chat.
- Adding proactive nudges (profile completion, stale apps, new matches).
- Implementing the escalation flow (unanswered questions, complex requests).
- Making Sieve context-aware (profile, matches, billing, tracking data).

---

## What Already Exists (DO NOT recreate)

1. **Sieve frontend widget:** `apps/web/app/components/sieve/SieveWidget.tsx` — FAB, chat panel, message list, input, typing indicator, brand design (gold sieve logo, hunter green header, warm parchment background). Fully styled and functional. Has a `getDemoResponse()` function that is the single replacement point.
2. **Widget integration:** `apps/web/app/layout.tsx` — `<SieveWidget />` rendered for authenticated users.
3. **Widget props:** `apiBase` (string), `position` ("bottom-right"|"bottom-left"), `greeting` (string).
4. **Anthropic SDK:** Already installed (`anthropic>=0.40.0` in `services/api/requirements.txt`), already used in `services/api/app/services/tailor.py` for tailored resume generation.
5. **ANTHROPIC_API_KEY:** Already in `services/api/.env` and `.env.example`.
6. **All data endpoints the LLM needs:**
   - `GET /api/auth/me` — user ID, email, onboarding status
   - `GET /api/profile` — full candidate profile JSON
   - `GET /api/profile/completeness` — score (0–100), deficiencies, recommendations
   - `GET /api/dashboard/metrics` — 5 KPIs (profile completeness, qualified jobs, applications, interviews, offers)
   - `GET /api/matches` — job matches with scores, reasons, gaps, application_status
   - `GET /api/billing/status` — plan (free/pro), usage counts, limits
   - `PATCH /api/matches/{match_id}/status` — update application status
7. **Auth system:** `get_current_user` dependency resolves user from cookie or Bearer token.

---

## What to Build

This prompt covers 6 parts. Implement in order.

---

# PART 1 — SIEVE BACKEND: CHAT ENDPOINT

### 1.1 Create the Sieve service

This is the core intelligence layer. It assembles the user's context, builds a system prompt, calls Claude, and returns the response.

**File to create:** `services/api/app/services/sieve.py` (NEW)

```python
"""
Sieve AI concierge service.
Provides context-aware chat powered by Claude with full access
to the user's profile, matches, tracking, and billing data.
"""
import os
import json
import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.match import Match
from app.models.candidate_profile import CandidateProfile

logger = logging.getLogger(__name__)

SIEVE_MODEL = "claude-sonnet-4-20250514"
MAX_CONVERSATION_TURNS = 20  # Keep last 20 messages for context


def _build_user_context(user: User, db: Session) -> dict:
    """
    Gather all relevant user data for the Sieve system prompt.
    This gives Claude full awareness of the user's state.
    """
    context = {
        "user_id": user.id,
        "email": user.email,
        "onboarding_complete": user.onboarding_completed_at is not None,
    }

    # Profile completeness
    try:
        from app.routers.profile import _compute_completeness
        profile = db.query(CandidateProfile).filter(
            CandidateProfile.user_id == user.id
        ).order_by(CandidateProfile.version.desc()).first()

        if profile and profile.profile_json:
            pj = profile.profile_json if isinstance(profile.profile_json, dict) else json.loads(profile.profile_json)
            context["profile_summary"] = {
                "has_profile": True,
                "name": pj.get("basics", {}).get("name", "Unknown"),
                "title": pj.get("basics", {}).get("title", ""),
                "skills_count": len(pj.get("skills", [])),
                "experience_count": len(pj.get("experience", [])),
                "education_count": len(pj.get("education", [])),
                "preferences": pj.get("preferences", {}),
            }
        else:
            context["profile_summary"] = {"has_profile": False}
    except Exception as e:
        logger.warning(f"Failed to load profile for sieve context: {e}")
        context["profile_summary"] = {"has_profile": False, "error": True}

    # Profile completeness score
    try:
        from app.services.profile_completeness import compute_completeness
        completeness = compute_completeness(user.id, db)
        context["profile_completeness"] = {
            "score": completeness.get("score", 0),
            "deficiencies": completeness.get("deficiencies", []),
        }
    except Exception:
        context["profile_completeness"] = {"score": 0, "deficiencies": []}

    # Matches summary (don't send full list — just counts and top 3)
    try:
        matches = db.query(Match).filter(Match.user_id == user.id).all()
        context["matches_summary"] = {
            "total_matches": len(matches),
            "by_status": {},
            "top_matches": [],
        }
        status_counts = {}
        for m in matches:
            s = m.application_status or "unreviewed"
            status_counts[s] = status_counts.get(s, 0) + 1

        context["matches_summary"]["by_status"] = status_counts

        # Top 3 by match_score
        sorted_matches = sorted(matches, key=lambda m: m.match_score or 0, reverse=True)[:3]
        for m in sorted_matches:
            job = m.job  # Assumes relationship is loaded
            context["matches_summary"]["top_matches"].append({
                "match_id": m.id,
                "job_title": getattr(job, "title", "Unknown") if job else "Unknown",
                "company": getattr(job, "company", "Unknown") if job else "Unknown",
                "match_score": m.match_score,
                "application_status": m.application_status,
            })
    except Exception as e:
        logger.warning(f"Failed to load matches for sieve context: {e}")
        context["matches_summary"] = {"total_matches": 0}

    # Billing/subscription
    try:
        from app.services.billing import get_usage
        usage = get_usage(user.id, db)
        context["billing"] = {
            "plan": usage.get("plan", "free"),
            "tailored_resumes_used": usage.get("tailored_resumes_used", 0),
            "tailored_resumes_limit": usage.get("tailored_resumes_limit", 1),
            "cover_letters_used": usage.get("cover_letters_used", 0),
            "cover_letters_limit": usage.get("cover_letters_limit", 0),
        }
    except Exception:
        context["billing"] = {"plan": "free"}

    # Dashboard metrics
    try:
        from app.routers.dashboard import _compute_metrics
        metrics = _compute_metrics(user.id, db)
        context["dashboard_metrics"] = metrics
    except Exception:
        context["dashboard_metrics"] = {}

    return context


SIEVE_SYSTEM_PROMPT = """You are Sieve, Winnow's personal AI concierge for job seekers. You help candidates navigate their job search using the Winnow platform.

## Your Personality
- Warm, professional, and encouraging
- Concise — keep responses under 150 words unless the user asks for detail
- Use the greeting style: "Greetings" for the first interaction, then be natural
- Refer to yourself as Sieve
- Use "sifting" metaphors sparingly (once per conversation at most)

## Your Capabilities
You have access to the user's complete Winnow data (provided below). You can:
1. **Profile guidance** — Tell them their completeness score, what's missing, and how to improve it
2. **Match insights** — Summarize their top matches, explain scores, suggest which to apply to
3. **Application coaching** — Help them decide next steps (save, apply, prepare for interview)
4. **Tailoring advice** — Explain the tailored resume feature, help them decide which jobs to tailor for
5. **Billing/usage info** — Tell them their plan, usage, and when to upgrade
6. **General job search tips** — Interview prep, resume advice, job search strategy
7. **Navigation help** — Tell them where to find features in Winnow

## Rules
- NEVER fabricate data. Only reference information from the user context below.
- If you don't have data to answer a question, say so honestly and suggest where to find it.
- If the user asks about something outside Winnow (e.g., salary negotiation, company reviews), give general advice but note it's not from Winnow data.
- If the user seems frustrated after 3+ messages without resolution, offer to escalate: "I may not be the best help here. Would you like to contact support at support@winnow.app?"
- NEVER reveal raw JSON, database IDs, or system internals.
- Refer to UI locations naturally: "Head to your Dashboard", "Check your Matches page", "Visit Settings to manage your subscription"

## User Context
{user_context}

## Current Date
{current_date}
"""


async def generate_chat_response(
    user: User,
    message: str,
    conversation_history: list[dict],
    db: Session,
) -> dict:
    """
    Generate a Sieve chat response using Claude.

    Args:
        user: The authenticated user
        message: The user's latest message
        conversation_history: Previous messages [{role, content}, ...]
        db: Database session

    Returns:
        dict with "response" (str) and optionally "suggestions" (list[str])
    """
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    # Build user context
    user_context = _build_user_context(user, db)

    # Build system prompt with injected context
    system = SIEVE_SYSTEM_PROMPT.format(
        user_context=json.dumps(user_context, indent=2, default=str),
        current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    # Build messages array (keep last N turns for context window management)
    messages = []
    for msg in conversation_history[-MAX_CONVERSATION_TURNS:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    # Add the new user message
    messages.append({"role": "user", "content": message})

    try:
        response = client.messages.create(
            model=SIEVE_MODEL,
            max_tokens=500,
            system=system,
            messages=messages,
        )

        assistant_text = response.content[0].text if response.content else ""

        # Extract quick-reply suggestions from the response
        suggestions = _extract_suggestions(user_context)

        return {
            "response": assistant_text,
            "suggestions": suggestions,
        }

    except anthropic.APIError as e:
        logger.error(f"Sieve Claude API error: {e}")
        return {
            "response": "I'm having trouble connecting right now. Please try again in a moment.",
            "suggestions": ["Try again"],
        }


def _extract_suggestions(user_context: dict) -> list[str]:
    """
    Generate contextual quick-reply suggestions based on user state.
    These appear as tappable buttons below the response.
    """
    suggestions = []

    # Profile incomplete
    completeness = user_context.get("profile_completeness", {})
    if completeness.get("score", 0) < 70:
        suggestions.append("How do I improve my profile?")

    # Has matches
    matches = user_context.get("matches_summary", {})
    if matches.get("total_matches", 0) > 0:
        suggestions.append("Show my top matches")

    # Has unreviewed matches
    by_status = matches.get("by_status", {})
    unreviewed = by_status.get("unreviewed", 0)
    if unreviewed > 3:
        suggestions.append("Which jobs should I apply to?")

    # Free plan nearing limits
    billing = user_context.get("billing", {})
    if billing.get("plan") == "free":
        used = billing.get("tailored_resumes_used", 0)
        limit = billing.get("tailored_resumes_limit", 1)
        if used >= limit:
            suggestions.append("Tell me about Pro")

    # Default suggestions if none generated
    if not suggestions:
        suggestions = ["What can you help with?", "Show my dashboard"]

    return suggestions[:3]  # Max 3 suggestions
```

### 1.2 Create the Sieve router

**File to create:** `services/api/app/routers/sieve.py` (NEW)

```python
"""
Sieve chatbot API endpoints.
Provides the chat endpoint and proactive triggers endpoint.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.services.sieve import generate_chat_response
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sieve", tags=["sieve"])


class SieveChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list[dict]] = []


class SieveChatResponse(BaseModel):
    response: str
    suggestions: Optional[list[str]] = []


@router.post("/chat", response_model=SieveChatResponse)
@limiter.limit("30/minute")
async def sieve_chat(
    request,  # Required first param for slowapi
    payload: SieveChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to Sieve and get a contextual response.
    
    The conversation_history should contain previous messages
    as [{role: "user"|"assistant", content: "..."}].
    The frontend maintains this history in component state.
    """
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if len(payload.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 characters)")

    result = await generate_chat_response(
        user=user,
        message=payload.message.strip(),
        conversation_history=payload.conversation_history or [],
        db=db,
    )

    return SieveChatResponse(**result)
```

### 1.3 Register the Sieve router

**File to modify:** `services/api/app/main.py`

Add:

```python
from app.routers import sieve

app.include_router(sieve.router)
```

---

# PART 2 — PROACTIVE TRIGGER ENGINE

The trigger engine runs on the backend and returns contextual nudges based on the user's current state. The frontend polls this endpoint when the widget opens.

### 2.1 Create the trigger service

**File to create:** `services/api/app/services/sieve_triggers.py` (NEW)

```python
"""
Sieve proactive trigger engine.
Evaluates user state and generates contextual nudges.
Each trigger has a priority, message, action, and cooldown.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.match import Match
from app.models.candidate_profile import CandidateProfile

logger = logging.getLogger(__name__)


class Trigger:
    """A proactive nudge to show the user."""

    def __init__(
        self,
        trigger_id: str,
        priority: int,
        message: str,
        action_label: str,
        action_type: str,  # "navigate" | "chat" | "dismiss"
        action_target: str = "",  # URL path or chat prefill
    ):
        self.trigger_id = trigger_id
        self.priority = priority  # 1 = highest
        self.message = message
        self.action_label = action_label
        self.action_type = action_type
        self.action_target = action_target

    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id,
            "priority": self.priority,
            "message": self.message,
            "action_label": self.action_label,
            "action_type": self.action_type,
            "action_target": self.action_target,
        }


def evaluate_triggers(
    user: User,
    db: Session,
    dismissed_ids: Optional[list[str]] = None,
) -> list[dict]:
    """
    Evaluate all trigger conditions for a user.
    Returns a list of active triggers sorted by priority.
    Excludes any triggers the user has dismissed (by trigger_id).
    """
    dismissed = set(dismissed_ids or [])
    triggers = []

    # --- TRIGGER 1: Profile incomplete ---
    try:
        from app.services.profile_completeness import compute_completeness
        completeness = compute_completeness(user.id, db)
        score = completeness.get("score", 0)
        deficiencies = completeness.get("deficiencies", [])

        if score < 50:
            top_gap = deficiencies[0] if deficiencies else "some sections"
            triggers.append(Trigger(
                trigger_id="profile_incomplete_critical",
                priority=1,
                message=f"Your profile is only {score}% complete. Adding {top_gap} would significantly improve your matches.",
                action_label="Complete Profile",
                action_type="navigate",
                action_target="/profile",
            ))
        elif score < 70:
            top_gap = deficiencies[0] if deficiencies else "a few details"
            triggers.append(Trigger(
                trigger_id="profile_incomplete_moderate",
                priority=3,
                message=f"Your profile is {score}% complete. Adding {top_gap} could unlock better matches.",
                action_label="Improve Profile",
                action_type="navigate",
                action_target="/profile",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (profile_completeness): {e}")

    # --- TRIGGER 2: New matches since last visit ---
    try:
        # Count matches created in the last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        new_matches_count = db.query(func.count(Match.id)).filter(
            Match.user_id == user.id,
            Match.created_at >= yesterday,
        ).scalar() or 0

        if new_matches_count >= 3:
            triggers.append(Trigger(
                trigger_id="new_matches_batch",
                priority=2,
                message=f"🎯 {new_matches_count} new jobs matched your profile since yesterday!",
                action_label="View Matches",
                action_type="navigate",
                action_target="/matches",
            ))
        elif new_matches_count > 0:
            triggers.append(Trigger(
                trigger_id="new_matches_few",
                priority=4,
                message=f"{new_matches_count} new match{'es' if new_matches_count > 1 else ''} found since yesterday.",
                action_label="View Matches",
                action_type="navigate",
                action_target="/matches",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (new_matches): {e}")

    # --- TRIGGER 3: Stale saved jobs (saved but not applied after 5+ days) ---
    try:
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        stale_saved = db.query(Match).filter(
            Match.user_id == user.id,
            Match.application_status == "saved",
            Match.updated_at <= five_days_ago,
        ).count()

        if stale_saved > 0:
            triggers.append(Trigger(
                trigger_id="stale_saved_jobs",
                priority=3,
                message=f"You saved {stale_saved} job{'s' if stale_saved > 1 else ''} but haven't applied yet. Need help deciding?",
                action_label="Review Saved Jobs",
                action_type="chat",
                action_target="Which of my saved jobs should I apply to?",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (stale_saved): {e}")

    # --- TRIGGER 4: High-match job not yet saved/applied ---
    try:
        high_unreviewed = db.query(Match).filter(
            Match.user_id == user.id,
            Match.match_score >= 80,
            Match.application_status.is_(None),
        ).count()

        if high_unreviewed > 0:
            triggers.append(Trigger(
                trigger_id="high_match_unreviewed",
                priority=2,
                message=f"You have {high_unreviewed} strong match{'es' if high_unreviewed > 1 else ''} (80%+) you haven't looked at yet!",
                action_label="See Top Matches",
                action_type="navigate",
                action_target="/matches?sort=score&min_score=80",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (high_match_unreviewed): {e}")

    # --- TRIGGER 5: No tailored resumes yet ---
    try:
        from app.models.tailored_resume import TailoredResume
        tailored_count = db.query(func.count(TailoredResume.id)).filter(
            TailoredResume.user_id == user.id,
        ).scalar() or 0

        total_matches = db.query(func.count(Match.id)).filter(
            Match.user_id == user.id,
        ).scalar() or 0

        if tailored_count == 0 and total_matches > 0:
            triggers.append(Trigger(
                trigger_id="no_tailored_resumes",
                priority=4,
                message="You haven't created any tailored resumes yet. A job-specific resume can 3x your callback rate.",
                action_label="Learn More",
                action_type="chat",
                action_target="How does tailored resume generation work?",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (no_tailored_resumes): {e}")

    # --- TRIGGER 6: Usage limit approaching (free plan) ---
    try:
        from app.services.billing import get_usage
        usage = get_usage(user.id, db)
        if usage.get("plan") == "free":
            used = usage.get("tailored_resumes_used", 0)
            limit = usage.get("tailored_resumes_limit", 1)
            if used >= limit:
                triggers.append(Trigger(
                    trigger_id="usage_limit_reached",
                    priority=2,
                    message="You've used all your free tailored resumes this month. Upgrade to Pro for 20/month.",
                    action_label="View Plans",
                    action_type="navigate",
                    action_target="/settings",
                ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (usage_limit): {e}")

    # --- TRIGGER 7: Interviews but no offer tracking ---
    try:
        interviewing = db.query(func.count(Match.id)).filter(
            Match.user_id == user.id,
            Match.application_status == "interviewing",
        ).scalar() or 0

        offers = db.query(func.count(Match.id)).filter(
            Match.user_id == user.id,
            Match.application_status == "offer",
        ).scalar() or 0

        if interviewing > 0 and offers == 0:
            triggers.append(Trigger(
                trigger_id="interview_coaching",
                priority=5,
                message=f"You have {interviewing} interview{'s' if interviewing > 1 else ''} in progress. Want some prep tips?",
                action_label="Interview Tips",
                action_type="chat",
                action_target="Give me interview preparation tips",
            ))
    except Exception as e:
        logger.warning(f"Trigger eval failed (interview_coaching): {e}")

    # Filter dismissed triggers
    active = [t for t in triggers if t.trigger_id not in dismissed]

    # Sort by priority (1 = highest)
    active.sort(key=lambda t: t.priority)

    # Return top 3
    return [t.to_dict() for t in active[:3]]
```

### 2.2 Add the triggers endpoint to the Sieve router

**File to modify:** `services/api/app/routers/sieve.py`

Add below the existing `/chat` endpoint:

```python
from app.services.sieve_triggers import evaluate_triggers


class SieveTriggersRequest(BaseModel):
    dismissed_ids: Optional[list[str]] = []


class SieveTriggersResponse(BaseModel):
    triggers: list[dict]


@router.post("/triggers", response_model=SieveTriggersResponse)
async def get_triggers(
    payload: SieveTriggersRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluate and return proactive triggers for the current user.
    The frontend calls this when the Sieve widget opens.
    Dismissed trigger IDs are sent to suppress previously dismissed nudges.
    """
    triggers = evaluate_triggers(
        user=user,
        db=db,
        dismissed_ids=payload.dismissed_ids,
    )
    return SieveTriggersResponse(triggers=triggers)
```

---

# PART 3 — FRONTEND: WIRE THE WIDGET TO THE BACKEND

Replace the demo `getDemoResponse()` function with real API calls, add trigger display, add quick-reply suggestions, and add conversation history management.

### 3.1 Update SieveWidget.tsx

**File to modify:** `apps/web/app/components/sieve/SieveWidget.tsx`

The changes needed (modify the existing component, do NOT rewrite from scratch):

#### 3.1a Replace `getDemoResponse()` with API call

Find the `getDemoResponse(message)` function. Replace it with:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

async function sendMessage(
  message: string,
  conversationHistory: { role: string; content: string }[]
): Promise<{ response: string; suggestions: string[] }> {
  try {
    const res = await fetch(`${API_BASE}/api/sieve/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
      }),
    });

    if (!res.ok) {
      if (res.status === 429) {
        return {
          response: "I need a moment to catch my breath. Please try again shortly.",
          suggestions: ["Try again"],
        };
      }
      throw new Error(`API error: ${res.status}`);
    }

    return await res.json();
  } catch (error) {
    console.error("Sieve chat error:", error);
    return {
      response: "I'm having trouble connecting right now. Please try again in a moment.",
      suggestions: ["Try again"],
    };
  }
}
```

#### 3.1b Add conversation history tracking

In the component state, add:

```typescript
const [conversationHistory, setConversationHistory] = useState<
  { role: string; content: string }[]
>([]);
```

When the user sends a message, update the handler:

```typescript
async function handleSend() {
  if (!input.trim()) return;
  const userMessage = input.trim();
  setInput("");

  // Add user message to display
  setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

  // Show typing indicator
  setIsTyping(true);

  // Build history for context
  const history = [...conversationHistory, { role: "user", content: userMessage }];

  // Call backend
  const result = await sendMessage(userMessage, history);

  // Update conversation history
  setConversationHistory([
    ...history,
    { role: "assistant", content: result.response },
  ]);

  // Add assistant response to display
  setMessages((prev) => [...prev, { role: "assistant", content: result.response }]);
  setSuggestions(result.suggestions || []);
  setIsTyping(false);
}
```

#### 3.1c Add quick-reply suggestions

Add state for suggestions:

```typescript
const [suggestions, setSuggestions] = useState<string[]>([]);
```

Render suggestion buttons below the messages, above the input:

```tsx
{suggestions.length > 0 && (
  <div style={{
    display: "flex",
    gap: "6px",
    padding: "8px 16px",
    flexWrap: "wrap",
    borderTop: "1px solid #E5E0D6",
  }}>
    {suggestions.map((s) => (
      <button
        key={s}
        onClick={() => {
          setInput(s);
          // Optionally auto-send:
          // handleSend() after setting input
        }}
        style={{
          background: "#F5F0E4",
          border: "1px solid #D4CFC3",
          borderRadius: "16px",
          padding: "6px 12px",
          fontSize: "12px",
          color: "#3E3525",
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        {s}
      </button>
    ))}
  </div>
)}
```

#### 3.1d Add proactive triggers on widget open

When the chat panel opens, fetch triggers and display the top one as a system message:

```typescript
const [dismissedTriggers, setDismissedTriggers] = useState<string[]>([]);

async function fetchTriggers() {
  try {
    const res = await fetch(`${API_BASE}/api/sieve/triggers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ dismissed_ids: dismissedTriggers }),
    });
    if (res.ok) {
      const data = await res.json();
      return data.triggers || [];
    }
  } catch {}
  return [];
}

// In the open handler (when user clicks FAB to open panel):
async function handleOpen() {
  setIsOpen(true);
  const triggers = await fetchTriggers();

  if (triggers.length > 0) {
    const topTrigger = triggers[0];
    // Show trigger as a system message with action button
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: topTrigger.message,
        trigger: topTrigger,  // Store trigger metadata for the action button
      },
    ]);
  }
}
```

#### 3.1e Render trigger action buttons

When rendering messages, check for trigger metadata and show an action button:

```tsx
{msg.trigger && (
  <div style={{ marginTop: "8px" }}>
    <button
      onClick={() => handleTriggerAction(msg.trigger)}
      style={{
        background: "#E8C84A",
        color: "#1B3025",
        border: "none",
        borderRadius: "8px",
        padding: "6px 14px",
        fontSize: "13px",
        fontWeight: "600",
        cursor: "pointer",
      }}
    >
      {msg.trigger.action_label}
    </button>
    <button
      onClick={() => dismissTrigger(msg.trigger.trigger_id)}
      style={{
        background: "transparent",
        border: "none",
        color: "#9CA3AF",
        fontSize: "11px",
        marginLeft: "8px",
        cursor: "pointer",
      }}
    >
      Dismiss
    </button>
  </div>
)}
```

Handle trigger actions:

```typescript
function handleTriggerAction(trigger: any) {
  if (trigger.action_type === "navigate") {
    window.location.href = trigger.action_target;
  } else if (trigger.action_type === "chat") {
    setInput(trigger.action_target);
    // Optionally auto-send
  }
}

function dismissTrigger(triggerId: string) {
  setDismissedTriggers((prev) => [...prev, triggerId]);
  // Remove the trigger message from display
  setMessages((prev) =>
    prev.filter((m) => m.trigger?.trigger_id !== triggerId)
  );
}
```

---

# PART 4 — ESCALATION FLOW

Track consecutive "I don't know" / "I can't help" responses and offer escalation.

### 4.1 Backend: Escalation detection

**File to modify:** `services/api/app/services/sieve.py`

Add after the main `generate_chat_response` function:

```python
# Escalation phrases that indicate Sieve couldn't help
ESCALATION_INDICATORS = [
    "i'm not sure",
    "i don't have that information",
    "i can't help with that",
    "beyond what i can",
    "outside my capabilities",
    "contact support",
]


def check_escalation_needed(
    response_text: str,
    conversation_history: list[dict],
) -> bool:
    """
    Check if escalation is needed based on:
    1. Current response contains escalation indicators
    2. Last 3 assistant responses all contained indicators
    """
    response_lower = response_text.lower()
    current_uncertain = any(phrase in response_lower for phrase in ESCALATION_INDICATORS)

    if not current_uncertain:
        return False

    # Check if the last 2 assistant messages also had issues
    recent_assistant = [
        m for m in conversation_history[-6:]
        if m.get("role") == "assistant"
    ][-2:]  # Last 2 assistant messages

    uncertain_count = 0
    for msg in recent_assistant:
        content_lower = msg.get("content", "").lower()
        if any(phrase in content_lower for phrase in ESCALATION_INDICATORS):
            uncertain_count += 1

    return uncertain_count >= 2  # 2 previous + 1 current = 3 consecutive
```

Then in `generate_chat_response`, after getting the LLM response, add:

```python
    # Check for escalation
    if check_escalation_needed(assistant_text, conversation_history):
        assistant_text += "\n\nI've been struggling with your recent questions. Would you like to reach out to our support team at **support@winnow.app**? They can help with more complex issues."
```

---

# PART 5 — CONVERSATION PERSISTENCE (Optional Enhancement)

Store conversation history in the database so conversations persist across page reloads.

### 5.1 Create the conversation model

**File to create:** `services/api/app/models/sieve_conversation.py` (NEW)

```python
"""
Sieve conversation history model.
Stores chat messages per user for persistence across sessions.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, String
from app.db.base import Base


class SieveConversation(Base):
    __tablename__ = "sieve_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    trigger_id = Column(String(100), nullable=True)  # If this message was a proactive trigger
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

### 5.2 Add to models __init__

**File to modify:** `services/api/app/models/__init__.py`

Add:

```python
from app.models.sieve_conversation import SieveConversation
```

### 5.3 Create Alembic migration

Run in PowerShell:

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add sieve_conversations table"
alembic upgrade head
```

### 5.4 Add history endpoints

**File to modify:** `services/api/app/routers/sieve.py`

Add:

```python
from app.models.sieve_conversation import SieveConversation


@router.get("/history")
async def get_conversation_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the user's recent Sieve conversation history.
    The frontend loads this when the widget opens to restore context.
    """
    messages = (
        db.query(SieveConversation)
        .filter(SieveConversation.user_id == user.id)
        .order_by(SieveConversation.created_at.desc())
        .limit(limit)
        .all()
    )

    # Reverse to chronological order
    messages.reverse()

    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "trigger_id": m.trigger_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    }


@router.delete("/history")
async def clear_conversation_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear the user's Sieve conversation history."""
    db.query(SieveConversation).filter(
        SieveConversation.user_id == user.id
    ).delete()
    db.commit()
    return {"status": "cleared"}
```

Also update the `sieve_chat` endpoint to persist messages:

```python
@router.post("/chat", response_model=SieveChatResponse)
async def sieve_chat(...):
    # ... existing code ...

    result = await generate_chat_response(...)

    # Persist messages
    db.add(SieveConversation(
        user_id=user.id,
        role="user",
        content=payload.message.strip(),
    ))
    db.add(SieveConversation(
        user_id=user.id,
        role="assistant",
        content=result["response"],
    ))
    db.commit()

    return SieveChatResponse(**result)
```

### 5.5 Frontend: Load history on widget open

**File to modify:** `apps/web/app/components/sieve/SieveWidget.tsx`

When the widget opens, fetch saved history:

```typescript
async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/api/sieve/history?limit=20`, {
      credentials: "include",
    });
    if (res.ok) {
      const data = await res.json();
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages.map((m: any) => ({
          role: m.role,
          content: m.content,
        })));
        setConversationHistory(data.messages.map((m: any) => ({
          role: m.role,
          content: m.content,
        })));
      }
    }
  } catch {}
}

// Call in handleOpen():
async function handleOpen() {
  setIsOpen(true);
  await loadHistory();
  const triggers = await fetchTriggers();
  // ... existing trigger display logic
}
```

Add a "Clear History" button in the widget header:

```tsx
<button
  onClick={async () => {
    await fetch(`${API_BASE}/api/sieve/history`, {
      method: "DELETE",
      credentials: "include",
    });
    setMessages([{ role: "assistant", content: greeting }]);
    setConversationHistory([]);
    setSuggestions([]);
  }}
  aria-label="Clear chat history"
  title="Clear history"
  style={{ /* small icon button styling */ }}
>
  🗑️
</button>
```

---

# PART 6 — TESTS

**File to create:** `services/api/tests/test_sieve.py` (NEW)

```python
"""Tests for Sieve chat and triggers endpoints."""
import pytest


class TestSieveChat:
    def test_chat_requires_auth(self, client):
        """Unauthenticated requests should get 401."""
        res = client.post("/api/sieve/chat", json={"message": "hello"})
        assert res.status_code == 401

    def test_chat_empty_message(self, auth_client):
        """Empty messages should get 400."""
        res = auth_client.post("/api/sieve/chat", json={"message": ""})
        assert res.status_code == 400

    def test_chat_too_long(self, auth_client):
        """Messages over 2000 chars should get 400."""
        res = auth_client.post("/api/sieve/chat", json={"message": "x" * 2001})
        assert res.status_code == 400

    def test_chat_returns_response(self, auth_client, monkeypatch):
        """Chat should return a response and suggestions."""
        # Mock the Claude API call
        async def mock_generate(*args, **kwargs):
            return {"response": "Hello! How can I help?", "suggestions": ["Show matches"]}

        monkeypatch.setattr("app.services.sieve.generate_chat_response", mock_generate)

        res = auth_client.post(
            "/api/sieve/chat",
            json={"message": "hello", "conversation_history": []},
        )
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert isinstance(data.get("suggestions"), list)


class TestSieveTriggers:
    def test_triggers_requires_auth(self, client):
        res = client.post("/api/sieve/triggers", json={})
        assert res.status_code == 401

    def test_triggers_returns_list(self, auth_client):
        res = auth_client.post(
            "/api/sieve/triggers",
            json={"dismissed_ids": []},
        )
        assert res.status_code == 200
        data = res.json()
        assert "triggers" in data
        assert isinstance(data["triggers"], list)

    def test_triggers_respects_dismissed(self, auth_client):
        """Dismissed triggers should not appear."""
        res = auth_client.post(
            "/api/sieve/triggers",
            json={"dismissed_ids": ["profile_incomplete_critical", "profile_incomplete_moderate"]},
        )
        data = res.json()
        for t in data["triggers"]:
            assert t["trigger_id"] not in ["profile_incomplete_critical", "profile_incomplete_moderate"]


class TestSieveHistory:
    def test_history_requires_auth(self, client):
        res = client.get("/api/sieve/history")
        assert res.status_code == 401

    def test_history_empty_by_default(self, auth_client):
        res = auth_client.get("/api/sieve/history")
        assert res.status_code == 200
        data = res.json()
        assert data["messages"] == []

    def test_clear_history(self, auth_client):
        res = auth_client.delete("/api/sieve/history")
        assert res.status_code == 200
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Sieve service (LLM chat) | `services/api/app/services/sieve.py` | CREATE |
| Sieve triggers engine | `services/api/app/services/sieve_triggers.py` | CREATE |
| Sieve router (chat + triggers + history) | `services/api/app/routers/sieve.py` | CREATE |
| Sieve conversation model | `services/api/app/models/sieve_conversation.py` | CREATE |
| Models __init__ | `services/api/app/models/__init__.py` | MODIFY — add SieveConversation |
| Alembic migration | `services/api/alembic/versions/` | CREATE (auto-generated) |
| Main app (register router) | `services/api/app/main.py` | MODIFY — add sieve router |
| Sieve widget (frontend) | `apps/web/app/components/sieve/SieveWidget.tsx` | MODIFY — replace demo mode |
| Tests | `services/api/tests/test_sieve.py` | CREATE |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Backend Sieve Service (Steps 1–4)

1. **Step 1:** Create `services/api/app/services/sieve.py` (Part 1.1). This is the core LLM chat service.
2. **Step 2:** Create `services/api/app/services/sieve_triggers.py` (Part 2.1). This is the proactive trigger engine.
3. **Step 3:** Create `services/api/app/routers/sieve.py` (Part 1.2 + Part 2.2). This has all three endpoints: `/chat`, `/triggers`, `/history`.
4. **Step 4:** Open `services/api/app/main.py`. Register the sieve router (Part 1.3):
   ```python
   from app.routers import sieve
   app.include_router(sieve.router)
   ```

### Phase 2: Conversation Persistence (Steps 5–7)

5. **Step 5:** Create `services/api/app/models/sieve_conversation.py` (Part 5.1).
6. **Step 6:** Open `services/api/app/models/__init__.py`. Add the import (Part 5.2).
7. **Step 7:** Create and run the Alembic migration (Part 5.3):
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   alembic revision --autogenerate -m "add sieve_conversations table"
   alembic upgrade head
   ```

### Phase 3: Escalation Logic (Step 8)

8. **Step 8:** Open `services/api/app/services/sieve.py`. Add the `check_escalation_needed` function and wire it into `generate_chat_response` (Part 4.1).

### Phase 4: Test Backend (Steps 9–10)

9. **Step 9:** Start the API:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
10. **Step 10:** Test the endpoints manually:
    ```powershell
    # Chat (use a valid session cookie or Bearer token)
    curl -X POST http://localhost:8000/api/sieve/chat ^
      -H "Content-Type: application/json" ^
      -H "Cookie: rm_session=YOUR_TOKEN" ^
      -d "{\"message\": \"What are my top matches?\", \"conversation_history\": []}"

    # Triggers
    curl -X POST http://localhost:8000/api/sieve/triggers ^
      -H "Content-Type: application/json" ^
      -H "Cookie: rm_session=YOUR_TOKEN" ^
      -d "{\"dismissed_ids\": []}"

    # History
    curl http://localhost:8000/api/sieve/history ^
      -H "Cookie: rm_session=YOUR_TOKEN"
    ```

### Phase 5: Frontend Widget Upgrade (Steps 11–15)

11. **Step 11:** Open `apps/web/app/components/sieve/SieveWidget.tsx`. Replace the `getDemoResponse()` function with the `sendMessage()` API call (Part 3.1a).
12. **Step 12:** Add `conversationHistory` state and update `handleSend` to track history (Part 3.1b).
13. **Step 13:** Add `suggestions` state and render quick-reply buttons (Part 3.1c).
14. **Step 14:** Add proactive trigger fetching on widget open (Part 3.1d). Add trigger action buttons (Part 3.1e).
15. **Step 15:** Add history loading on widget open and "Clear History" button (Part 5.5).

### Phase 6: Test End-to-End (Steps 16–18)

16. **Step 16:** Start both API and web:
    ```powershell
    # Terminal 1
    cd services/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # Terminal 2
    cd apps/web && npm run dev
    ```
17. **Step 17:** Open `http://localhost:3000`. Log in. Click the Sieve FAB button. Verify:
    - [ ] Proactive trigger appears (e.g., "Your profile is X% complete...")
    - [ ] Typing a message sends to the API and returns a real LLM response
    - [ ] Quick-reply suggestion buttons appear below responses
    - [ ] Conversation history persists when you close and reopen the widget
    - [ ] "Clear History" button works
    - [ ] Trigger "Dismiss" button hides the trigger
    - [ ] Trigger action buttons work (navigate or prefill chat)
18. **Step 18:** Create `services/api/tests/test_sieve.py` (Part 6) and run tests:
    ```powershell
    cd services/api
    pytest tests/test_sieve.py -v
    ```

### Phase 7: Lint (Step 19)

19. **Step 19:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd ../../apps/web
    npm run lint
    ```

---

## Trigger Reference Table

| Trigger ID | Priority | Condition | Message | Action |
|------------|----------|-----------|---------|--------|
| `profile_incomplete_critical` | 1 | Completeness < 50% | "Your profile is only X% complete..." | Navigate → /profile |
| `profile_incomplete_moderate` | 3 | Completeness 50–69% | "Your profile is X% complete..." | Navigate → /profile |
| `new_matches_batch` | 2 | 3+ new matches in 24h | "🎯 X new jobs matched..." | Navigate → /matches |
| `new_matches_few` | 4 | 1–2 new matches in 24h | "X new match found..." | Navigate → /matches |
| `stale_saved_jobs` | 3 | Saved jobs > 5 days old | "You saved X jobs but haven't applied..." | Chat → "Which should I apply to?" |
| `high_match_unreviewed` | 2 | 80%+ matches not reviewed | "X strong matches you haven't looked at..." | Navigate → /matches?sort=score |
| `no_tailored_resumes` | 4 | 0 tailored + has matches | "You haven't created any tailored resumes..." | Chat → "How does tailoring work?" |
| `usage_limit_reached` | 2 | Free plan, limit hit | "You've used all free tailored resumes..." | Navigate → /settings |
| `interview_coaching` | 5 | Has interviews, no offers | "You have X interviews. Want prep tips?" | Chat → "Interview preparation tips" |

---

## Non-Goals (Do NOT implement in this prompt)

- Voice input/output for Sieve
- Sieve on the mobile app (future — after PROMPT23)
- Multi-language Sieve support
- Sieve performing actions on behalf of the user (it advises, not acts)
- Real-time streaming responses (use simple request/response for v2)
- Fine-tuning a custom model for Sieve
- RAG (retrieval-augmented generation) over job descriptions
- Push notifications from triggers (triggers are pull-based, shown on widget open)
- Admin analytics on Sieve usage (add in a future monitoring pass)

---

## Summary Checklist

### Backend — LLM Chat Service
- [ ] `sieve.py` service created with `_build_user_context`, `SIEVE_SYSTEM_PROMPT`, `generate_chat_response`
- [ ] User context includes: profile summary, completeness, matches summary (counts + top 3), billing/usage, dashboard metrics
- [ ] System prompt defines personality, capabilities, and rules (never fabricate, never reveal internals)
- [ ] Claude API call with conversation history (last 20 turns)
- [ ] Quick-reply suggestions generated from user state
- [ ] Error handling for API failures (graceful fallback message)
- [ ] Rate limited: 30/minute

### Backend — Proactive Triggers
- [ ] `sieve_triggers.py` with `evaluate_triggers` function
- [ ] 9 trigger conditions implemented (profile, matches, stale jobs, high matches, tailoring, billing, interviews)
- [ ] Each trigger has: id, priority, message, action_label, action_type, action_target
- [ ] Dismissed trigger IDs respected (filtered out)
- [ ] Returns top 3 triggers sorted by priority
- [ ] All trigger evaluations wrapped in try/except (never crashes)

### Backend — Escalation
- [ ] `check_escalation_needed` detects 3+ consecutive uncertain responses
- [ ] Appends support contact suggestion when escalation triggered

### Backend — Conversation Persistence
- [ ] `sieve_conversations` table created (user_id, role, content, trigger_id, created_at)
- [ ] Messages persisted on every chat exchange
- [ ] `GET /api/sieve/history` returns recent messages
- [ ] `DELETE /api/sieve/history` clears conversation
- [ ] Cascade delete when user account deleted

### Backend — Router
- [ ] `POST /api/sieve/chat` — authenticated, rate-limited, validates input
- [ ] `POST /api/sieve/triggers` — authenticated, returns evaluated triggers
- [ ] `GET /api/sieve/history` — returns saved conversation
- [ ] `DELETE /api/sieve/history` — clears conversation
- [ ] Router registered in `main.py`

### Frontend — Widget Upgrade
- [ ] `getDemoResponse()` replaced with `sendMessage()` API call
- [ ] Conversation history tracked in state and sent with each request
- [ ] Quick-reply suggestion buttons rendered below responses
- [ ] Proactive triggers fetched on widget open
- [ ] Trigger messages displayed with action button + dismiss button
- [ ] Trigger actions: "navigate" opens URL, "chat" prefills input
- [ ] Dismissed triggers tracked in state (not re-shown)
- [ ] History loaded from backend on widget open
- [ ] "Clear History" button in widget header
- [ ] Graceful error handling (fallback messages on API failure)

### Tests
- [ ] `test_sieve.py` with tests for chat (auth, validation, response), triggers (auth, response, dismissed), history (auth, empty, clear)
- [ ] Tests pass with `pytest tests/test_sieve.py -v`

Return code changes only.
