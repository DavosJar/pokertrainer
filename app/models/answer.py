from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    scenario_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    hand: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    chosen_action: Mapped[str] = mapped_column(String(32), nullable=False)
    correct_action: Mapped[str] = mapped_column(String(32), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    response_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="answers")
    scenario: Mapped["Scenario"] = relationship("Scenario")

    __table_args__ = (
        Index("ix_answers_stat_lookup", "scenario_id", "hand", "is_correct"),
        Index("ix_answers_session_date", "session_id", "created_at"),
        Index("ix_answers_date_correct", "created_at", "is_correct"),
    )
