from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class StatsOverview(BaseModel):
    total_answers: int
    total_correct: int
    global_accuracy_pct: float
    avg_response_ms: int
    median_response_ms: int
    correct_fast_pct: float
    current_streak: int
    best_streak: int
    total_sessions: int


class AccuracyPoint(BaseModel):
    date: str
    accuracy_pct: float
    avg_response_ms: int
    total_hands: int


class CategoryAccuracy(BaseModel):
    category: str
    label: str
    total_hands: int
    correct_hands: int
    accuracy_pct: float
    avg_response_ms: int


class HandHeatmapCell(BaseModel):
    hand: str
    total_attempts: int
    correct_attempts: int
    accuracy_pct: Optional[float] = None
    median_response_ms: Optional[int] = None
    default_action: str
    default_color: str


class TopFailedHand(BaseModel):
    hand: str
    scenario_id: str
    scenario_name: str
    position: str
    stack_range: str
    total_attempts: int
    failures: int
    accuracy_pct: float
    correct_action: str
    correct_followup: Optional[str] = None
