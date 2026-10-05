import uuid
import json
import random
from datetime import datetime, timezone
from statistics import median
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.models.scenario import Scenario, ScenarioHand
from app.models.session import TrainingSession
from app.models.answer import Answer
from app.schemas.training import (
    SessionStartRequest,
    NextHandResponse,
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    TableStateSchema,
    VillainReaction,
    VisualCard,
    ActionOption
)
from app.services.table_state import (
    ACTION_STYLES,
    BY_STACK_LIST_KEYS,
    BY_STACK_MARGINAL_KEY,
    LIMP,
    VILLAIN_KINDS,
    VILLAIN_SEATS,
    action_label,
    build_action_options,
    build_table_payload,
    heads_up_from_game,
    random_effective_stack,
    resolve_followup_action,
    response_actions_for_kind,
    roll_villain,
    stack_key_for,
    villain_seats_for,
)
from app.tools.poker_utils import (
    ALL_169_HANDS,
    generate_visual_cards,
    find_borderline_hands,
    MATRIX_GRID
)


def build_hand_sampling_weight(
    hand_action: Optional[str],
    is_borderline: bool = False,
    total_attempts: int = 0,
) -> int:
    """Pondera las manos para que la práctica destaque manos activas, frontera y sin practicar."""
    weight = 1

    if hand_action and str(hand_action).upper() != "FOLD":
        weight *= 3
    if is_borderline:
        weight *= 2
    if total_attempts == 0:
        weight *= 2

    return weight


def _apply_scenario_appearance(options: List[ActionOption], actions_cfg: Dict[str, Any]) -> List[ActionOption]:
    """Color y atajo los manda el escenario. La etiqueta solo si CONFIG no la conoce."""
    for option in options:
        cfg = (actions_cfg or {}).get(option.id)
        if isinstance(cfg, dict):
            if cfg.get("label") and option.id not in ACTION_STYLES:
                option.label = cfg["label"]
            if cfg.get("color"):
                option.color = cfg["color"]
            if cfg.get("hotkey"):
                option.hotkey = cfg["hotkey"]
    return options


def _opening_options(actions_cfg: Dict[str, Any]) -> List[ActionOption]:
    """
    PASO 0: los botones salen del catalogo 'actions' del escenario, en su orden.
    Que accion abre followup lo declara el propio JSON con has_followup.
    """
    action_ids = tuple((actions_cfg or {}).keys())
    if not action_ids:
        action_ids = ("OPEN_SHOVE", "OR", "FOLD")

    options = build_action_options(action_ids)
    for option in options:
        cfg = (actions_cfg or {}).get(option.id)
        option.has_followup = bool(isinstance(cfg, dict) and cfg.get("has_followup", False))
    return _apply_scenario_appearance(options, actions_cfg)


def _response_options(kind: str) -> List[ActionOption]:
    """Botones del PASO 2/3: vs all-in solo Fold/Call, vs normal agrega All-in."""
    return build_action_options(response_actions_for_kind(kind), has_followup=False)


def _table_schema(payload: Dict[str, Any]) -> TableStateSchema:
    return TableStateSchema(**payload)


def _is_limp(action: Optional[str]) -> bool:
    """True si la accion de hero fue un limp (solo posible en heads-up)."""
    return str(action or "").strip().upper() == "LIMP"


def _roll_for_scenario(
    scenario: Scenario, parent_action: Optional[str] = None
) -> Dict[str, str]:
    """
    PASO 2 - Sortea la respuesta del rival.

    En heads-up solo hay un rival, asi que su asiento lo fija la posicion de
    hero y unicamente se sortea el tipo de raise. En defensa de la BB el tipo
    no se sortea: la data solo contempla el shove del SB.
    """
    heads_up = heads_up_from_game(scenario.game)
    seats = villain_seats_for(scenario.position, heads_up)
    return roll_villain(
        heads_up=heads_up,
        seats=seats,
        after_limp=_is_limp(parent_action),
        spot=scenario.spot,
    )


def _by_stack_entry(scenario: Scenario, effective_stack: float) -> Dict[str, Any]:
    """
    La fila by_stack que decide la mano: la clave es floor(stack*2)/2.

    Si el stack cae fuera de la grilla (ej. un cliente viejo manda otro valor)
    se usa la clave mas cercana por abajo, nunca se revienta.
    """
    by_stack = scenario.by_stack or {}
    if not by_stack:
        return {}

    key = stack_key_for(effective_stack)
    if key in by_stack and isinstance(by_stack[key], dict):
        return by_stack[key]

    try:
        target = float(key)
        lower = [k for k in by_stack.keys() if float(k) <= target]
        fallback = max(lower, key=float) if lower else min(by_stack.keys(), key=float)
        entry = by_stack[fallback]
        return entry if isinstance(entry, dict) else {}
    except (ValueError, TypeError):
        return {}


def _by_stack_active_action(entry: Dict[str, Any]) -> str:
    """La accion activa del escenario (shove -> OPEN_SHOVE, call -> CALL)."""
    for list_key, action_id in BY_STACK_LIST_KEYS.items():
        if entry.get(list_key):
            return action_id
    return "FOLD"


def resolve_by_stack_action(
    scenario: Scenario, hand: str, effective_stack: float
) -> Tuple[str, bool]:
    """
    Respuesta correcta en un escenario by_stack: (accion, es_marginal).

    La mano se busca en la lista activa de su stack (shove o call); lo que no
    esta en ninguna lista toma la accion complementaria (fold). Estar en la
    lista 'marginal' no cambia la accion, solo evita la penalizacion.
    """
    entry = _by_stack_entry(scenario, effective_stack)
    if not entry:
        return "FOLD", False

    for list_key, action_id in BY_STACK_LIST_KEYS.items():
        if hand in (entry.get(list_key) or []):
            is_marginal = hand in (entry.get(BY_STACK_MARGINAL_KEY, []) or [])
            return action_id, is_marginal

    is_marginal = hand in (entry.get(BY_STACK_MARGINAL_KEY, []) or [])
    return "FOLD", is_marginal


def resolve_by_stack_table(
    scenario: Scenario, effective_stack: float
) -> Dict[str, Dict[str, Any]]:
    """Tabla completa hand -> {action, marginal} a un stack dado (las 169)."""
    table = {}
    for hand in ALL_169_HANDS:
        action, is_marginal = resolve_by_stack_action(scenario, hand, effective_stack)
        table[hand] = {"action": action, "marginal": is_marginal}
    return table


def default_by_stack_key(scenario: Scenario) -> Optional[str]:
    """La clave del medio de la grilla: el corte representativo para pintar."""
    keys = list((scenario.by_stack or {}).keys())
    if not keys:
        return None
    ordered = sorted(keys, key=float)
    return ordered[len(ordered) // 2]


def start_training_session(db: Session, req: SessionStartRequest) -> TrainingSession:
    # Validar que los escenarios existan
    scenarios = db.execute(
        select(Scenario).where(Scenario.id.in_(req.scenario_ids))
    ).scalars().all()

    if not scenarios:
        raise ValueError("Ninguno de los escenarios seleccionados existe en la base de datos.")

    session_id = str(uuid.uuid4())
    new_session = TrainingSession(
        id=session_id,
        started_at=datetime.now(timezone.utc),
        mode=req.mode,
        filter_config={
            "scenario_ids": req.scenario_ids,
            "mode": req.mode,
            "time_limit_seconds": req.time_limit_seconds,
            "hand_limit": req.hand_limit
        },
        total_hands=0,
        correct_hands=0
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def get_session_stats(db: Session, session_id: str) -> Dict[str, Any]:
    answers = db.execute(
        select(Answer)
        .where(Answer.session_id == session_id)
        .order_by(desc(Answer.id))
    ).scalars().all()

    total = len(answers)
    correct = sum(1 for a in answers if a.is_correct)
    pct = round((correct / total * 100), 1) if total > 0 else 0.0

    streak = 0
    for a in answers:
        if a.is_correct:
            streak += 1
        else:
            break

    response_ms = [a.response_ms for a in answers if a.response_ms > 0]
    median_ms = int(median(response_ms)) if response_ms else 0
    fast_correct = sum(1 for a in answers if a.is_correct and a.response_ms <= 2000)
    correct_fast_pct = round((fast_correct / correct * 100), 1) if correct > 0 else 0.0

    return {
        "total": total,
        "correct": correct,
        "pct": pct,
        "streak": streak,
        "median_response_ms": median_ms,
        "correct_fast_pct": correct_fast_pct,
    }


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_session_summary(db: Session, session_id: str) -> Dict[str, Any]:
    session_obj = db.execute(
        select(TrainingSession).where(TrainingSession.id == session_id)
    ).scalar_one_or_none()

    if not session_obj:
        raise ValueError(f"Sesión no encontrada: {session_id}")

    stats = get_session_stats(db, session_id)
    time_limit = session_obj.filter_config.get("time_limit_seconds")
    hand_limit = session_obj.filter_config.get("hand_limit")
    started_at = _as_utc(session_obj.started_at)

    remaining_seconds = None
    has_reached_time_limit = False
    has_reached_hand_limit = bool(hand_limit is not None and stats["total"] >= int(hand_limit))

    if session_obj.ended_at is not None:
        remaining_seconds = 0
        has_reached_time_limit = True
    elif time_limit is not None and started_at is not None:
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        remaining_seconds = max(0, int(int(time_limit) - elapsed))
        has_reached_time_limit = remaining_seconds <= 0

    if session_obj.ended_at is not None:
        has_reached_time_limit = True

    return {
        "session_id": session_id,
        "mode": session_obj.mode,
        "started_at": session_obj.started_at.isoformat(),
        "ended_at": session_obj.ended_at.isoformat() if session_obj.ended_at else None,
        "scenario_ids": session_obj.filter_config.get("scenario_ids", []),
        "total_hands": stats["total"],
        "correct_hands": stats["correct"],
        "accuracy_pct": stats["pct"],
        "median_response_ms": stats["median_response_ms"],
        "correct_fast_pct": stats["correct_fast_pct"],
        "time_limit_seconds": int(time_limit) if time_limit is not None else None,
        "hand_limit": int(hand_limit) if hand_limit is not None else None,
        "remaining_time_seconds": remaining_seconds,
        "has_reached_time_limit": has_reached_time_limit,
        "has_reached_hand_limit": has_reached_hand_limit,
    }


def get_next_training_hand(
    db: Session,
    session_id: str,
    scenario_id: Optional[str] = None,
    hand: Optional[str] = None,
    level: int = 1,
    parent_action: Optional[str] = None
) -> NextHandResponse:
    session_obj = db.execute(
        select(TrainingSession).where(TrainingSession.id == session_id)
    ).scalar_one_or_none()

    if not session_obj:
        raise ValueError(f"Sesión no encontrada: {session_id}")

    if session_obj.ended_at is not None:
        raise ValueError("La sesión ya está finalizada.")

    hand_limit = session_obj.filter_config.get("hand_limit")
    time_limit = session_obj.filter_config.get("time_limit_seconds")

    if hand_limit is not None and session_obj.total_hands >= int(hand_limit):
        raise ValueError("Se ha alcanzado el límite de manos de la sesión.")

    if time_limit is not None:
        started_at = _as_utc(session_obj.started_at)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds() if started_at else 0
        if elapsed >= int(time_limit):
            session_obj.ended_at = datetime.now(timezone.utc)
            db.commit()
            raise ValueError("Se ha agotado el tiempo límite de la sesión.")

    stats = get_session_stats(db, session_id)
    allowed_scenario_ids = session_obj.filter_config.get("scenario_ids", [])
    mode = session_obj.mode or "normal"

    # Nivel 2: Decisión subsiguiente vs 3bet para una mano que ya se jugó en Nivel 1
    if level == 2 and scenario_id and hand:
        scenario = db.execute(
            select(Scenario).where(Scenario.id == scenario_id)
        ).scalar_one_or_none()
        if not scenario:
            raise ValueError(f"Escenario {scenario_id} no encontrado.")

        # PASO 2 - el rival se elige AL AZAR: quien responde y que tipo de raise.
        # En heads-up el rival ya esta en su asiento y solo se sortea el tipo.
        # En defensa de la BB siempre empujan: no hay sorteo.
        after_limp = _is_limp(parent_action)
        villain = _roll_for_scenario(scenario, parent_action)
        spot_key = str(scenario.spot or "").strip().upper()

        if spot_key == "VS_LIMP":
            prompt = f"¿Qué haces con {hand} tras ISO ante el 3bet all-in del SB?"
        elif spot_key == "VS_MIN_RAISE":
            prompt = f"¿Qué haces con {hand} tras 3Bet ante el 4bet all-in del SB?"
        elif after_limp:
            prompt = f"¿Qué haces con {hand} tras un raise / raise All-In del rival?"
        else:
            prompt = f"¿Qué haces con {hand} tras OR ante un 3bet / 3bet All-In?"

        cards_data = generate_visual_cards(hand)
        visual_cards = [VisualCard(**c) for c in cards_data]

        return NextHandResponse(
            session_id=session_id,
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            position=scenario.position,
            stack_range=scenario.stack_range,
            spot=scenario.spot,
            tags=scenario.tags or [],
            hand=hand,
            cards=visual_cards,
            level=2,
            parent_action=parent_action or "OR",
            available_actions=_response_options(villain["kind"]),
            followup_prompt=prompt,
            current_streak=stats["streak"],
            session_hands_played=stats["total"],
            session_accuracy_pct=stats["pct"],
            heads_up=heads_up_from_game(scenario.game),
            villain=VillainReaction(**villain),
        )

    # Nivel 1: Selección del escenario y mano
    chosen_scenario_id = random.choice(allowed_scenario_ids)
    scenario = db.execute(
        select(Scenario).where(Scenario.id == chosen_scenario_id)
    ).scalar_one_or_none()
    if not scenario:
        raise ValueError(f"Escenario {chosen_scenario_id} no encontrado.")

    # Escenario por stack: no hay filas en scenario_hands. El stack se sortea
    # PRIMERO y la mano sale de la tabla de ese stack (las 169, con su accion
    # resuelta). Las marginales pesan como frontera.
    from types import SimpleNamespace

    by_stack_cfg = scenario.by_stack or {}
    pre_drawn_stack: Optional[float] = None
    if by_stack_cfg:
        pre_drawn_stack = random_effective_stack(
            scenario.stack_range, scenario.stack_min, scenario.stack_max
        )
        by_table = resolve_by_stack_table(scenario, pre_drawn_stack)
        hands_dict = {
            hand: SimpleNamespace(action=info["action"]) for hand, info in by_table.items()
        }
        borderline_set = {hand for hand, info in by_table.items() if info["marginal"]}
    else:
        hands_dict = {h.hand: h for h in scenario.hands}
        borderline_set = find_borderline_hands({h.hand: {"action": h.action} for h in scenario.hands})

    attempt_counts = db.execute(
        select(Answer.hand, func.count(Answer.id).label("count"))
        .where(Answer.scenario_id == scenario.id)
        .group_by(Answer.hand)
    ).all()
    attempt_counts_map = {hand: count for hand, count in attempt_counts}

    def weighted_hand_choice(candidates: List[str]) -> str:
        weights = []
        for hand in candidates:
            hand_record = hands_dict.get(hand)
            action = getattr(hand_record, "action", None) if hand_record else None
            weight = build_hand_sampling_weight(
                hand_action=action,
                is_borderline=hand in borderline_set,
                total_attempts=attempt_counts_map.get(hand, 0),
            )
            weights.append(weight)

        if not candidates:
            return random.choice(ALL_169_HANDS)

        return random.choices(candidates, weights=weights, k=1)[0]

    # Selección de mano según el modo
    chosen_hand = None

    if mode == "errors_only":
        failed_answers = db.execute(
            select(Answer.hand, func.count(Answer.id).label("fail_count"))
            .where(
                Answer.scenario_id == scenario.id,
                Answer.is_correct == False
            )
            .group_by(Answer.hand)
            .order_by(desc("fail_count"))
            .limit(30)
        ).all()

        if failed_answers:
            hands_pool = []
            weights = []
            for h, count in failed_answers:
                hands_pool.append(h)
                hand_record = hands_dict.get(h)
                action = getattr(hand_record, "action", None) if hand_record else None
                weight = build_hand_sampling_weight(
                    hand_action=action,
                    is_borderline=h in borderline_set,
                    total_attempts=attempt_counts_map.get(h, 0),
                )
                weights.append(max(1, weight * (count + 1)))
            chosen_hand = random.choices(hands_pool, weights=weights, k=1)[0]
        else:
            candidate_hands = list(borderline_set) if borderline_set else ALL_169_HANDS
            chosen_hand = weighted_hand_choice(candidate_hands)

    elif mode == "borderline":
        candidate_hands = list(borderline_set) if borderline_set else ALL_169_HANDS
        chosen_hand = weighted_hand_choice(candidate_hands)

    else:
        chosen_hand = weighted_hand_choice(list(hands_dict.keys()))

    # Opciones de acciones base
    actions_cfg = scenario.actions_config or {}
    available_actions = _opening_options(actions_cfg)

    cards_data = generate_visual_cards(chosen_hand)
    visual_cards = [VisualCard(**c) for c in cards_data]

    # PASO 0 - REPARTO: stack efectivo sale del rango del escenario.
    # En heads-up hero ocupa una ciega, asi que ya postea su ficha antes de hablar.
    # En by_stack el stack ya se sorteo arriba, antes de elegir la mano.
    effective_stack = (
        pre_drawn_stack
        if pre_drawn_stack is not None
        else random_effective_stack(
            scenario.stack_range, scenario.stack_min, scenario.stack_max
        )
    )
    heads_up = heads_up_from_game(scenario.game)

    return NextHandResponse(
        session_id=session_id,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        position=scenario.position,
        stack_range=scenario.stack_range,
        spot=scenario.spot,
        tags=scenario.tags or [],
        hand=chosen_hand,
        cards=visual_cards,
        level=1,
        parent_action=None,
        available_actions=available_actions,
        followup_prompt=None,
        current_streak=stats["streak"],
        session_hands_played=stats["total"],
        session_accuracy_pct=stats["pct"],
        table=_table_schema(
            build_table_payload(
                effective_stack,
                scenario.stack_range,
                heads_up=heads_up,
                hero_position=scenario.position,
                spot=scenario.spot,
            )
        ),
        heads_up=heads_up,
    )


def build_full_matrix_dict(
    scenario: Scenario, effective_stack: Optional[float] = None
) -> Dict[str, Any]:
    """
    Matriz completa del escenario, lista para consultar la mano juzgada.

    En by_stack la respuesta depende del stack: se pinta el corte de la mano
    en curso (o el corte del medio si no se pasa stack). Las marginales van
    con su accion de todos modos y marcadas, para que la matriz no mienta.
    """
    matrix_hands = {}
    actions_cfg = scenario.actions_config or {}
    followups_cfg = scenario.followups_config or {}

    if scenario.by_stack:
        stack = effective_stack
        if stack is None:
            middle = default_by_stack_key(scenario)
            stack = float(middle) if middle is not None else 0.0
        by_table = resolve_by_stack_table(scenario, stack)

        for hand, info in by_table.items():
            action_data = actions_cfg.get(info["action"], {})
            matrix_hands[hand] = {
                "action": info["action"],
                "action_label": action_data.get("label", info["action"]),
                "color": action_data.get("color", "#CCCCCC"),
                "followup": None,
                "followup_label": None,
                "followup_color": None,
                "frequency": 100.0,
                "marginal": bool(info["marginal"]),
                "stack": stack_key_for(stack),
            }
        return matrix_hands

    for h in scenario.hands:
        action_data = actions_cfg.get(h.action, {})
        inline = _parse_followup_ref(h.followup_action)
        if isinstance(inline, dict):
            # Followup inline por mano (ej. {"vs_4bet_ai": "CALL"}): se muestra
            # la respuesta resuelta, que es lo que el jugador debe hacer.
            resolved = resolve_followup_action({}, inline, "ai", spot=scenario.spot)
            followup_data = None
            followup_key = resolved
            followup_label = action_label(resolved) if resolved else None
        else:
            followup_data = followups_cfg.get(h.followup_action, {}) if h.followup_action else None
            followup_key = h.followup_action
            followup_label = followup_data.get("label") if followup_data else None

        matrix_hands[h.hand] = {
            "action": h.action,
            "action_label": action_data.get("label", h.action),
            "color": action_data.get("color", "#CCCCCC"),
            "followup": followup_key,
            "followup_label": followup_label,
            "followup_color": followup_data.get("color") if followup_data else None,
            "frequency": h.frequency
        }
    return matrix_hands


def submit_training_answer(db: Session, req: AnswerSubmitRequest) -> AnswerSubmitResponse:
    scenario = db.execute(
        select(Scenario).where(Scenario.id == req.scenario_id)
    ).scalar_one_or_none()
    if not scenario:
        raise ValueError(f"Escenario {req.scenario_id} no encontrado.")

    hand_record = db.execute(
        select(ScenarioHand).where(
            ScenarioHand.scenario_id == req.scenario_id,
            ScenarioHand.hand == req.hand
        )
    ).scalar_one_or_none()
    # Los escenarios by_stack no tienen filas en scenario_hands: la respuesta
    # correcta se resuelve contra la tabla del stack, nunca se revienta.
    is_by_stack = bool(scenario.by_stack)
    if not hand_record and not is_by_stack:
        raise ValueError(f"Mano {req.hand} no encontrada en el escenario {req.scenario_id}.")

    actions_cfg = scenario.actions_config or {}
    followups_cfg = scenario.followups_config or {}
    heads_up = heads_up_from_game(scenario.game)

    is_correct = False
    correct_action = ""
    correct_followup = hand_record.followup_action if hand_record else None
    explanation = ""
    needs_level_2 = False

    villain: Optional[Dict[str, str]] = None
    next_actions: Optional[List[ActionOption]] = None

    # Stack efectivo de la mano. Si el cliente no lo manda, se sortea del rango
    # del escenario (stack_min/stack_max si los declara, si no stack_range).
    effective_stack = req.effective_stack or random_effective_stack(
        scenario.stack_range, scenario.stack_min, scenario.stack_max
    )

    if req.level == 1:
        if is_by_stack:
            # Push/fold o call/fold por stack: sin followup, sin segundo nivel.
            correct_action, is_marginal = resolve_by_stack_action(
                scenario, req.hand, effective_stack
            )
            chosen = req.chosen_action.strip().upper()
            correct_action_label = action_label(correct_action)
            stack_label = stack_key_for(effective_stack)

            if is_marginal:
                # La mano marginal no se penaliza: cualquiera de las dos vale.
                is_correct = True
                active_label = action_label(_by_stack_active_action(
                    _by_stack_entry(scenario, effective_stack)
                ))
                explanation = (
                    f"Marginal a {stack_label} BB: vale {active_label} "
                    f"y vale {correct_action_label}."
                )
            elif chosen == correct_action.strip().upper():
                is_correct = True
                explanation = f"¡Correcto! {correct_action_label} para {req.hand}."
            else:
                explanation = f"Incorrecto. Era {correct_action_label}."
        else:
            correct_action = hand_record.action
            is_correct = (req.chosen_action.strip().upper() == correct_action.strip().upper())
            # Misma etiqueta que muestra el boton, para que feedback y botones no se contradigan.
            correct_action_label = action_label(
                correct_action, (actions_cfg.get(correct_action, {}) or {}).get("label")
            )

            action_def = actions_cfg.get(correct_action, {})
            has_followup = action_def.get("has_followup", False)

            if is_correct:
                if has_followup and hand_record.followup_action:
                    # Accion correcta -> PASO 2: el rival responde al azar y sigue.
                    needs_level_2 = True
                    villain = _roll_for_scenario(scenario, req.chosen_action)
                    next_actions = _response_options(villain["kind"])
                    explanation = f"¡Correcto! {correct_action_label}. {villain['label']}."
                else:
                    explanation = f"¡Correcto! {correct_action_label} para {req.hand}."
            else:
                explanation = f"Incorrecto. Era {correct_action_label}."

    elif req.level == 2 and is_by_stack:
        # No hay followup en by_stack; si llega un nivel 2 se califica igual
        # que el nivel 1 para no castigar un estado imposible.
        correct_action, is_marginal = resolve_by_stack_action(
            scenario, req.hand, effective_stack
        )
        is_correct = is_marginal or (
            req.chosen_action.strip().upper() == correct_action.strip().upper()
        )
        correct_label = action_label(correct_action)
        explanation = (
            f"¡Correcto! {correct_label}." if is_correct
            else f"Incorrecto. Era {correct_label}."
        )

    elif req.level == 2:
        # El followup declara una respuesta distinta segun el tipo de 3bet que ocurrio.
        villain_kind = (req.villain_kind or "normal").strip().lower()
        if villain_kind not in VILLAIN_KINDS:
            raise ValueError(f"Tipo de 3bet desconocido: {req.villain_kind}")

        villain_actor = req.villain_actor or "SB"
        if villain_actor not in VILLAIN_SEATS:
            raise ValueError(f"Rival desconocido: {req.villain_actor}")

        villain = {"actor": villain_actor, "kind": villain_kind}

        # Tras OR el rival hace un 3bet (clave vs_3bet); tras LIMP hace un raise
        # (clave vs_raise); tras el 3bet de la BB el SB responde con 4bet all-in
        # (clave vs_4bet_ai). El followup puede venir del catalogo o inline.
        after_limp = _is_limp(req.parent_action)
        followup_ref = _parse_followup_ref(hand_record.followup_action)
        correct_action = resolve_followup_action(
            followups_cfg, followup_ref, villain_kind,
            after_limp=after_limp, spot=scenario.spot,
        ) or ""
        is_correct = (req.chosen_action.strip().upper() == correct_action.strip().upper())

        correct_label = action_label(correct_action)

        if is_correct:
            explanation = (
                f"¡Correcto! {correct_label} ante el "
                f"{villain_kind_label(villain_kind, after_limp, scenario.spot)}."
            )
        else:
            explanation = f"Incorrecto. Era {correct_label}."

    # Estado final de la mesa. Se deriva de la secuencia, nunca se escribe a mano.
    if req.level == 2 and villain is not None:
        # En el nivel 2 hay que reconstruir desde la accion del nivel 1, que el
        # cliente manda en parent_action (OR, LIMP, OPEN_SHOVE...).
        table_payload = build_table_payload(
            effective_stack,
            scenario.stack_range,
            action=req.parent_action or "OR",
            villain=villain,
            hero_response=req.chosen_action,
            heads_up=heads_up,
            hero_position=scenario.position,
            spot=scenario.spot,
        )
    else:
        table_payload = build_table_payload(
            effective_stack,
            scenario.stack_range,
            action=req.chosen_action,
            villain=villain,
            heads_up=heads_up,
            hero_position=scenario.position,
            spot=scenario.spot,
        )

    # Guardar respuesta en BD
    answer_obj = Answer(
        session_id=req.session_id,
        scenario_id=req.scenario_id,
        hand=req.hand,
        level=req.level,
        chosen_action=req.chosen_action,
        correct_action=correct_action,
        is_correct=is_correct,
        response_ms=req.response_ms,
        created_at=datetime.now(timezone.utc)
    )
    db.add(answer_obj)

    # Actualizar contador de la sesión
    session_obj = db.execute(
        select(TrainingSession).where(TrainingSession.id == req.session_id)
    ).scalar_one_or_none()

    if session_obj:
        if session_obj.ended_at is not None:
            raise ValueError("La sesión ya está finalizada.")

        session_obj.total_hands += 1
        if is_correct:
            session_obj.correct_hands += 1

        hand_limit = session_obj.filter_config.get("hand_limit")
        if hand_limit is not None and session_obj.total_hands >= int(hand_limit):
            session_obj.ended_at = datetime.now(timezone.utc)

    db.commit()

    stats = get_session_stats(db, req.session_id)

    # Matriz completa del escenario, lista para consultar la mano juzgada.
    # En by_stack se pinta el corte del stack de la mano en curso.
    full_matrix = build_full_matrix_dict(scenario, effective_stack)

    return AnswerSubmitResponse(
        is_correct=is_correct,
        level=req.level,
        chosen_action=req.chosen_action,
        correct_action=correct_action,
        correct_followup=correct_followup,
        explanation=explanation,
        response_ms=req.response_ms,
        needs_level_2=needs_level_2,
        next_level=2 if needs_level_2 else 1,
        current_streak=stats["streak"],
        session_total_hands=stats["total"],
        session_correct_hands=stats["correct"],
        session_accuracy_pct=stats["pct"],
        full_matrix=full_matrix,
        actions_config=actions_cfg,
        followups_config=followups_cfg,
        table=_table_schema(table_payload),
        heads_up=heads_up,
        villain=VillainReaction(**villain) if villain and req.level == 1 else None,
        next_actions=next_actions,
    )


def _parse_followup_ref(followup_action: Optional[str]) -> Optional[object]:
    """
    El followup de una mano es una clave al catalogo ('4BET_AI') o un dict
    inline serializado ('{"vs_4bet_ai": "CALL"}'). Devuelve el dict cuando
    corresponde para resolver la variante sin catalogo.
    """
    if not followup_action:
        return None
    text = str(followup_action).strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return text


def villain_kind_label(kind: str, after_limp: bool = False, spot: Optional[str] = None) -> str:
    """Texto del raise del rival para el feedback (3bet tras OR, raise tras LIMP, 4bet tras 3bet)."""
    if str(spot or "").strip().upper() == "VS_MIN_RAISE":
        return "4bet all-in"
    if after_limp:
        return "raise all-in" if kind == "ai" else "raise"
    return "3bet all-in" if kind == "ai" else "3bet"
