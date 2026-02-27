from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base


class DailyUsageCounter(Base):
    __tablename__ = "daily_usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "counter_name", "date", name="uq_daily_user_counter_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    counter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @classmethod
    def get_today_count(cls, session: Session, user_id: int, counter_name: str) -> int:
        """Return today's count for a given counter, or 0 if no row exists."""
        today = date.today()
        row = session.execute(
            select(cls.count).where(
                cls.user_id == user_id,
                cls.counter_name == counter_name,
                cls.date == today,
            )
        ).scalar_one_or_none()
        return row or 0

    @classmethod
    def increment(cls, session: Session, user_id: int, counter_name: str) -> int:
        """Upsert today's row and increment the count. Returns new count.

        Uses PostgreSQL INSERT ON CONFLICT when available, falls back to
        SELECT+INSERT/UPDATE for SQLite (used in tests).
        """
        today = date.today()

        # Try PostgreSQL upsert first
        dialect_name = session.bind.dialect.name if session.bind else ""
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = (
                pg_insert(cls)
                .values(user_id=user_id, counter_name=counter_name, date=today, count=1)
                .on_conflict_do_update(
                    constraint="uq_daily_user_counter_date",
                    set_={"count": cls.count + 1},
                )
                .returning(cls.count)
            )
            result = session.execute(stmt).scalar_one()
            session.flush()
            return result

        # Fallback: SELECT + INSERT/UPDATE (SQLite-compatible)
        row = session.execute(
            select(cls).where(
                cls.user_id == user_id,
                cls.counter_name == counter_name,
                cls.date == today,
            )
        ).scalar_one_or_none()

        if row is None:
            row = cls(user_id=user_id, counter_name=counter_name, date=today, count=1)
            session.add(row)
            session.flush()
            return 1

        row.count += 1
        session.flush()
        return row.count
