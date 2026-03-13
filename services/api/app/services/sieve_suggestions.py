"""Sieve suggestion service — scoring, prompt generation, and detection.

Captures improvement ideas from Sieve conversations or manual admin entry,
scores them against Winnow's strategy, and generates implementation prompts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sieve_suggestion import SieveSuggestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategic context for AI scoring
# ---------------------------------------------------------------------------

WINNOW_STRATEGY = """\
Winnow is a three-sided hiring platform (candidates, employers, recruiters) with
six strategic competitive exploits:
1. Living Profiles — resumes parsed into structured, always-up-to-date profiles
2. Explainable Matching — Interview Probability Scores (IPS) with transparent breakdowns
3. AI Tailoring — per-job tailored resumes and cover letters
4. Career Intelligence — salary benchmarks, trajectory analysis, market positioning
5. Sieve AI Concierge — context-aware conversational assistant for all segments
6. Trust & Compliance — fraud detection, consent management, GDPR exports

Three-segment architecture:
- Candidates: free / starter $9/mo / pro $29/mo
- Employers: free / starter $49/mo / pro $149/mo / enterprise (custom)
- Recruiters: trial 14-day / solo $39/mo / team $89/user/mo / agency $129/user/mo

Tech stack: Next.js frontend, FastAPI backend, Expo mobile app, Chrome extension,
PostgreSQL + Redis, RQ workers, Stripe billing, pgvector semantic search.
"""

SCORING_PROMPT = """\
You are evaluating a product suggestion for Winnow, a hiring platform.

## Winnow Context
{strategy}

## Suggestion
Title: {title}
Description: {description}
Category: {category}

## Instructions
Score this suggestion on three axes. Return ONLY valid JSON (no markdown fences):

{{
  "alignment_score": <0-100 — strategic exploit alignment>,
  "value_score": <0-100 integer — how much would this improve the platform for users?>,
  "cost_estimate": "<low|medium|high> — implementation effort",
  "rationale": "<2-3 sentences explaining the scores>"
}}
"""

PROMPT_GENERATION_TEMPLATE = """\
You are generating an implementation prompt for a Claude Code session.

## Winnow Repository Structure
```
apps/web/              Next.js 14 frontend (TypeScript, React 18, Tailwind CSS)
apps/mobile/           Expo React Native app
apps/chrome-extension/ Chrome extension
services/api/          FastAPI backend (Python 3.11, SQLAlchemy, Alembic)
infra/                 Docker Compose (Postgres 16, Redis 7)
```

Key backend paths:
- Models: services/api/app/models/
- Schemas: services/api/app/schemas/
- Services: services/api/app/services/
- Routers: services/api/app/routers/
- Migrations: services/api/alembic/versions/

Key frontend paths:
- Pages: apps/web/app/
- Components: apps/web/components/
- Hooks: apps/web/app/hooks/

## Suggestion
Title: {title}
Description: {description}
Category: {category}

## Scoring
- Strategic Alignment: {alignment_score}/100
- Value/Impact: {value_score}/100
- Cost: {cost_estimate}
- Rationale: {scoring_rationale}

## Instructions
Write a detailed, actionable implementation prompt that someone can paste into
Claude Code to build this feature. Include:
1. Clear objective (1-2 sentences)
2. Files to create or modify (with paths)
3. Key implementation details
4. Database changes if needed (model + migration)
5. API endpoints if needed
6. Frontend changes if needed
7. Testing/verification steps

Be specific about existing patterns to follow. The prompt should be self-contained
and ready to execute.
"""

# Keyword patterns that suggest someone is describing an idea or problem
_SUGGESTION_KEYWORDS = [
    r"\bwould be (?:nice|great|cool|helpful|useful)\b",
    r"\byou should (?:add|build|create|make|implement)\b",
    r"\bwhat if (?:we|you|there)\b",
    r"\bfeature request\b",
    r"\bit would help if\b",
    r"\bcan you add\b",
    r"\bi wish (?:there was|you could|it could)\b",
    r"\bbug[: ]",
    r"\bbroken\b",
    r"\bdoesn'?t work\b",
    r"\bshould be able to\b",
    r"\bimprovement\b",
    r"\bidea[: ]\b",
]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_suggestion(
    session: Session,
    title: str,
    description: str,
    category: str = "feature",
    source: str = "admin_manual",
    source_user_id: int | None = None,
    conversation_snippet: str | None = None,
) -> SieveSuggestion:
    """Create a new suggestion in pending status."""
    suggestion = SieveSuggestion(
        title=title,
        description=description,
        category=category,
        source=source,
        source_user_id=source_user_id,
        conversation_snippet=conversation_snippet,
        status="pending",
    )
    session.add(suggestion)
    session.commit()
    session.refresh(suggestion)
    return suggestion


def get_suggestion(session: Session, suggestion_id: int) -> SieveSuggestion | None:
    return session.get(SieveSuggestion, suggestion_id)


def list_suggestions(
    session: Session,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
) -> list[SieveSuggestion]:
    """List suggestions with optional filters."""
    stmt = select(SieveSuggestion).order_by(SieveSuggestion.created_at.desc())
    if status:
        stmt = stmt.where(SieveSuggestion.status == status)
    if priority:
        stmt = stmt.where(SieveSuggestion.priority_label == priority)
    if category:
        stmt = stmt.where(SieveSuggestion.category == category)
    return list(session.execute(stmt).scalars().all())


def get_summary_counts(session: Session) -> dict:
    """Return total, high-priority, and awaiting-approval counts."""
    total = session.execute(
        select(func.count(SieveSuggestion.id))
    ).scalar_one()
    high = session.execute(
        select(func.count(SieveSuggestion.id)).where(
            SieveSuggestion.priority_label == "HIGH"
        )
    ).scalar_one()
    awaiting = session.execute(
        select(func.count(SieveSuggestion.id)).where(
            SieveSuggestion.status == "prompt_ready"
        )
    ).scalar_one()
    return {
        "total": total,
        "high_priority_count": high,
        "awaiting_approval_count": awaiting,
    }


def delete_suggestion(session: Session, suggestion_id: int) -> bool:
    """Delete a suggestion (only pending or rejected)."""
    suggestion = session.get(SieveSuggestion, suggestion_id)
    if not suggestion:
        return False
    if suggestion.status not in ("pending", "rejected"):
        return False
    session.delete(suggestion)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

COST_SCORE_MAP = {"low": 90, "medium": 60, "high": 30}


def _compute_priority(
    alignment: float, value: float, cost_score: float
) -> tuple[float, str]:
    """Weighted priority: 35% alignment + 40% value + 25% cost."""
    score = 0.35 * alignment + 0.40 * value + 0.25 * cost_score
    if score >= 70:
        label = "HIGH"
    elif score >= 40:
        label = "MEDIUM"
    else:
        label = "LOW"
    return round(score, 1), label


def score_suggestion(session: Session, suggestion_id: int) -> SieveSuggestion | None:
    """Call LLM to evaluate a suggestion's alignment, value, and cost."""
    suggestion = session.get(SieveSuggestion, suggestion_id)
    if not suggestion:
        return None

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        logger.error("Cannot score suggestion: ANTHROPIC_API_KEY not set")
        return None

    prompt = SCORING_PROMPT.format(
        strategy=WINNOW_STRATEGY,
        title=suggestion.title,
        description=suggestion.description,
        category=suggestion.category,
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
    except Exception as exc:
        logger.error("Scoring LLM call failed: %s", exc)
        return None

    alignment = float(data.get("alignment_score", 50))
    value = float(data.get("value_score", 50))
    cost_est = data.get("cost_estimate", "medium").lower()
    cost_sc = COST_SCORE_MAP.get(cost_est, 60)
    priority_score, priority_label = _compute_priority(alignment, value, cost_sc)

    suggestion.alignment_score = alignment
    suggestion.value_score = value
    suggestion.cost_estimate = cost_est
    suggestion.cost_score = cost_sc
    suggestion.priority_score = priority_score
    suggestion.priority_label = priority_label
    suggestion.scoring_rationale = data.get("rationale", "")
    suggestion.status = "scored"
    suggestion.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(suggestion)
    return suggestion


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------


def generate_prompt(session: Session, suggestion_id: int) -> SieveSuggestion | None:
    """Generate a Claude Code implementation prompt for a scored suggestion."""
    suggestion = session.get(SieveSuggestion, suggestion_id)
    if not suggestion:
        return None
    if suggestion.status not in ("scored", "prompt_ready"):
        return None

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        logger.error("Cannot generate prompt: ANTHROPIC_API_KEY not set")
        return None

    user_prompt = PROMPT_GENERATION_TEMPLATE.format(
        title=suggestion.title,
        description=suggestion.description,
        category=suggestion.category,
        alignment_score=suggestion.alignment_score or 0,
        value_score=suggestion.value_score or 0,
        cost_estimate=suggestion.cost_estimate or "medium",
        scoring_rationale=suggestion.scoring_rationale or "",
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": user_prompt}],
        )
        prompt_text = response.content[0].text.strip()
    except Exception as exc:
        logger.error("Prompt generation LLM call failed: %s", exc)
        return None

    suggestion.implementation_prompt = prompt_text
    suggestion.status = "prompt_ready"
    suggestion.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(suggestion)
    return suggestion


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug[:60]


def approve_suggestion(
    session: Session, suggestion_id: int, admin_notes: str | None = None
) -> SieveSuggestion | None:
    """Approve a suggestion and write the prompt to tasks/prompts/."""
    suggestion = session.get(SieveSuggestion, suggestion_id)
    if not suggestion:
        return None
    if suggestion.status != "prompt_ready":
        return None

    # Write prompt file
    prompts_dir = Path(__file__).resolve().parents[3] / "tasks" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(suggestion.title)
    filename = f"{suggestion.id}_{slug}.md"
    filepath = prompts_dir / filename

    content = f"# {suggestion.title}\n\n"
    content += f"**Category**: {suggestion.category}\n"
    content += (
        f"**Priority**: {suggestion.priority_label}"
        f" ({suggestion.priority_score})\n"
    )
    content += f"**Alignment**: {suggestion.alignment_score}/100 | "
    content += f"**Value**: {suggestion.value_score}/100 | "
    content += f"**Cost**: {suggestion.cost_estimate}\n\n"
    content += "---\n\n"
    content += suggestion.implementation_prompt or ""
    content += "\n"

    filepath.write_text(content, encoding="utf-8")

    suggestion.prompt_file_path = str(filepath)
    suggestion.status = "approved"
    suggestion.admin_notes = admin_notes
    suggestion.approved_at = datetime.now(UTC)
    suggestion.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(suggestion)
    return suggestion


def reject_suggestion(
    session: Session, suggestion_id: int, admin_notes: str
) -> SieveSuggestion | None:
    """Reject a suggestion with notes."""
    suggestion = session.get(SieveSuggestion, suggestion_id)
    if not suggestion:
        return None

    suggestion.status = "rejected"
    suggestion.admin_notes = admin_notes
    suggestion.rejected_at = datetime.now(UTC)
    suggestion.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(suggestion)
    return suggestion


# ---------------------------------------------------------------------------
# Detection in Sieve messages
# ---------------------------------------------------------------------------


def detect_suggestion_in_message(
    message: str,
    user_id: int,
    session: Session,
) -> SieveSuggestion | None:
    """Check if a user message contains a suggestion/idea/bug report.

    Uses keyword matching first (cheap), then LLM extraction if triggered.
    Only runs for admin users to avoid noise.
    """
    from app.models.user import User

    user = session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if not user or not user.is_admin:
        return None

    # Keyword pre-filter
    lower = message.lower()
    if not any(re.search(pat, lower) for pat in _SUGGESTION_KEYWORDS):
        return None

    # LLM extraction
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not anthropic_key:
        return None

    extraction_prompt = f"""\
The following message was sent in a product chat. Determine if it contains a
product suggestion, feature request, improvement idea, or bug report.

Message: "{message}"

If YES, return JSON (no markdown fences):
{{"is_suggestion": true, "title": "<short title>",
"description": "<what they want>",
"category": "<feature|improvement|bug|ux|performance>"}}

If NO, return:
{{"is_suggestion": false}}
"""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("Suggestion detection failed: %s", exc)
        return None

    if not data.get("is_suggestion"):
        return None

    return create_suggestion(
        session=session,
        title=data.get("title", "Untitled suggestion"),
        description=data.get("description", message),
        category=data.get("category", "feature"),
        source="sieve_detected",
        source_user_id=user_id,
        conversation_snippet=message[:2000],
    )
