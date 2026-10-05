from datetime import datetime, timedelta
from statistics import median
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc, case, and_

from app.models.answer import Answer
from app.models.scenario import Scenario, ScenarioHand
from app.models.session import TrainingSession
from app.schemas.stats import (
    StatsOverview,
    AccuracyPoint,
    CategoryAccuracy,
    HandHeatmapCell,
    TopFailedHand
)
from app.tools.poker_utils import ALL_169_HANDS, MATRIX_GRID


def _median_or_zero(values: List[int]) -> int:
    if not values:
        return 0
    return int(median(values))


def get_stats_overview(
    db: Session,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> StatsOverview:
    query = select(
        func.count(Answer.id).label("total"),
        func.sum(case((Answer.is_correct == True, 1), else_=0)).label("correct"),
        func.avg(Answer.response_ms).label("avg_ms")
    )

    conditions = []
    if from_date:
        conditions.append(Answer.created_at >= from_date)
    if to_date:
        conditions.append(Answer.created_at <= to_date)

    if conditions:
        query = query.where(and_(*conditions))

    row = db.execute(query).one()
    total = row.total or 0
    correct = row.correct or 0
    avg_ms = int(row.avg_ms or 0)
    pct = round((correct / total * 100), 1) if total > 0 else 0.0

    response_ms_rows = db.execute(
        select(Answer.response_ms)
        .where(and_(*conditions)) if conditions else select(Answer.response_ms)
    ).scalars().all()
    median_ms = _median_or_zero(response_ms_rows)

    fast_correct_count = db.execute(
        select(func.count(Answer.id))
        .where(
            Answer.is_correct == True,
            Answer.response_ms <= 2000,
            *conditions,
        ) if conditions else
        select(func.count(Answer.id)).where(Answer.is_correct == True, Answer.response_ms <= 2000)
    ).scalar_one() or 0
    correct_fast_pct = round((fast_correct_count / correct * 100), 1) if correct > 0 else 0.0

    # Sesiones totales
    session_count_query = select(func.count(TrainingSession.id))
    if conditions:
        session_count_query = session_count_query.where(
            and_(*[c.replace(Answer.created_at, TrainingSession.started_at) for c in conditions])
        )
    total_sessions = db.execute(session_count_query).scalar_one() or 0

    # Racha actual y mejor racha histórica
    all_answers = db.execute(
        select(Answer.is_correct)
        .order_by(Answer.id.asc())
    ).scalars().all()

    current_streak = 0
    best_streak = 0
    temp_streak = 0

    for is_corr in all_answers:
        if is_corr:
            temp_streak += 1
            if temp_streak > best_streak:
                best_streak = temp_streak
        else:
            temp_streak = 0

    # La racha actual se calcula desde el final hacia atrás
    for is_corr in reversed(all_answers):
        if is_corr:
            current_streak += 1
        else:
            break

    return StatsOverview(
        total_answers=total,
        total_correct=correct,
        global_accuracy_pct=pct,
        avg_response_ms=avg_ms,
        median_response_ms=median_ms,
        correct_fast_pct=correct_fast_pct,
        current_streak=current_streak,
        best_streak=best_streak,
        total_sessions=total_sessions
    )


def get_accuracy_over_time(
    db: Session,
    group_by: str = "day",
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> List[AccuracyPoint]:
    """
    Agrupa precisión y tiempo medio de respuesta por día o semana usando SQLite strftime.
    """
    date_format = "%Y-%m-%d" if group_by == "day" else "%Y-%W"
    date_col = func.strftime(date_format, Answer.created_at).label("period")

    query = select(
        date_col,
        func.count(Answer.id).label("total"),
        func.sum(case((Answer.is_correct == True, 1), else_=0)).label("correct"),
        func.avg(Answer.response_ms).label("avg_ms")
    )

    conditions = []
    if from_date:
        conditions.append(Answer.created_at >= from_date)
    if to_date:
        conditions.append(Answer.created_at <= to_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.group_by("period").order_by("period")
    rows = db.execute(query).all()

    points = []
    for r in rows:
        tot = r.total or 0
        corr = r.correct or 0
        accuracy = round((corr / tot * 100), 1) if tot > 0 else 0.0
        points.append(
            AccuracyPoint(
                date=r.period,
                accuracy_pct=accuracy,
                avg_response_ms=int(r.avg_ms or 0),
                total_hands=tot
            )
        )
    return points


def get_accuracy_by_category(
    db: Session,
    category: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None
) -> List[CategoryAccuracy]:
    """
    Agrupa por 'position', 'stack_range' o 'scenario'.
    """
    if category == "position":
        group_col = Scenario.position
        label_col = Scenario.position
    elif category == "stack_range":
        group_col = Scenario.stack_range
        label_col = Scenario.stack_range
    elif category == "scenario":
        group_col = Scenario.id
        label_col = Scenario.name
    else:
        raise ValueError(f"Categoría no válida: {category}")

    query = (
        select(
            group_col.label("cat_key"),
            label_col.label("cat_label"),
            func.count(Answer.id).label("total"),
            func.sum(case((Answer.is_correct == True, 1), else_=0)).label("correct"),
            func.avg(Answer.response_ms).label("avg_ms")
        )
        .join(Scenario, Answer.scenario_id == Scenario.id)
    )

    conditions = []
    if from_date:
        conditions.append(Answer.created_at >= from_date)
    if to_date:
        conditions.append(Answer.created_at <= to_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.group_by("cat_key", "cat_label").order_by(desc("total"))
    rows = db.execute(query).all()

    results = []
    for r in rows:
        tot = r.total or 0
        corr = r.correct or 0
        accuracy = round((corr / tot * 100), 1) if tot > 0 else 0.0
        results.append(
            CategoryAccuracy(
                category=str(r.cat_key),
                label=str(r.cat_label),
                total_hands=tot,
                correct_hands=corr,
                accuracy_pct=accuracy,
                avg_response_ms=int(r.avg_ms or 0)
            )
        )
    return results


def get_scenario_heatmap(db: Session, scenario_id: str) -> List[HandHeatmapCell]:
    """
    Calcula la precisión por celda para cada una de las 169 manos del escenario.
    """
    scenario = db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    ).scalar_one_or_none()
    if not scenario:
        raise ValueError(f"Escenario {scenario_id} no encontrado.")

    # Respuestas agrupadas por mano
    stats_rows = db.execute(
        select(
            Answer.hand,
            func.count(Answer.id).label("total"),
            func.sum(case((Answer.is_correct == True, 1), else_=0)).label("correct")
        )
        .where(Answer.scenario_id == scenario_id)
        .group_by(Answer.hand)
    ).all()

    response_ms_by_hand = {}
    response_rows = db.execute(
        select(Answer.hand, Answer.response_ms)
        .where(Answer.scenario_id == scenario_id)
    ).all()
    for hand, response_ms in response_rows:
        response_ms_by_hand.setdefault(hand, []).append(response_ms)

    stats_map = {r.hand: (r.total, r.correct) for r in stats_rows}
    actions_cfg = scenario.actions_config or {}

    cells = []
    for h in scenario.hands:
        hand_stats = stats_map.get(h.hand, (0, 0))
        tot, corr = hand_stats
        acc = round((corr / tot * 100), 1) if tot > 0 else None
        median_ms = None
        if response_ms_by_hand.get(h.hand):
            median_ms = _median_or_zero(response_ms_by_hand[h.hand])
        action_data = actions_cfg.get(h.action, {})
        default_color = action_data.get("color", "#64748B")

        cells.append(
            HandHeatmapCell(
                hand=h.hand,
                total_attempts=tot,
                correct_attempts=corr,
                accuracy_pct=acc,
                median_response_ms=median_ms,
                default_action=h.action,
                default_color=default_color
            )
        )

    return cells


def get_top_failed_hands(
    db: Session,
    limit: int = 20,
    scenario_id: Optional[str] = None
) -> List[TopFailedHand]:
    """
    Ranking de las manos más falladas.
    """
    query = (
        select(
            Answer.hand,
            Answer.scenario_id,
            Scenario.name.label("scenario_name"),
            Scenario.position,
            Scenario.stack_range,
            func.count(Answer.id).label("total_attempts"),
            func.sum(case((Answer.is_correct == False, 1), else_=0)).label("failures"),
            ScenarioHand.action.label("correct_action"),
            ScenarioHand.followup_action.label("correct_followup")
        )
        .join(Scenario, Answer.scenario_id == Scenario.id)
        .join(
            ScenarioHand,
            and_(
                ScenarioHand.scenario_id == Answer.scenario_id,
                ScenarioHand.hand == Answer.hand
            )
        )
    )

    if scenario_id:
        query = query.where(Answer.scenario_id == scenario_id)

    query = (
        query
        .group_by(
            Answer.hand,
            Answer.scenario_id,
            Scenario.name,
            Scenario.position,
            Scenario.stack_range,
            ScenarioHand.action,
            ScenarioHand.followup_action
        )
        .having(func.sum(case((Answer.is_correct == False, 1), else_=0)) > 0)
        .order_by(desc("failures"), desc("total_attempts"))
        .limit(limit)
    )

    rows = db.execute(query).all()
    results = []
    for r in rows:
        tot = r.total_attempts or 0
        fails = r.failures or 0
        corr = tot - fails
        accuracy = round((corr / tot * 100), 1) if tot > 0 else 0.0
        results.append(
            TopFailedHand(
                hand=r.hand,
                scenario_id=r.scenario_id,
                scenario_name=r.scenario_name,
                position=r.position,
                stack_range=r.stack_range,
                total_attempts=tot,
                failures=fails,
                accuracy_pct=accuracy,
                correct_action=r.correct_action,
                correct_followup=r.correct_followup
            )
        )
    return results


def get_strengths_and_weaknesses(db: Session) -> Dict[str, Any]:
    """
    Compara las áreas más fuertes vs más débiles (posiciones, rangos de stack y escenarios).
    """
    by_pos = get_accuracy_by_category(db, "position")
    by_stack = get_accuracy_by_category(db, "stack_range")
    by_scen = get_accuracy_by_category(db, "scenario")

    def sort_best_worst(items: List[CategoryAccuracy]):
        filtered = [it for it in items if it.total_hands >= 1]
        sorted_items = sorted(filtered, key=lambda x: x.accuracy_pct, reverse=True)
        if len(sorted_items) == 1:
            return {
                "best": sorted_items[0],
                "worst": None,
                "all": sorted_items,
                "insufficient_data": True,
            }

        return {
            "best": sorted_items[0] if sorted_items else None,
            "worst": sorted_items[-1] if sorted_items else None,
            "all": sorted_items,
            "insufficient_data": False,
        }

    return {
        "positions": sort_best_worst(by_pos),
        "stack_ranges": sort_best_worst(by_stack),
        "scenarios": sort_best_worst(by_scen)
    }
