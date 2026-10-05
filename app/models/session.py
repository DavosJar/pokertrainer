from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TrainingSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    filter_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    total_hands: Mapped[int] = mapped_column(Integer, default=0)
    correct_hands: Mapped[int] = mapped_column(Integer, default=0)

    answers: Mapped[List["Answer"]] = relationship(
        "Answer",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
