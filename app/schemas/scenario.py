from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ScenarioFilter(BaseModel):
    positions: Optional[List[str]] = None
    stack_ranges: Optional[List[str]] = None
    spots: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ActionConfigItem(BaseModel):
    label: str
    color: str
    hotkey: Optional[str] = None
    has_followup: Optional[bool] = False


class FollowupConfigItem(BaseModel):
    label: str
    color: str
    vs_3bet: Optional[str] = None
    vs_3bet_ai: Optional[str] = None


class ScenarioListItem(BaseModel):
    id: str
    name: str
    position: str
    stack_range: str
    spot: str
    game: str = "SPIN_3MAX"
    tags: List[str] = Field(default_factory=list)
    action_counts: Dict[str, int] = Field(default_factory=dict)
    actions_config: Dict[str, Any] = Field(default_factory=dict)
    total_hands: int = 169

    model_config = ConfigDict(from_attributes=True)


class HandDetail(BaseModel):
    hand: str
    action: str
    followup: Optional[str] = None
    frequency: float = 100.0
    marginal: bool = False


class ScenarioDetail(BaseModel):
    id: str
    name: str
    position: str
    stack_range: str
    spot: str
    game: str
    tags: List[str]
    actions_config: Dict[str, Any]
    followups_config: Dict[str, Any]
    reference_stats: Optional[Dict[str, Any]] = None
    hands: Dict[str, HandDetail]
    # Solo en escenarios by_stack: los cortes disponibles y cual se pinta.
    by_stack_keys: List[str] = Field(default_factory=list)
    hands_stack: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
