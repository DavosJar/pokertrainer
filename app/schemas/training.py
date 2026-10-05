from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class VisualCard(BaseModel):
    rank: str
    suit: str
    symbol: str
    name: str
    color: str
    textColor: str


class ActionOption(BaseModel):
    id: str
    label: str
    color: str
    hotkey: Optional[str] = None
    has_followup: bool = False
    text_color: Optional[str] = None


class SeatAmounts(BaseModel):
    """Fichas en mesa y stacks derivados. El frontend no calcula nada."""

    sb: Optional[float] = None
    bb: Optional[float] = None
    hero: Optional[float] = None


class SeatStacks(BaseModel):
    sb: float = 0.0
    bb: float = 0.0
    hero: float = 0.0


class SeatFlags(BaseModel):
    sb: bool = False
    bb: bool = False


class SeatAllIn(BaseModel):
    sb: bool = False
    bb: bool = False
    hero: bool = False


class TableStateSchema(BaseModel):
    """Estado de la mesa en un instante. Los montos ya vienen calculados."""

    effective_stack: float
    pot: float
    dead: float = 0.0
    bets: SeatAmounts = Field(default_factory=SeatAmounts)
    stacks: SeatStacks = Field(default_factory=SeatStacks)
    all_in: SeatAllIn = Field(default_factory=SeatAllIn)
    folded: SeatFlags = Field(default_factory=SeatFlags)


class VillainReaction(BaseModel):
    """PASO 2: que rival responde y de que tipo."""

    actor: str
    kind: str  # "normal" | "ai"
    label: str


class SessionStartRequest(BaseModel):
    scenario_ids: List[str] = Field(..., min_length=1)
    mode: str = Field(default="normal")  # "normal", "errors_only", "borderline"
    time_limit_seconds: Optional[int] = None
    hand_limit: Optional[int] = None


class SessionStartResponse(BaseModel):
    session_id: str
    mode: str
    started_at: str
    scenario_ids: List[str]
    total_scenarios: int
    time_limit_seconds: Optional[int] = None
    hand_limit: Optional[int] = None


class SessionStatusResponse(BaseModel):
    session_id: str
    mode: str
    started_at: str
    ended_at: Optional[str] = None
    scenario_ids: List[str]
    total_hands: int
    correct_hands: int
    accuracy_pct: float
    median_response_ms: int = 0
    correct_fast_pct: float = 0.0
    time_limit_seconds: Optional[int] = None
    hand_limit: Optional[int] = None
    remaining_time_seconds: Optional[int] = None
    has_reached_time_limit: bool = False
    has_reached_hand_limit: bool = False


class NextHandResponse(BaseModel):
    session_id: str
    scenario_id: str
    scenario_name: str
    position: str
    stack_range: str
    spot: str
    tags: List[str]
    hand: str
    cards: List[VisualCard]
    level: int  # 1 = Base Action, 2 = Followup vs 3bet
    parent_action: Optional[str] = None
    available_actions: List[ActionOption]
    followup_prompt: Optional[str] = None
    # True si la mesa es de 2 asientos: hero en una ciega y un solo rival.
    heads_up: bool = False
    current_streak: int = 0
    session_hands_played: int = 0
    session_accuracy_pct: float = 0.0
    # Mesa y rival: el cliente solo dibuja, no calcula.
    table: Optional[TableStateSchema] = None
    villain: Optional[VillainReaction] = None


class AnswerSubmitRequest(BaseModel):
    session_id: str
    scenario_id: str
    hand: str
    level: int  # 1 o 2
    chosen_action: str
    response_ms: int = Field(default=0, ge=0)
    # Que chose hero en el PASO 1. Necesario en el nivel 2 para saber si el
    # rival respondio a un 3bet (tras OR) o a un raise (tras LIMP).
    parent_action: Optional[str] = None
    # Stack efectivo repartido en PASO 0 (para reconstruir la mesa en el PASO 3).
    effective_stack: Optional[float] = Field(default=None, gt=0)
    # PASO 2: rival que respondio, necesario para saber si se evalua vs_3bet o vs_3bet_ai.
    villain_actor: Optional[str] = None
    villain_kind: Optional[str] = None


class AnswerSubmitResponse(BaseModel):
    is_correct: bool
    level: int
    chosen_action: str
    correct_action: str
    correct_followup: Optional[str] = None
    explanation: str
    response_ms: int
    needs_level_2: bool = False  # Si acertó nivel 1 y la acción tiene followup
    next_level: Optional[int] = None
    current_streak: int
    session_total_hands: int
    session_correct_hands: int
    session_accuracy_pct: float
    full_matrix: Optional[Dict[str, Any]] = None  # Enviado si falló o si se solicita
    actions_config: Optional[Dict[str, Any]] = None
    followups_config: Optional[Dict[str, Any]] = None
    # Estado de mesa resultante y, si abre el PASO 2, los botones del siguiente paso.
    table: Optional[TableStateSchema] = None
    heads_up: bool = False
    villain: Optional[VillainReaction] = None
    next_actions: Optional[List[ActionOption]] = None