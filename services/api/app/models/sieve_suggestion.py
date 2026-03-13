"""Sieve suggestion model.

Captures improvement ideas, feature requests, and bug reports from Sieve
conversations or manual admin entry.  Each suggestion flows through:
pending → scored → prompt_ready → approved/rejected.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.base import Base


class SieveSuggestion(Base):
    __tablename__ = "sieve_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(
        String(30), nullable=False, default="feature"
    )  # feature / improvement / bug / ux / performance

    # Origin
    source = Column(
        String(30), nullable=False, default="admin_manual"
    )  # sieve_detected / admin_manual
    source_user_id = Column(Integer, nullable=True)
    conversation_snippet = Column(Text, nullable=True)

    # Scoring
    alignment_score = Column(Float, nullable=True)  # 0-100
    value_score = Column(Float, nullable=True)  # 0-100
    cost_estimate = Column(String(10), nullable=True)  # low / medium / high
    cost_score = Column(Float, nullable=True)  # 0-100 (derived from cost_estimate)
    priority_score = Column(Float, nullable=True)  # weighted composite
    priority_label = Column(String(10), nullable=True)  # HIGH / MEDIUM / LOW
    scoring_rationale = Column(Text, nullable=True)

    # Implementation prompt
    implementation_prompt = Column(Text, nullable=True)
    prompt_file_path = Column(String(500), nullable=True)

    # Status workflow
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending / scored / prompt_ready / approved / rejected
    admin_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
