from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stack_range: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    spot: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    game: Mapped[str] = mapped_column(String(32), default="SPIN_3MAX")
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    actions_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    followups_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    reference_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # Solo en escenarios 'by_stack': la respuesta correcta depende del stack.
    # Un escenario con 'hands' los deja en None y no tiene tabla.
    stack_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stack_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stack_step: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    by_stack: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    hands: Mapped[List["ScenarioHand"]] = relationship(
        "ScenarioHand",
        back_populates="scenario",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_scenarios_pos_stack", "position", "stack_range"),
    )


class ScenarioHand(Base):
    __tablename__ = "scenario_hands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    hand: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    followup_action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    frequency: Mapped[float] = mapped_column(Float, default=100.0)

    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="hands")

    __table_args__ = (
        UniqueConstraint("scenario_id", "hand", name="uq_scenario_hand"),
        Index("ix_scenario_hand_lookup", "scenario_id", "hand"),
        Index("ix_scenario_action_lookup", "scenario_id", "action"),
    )
