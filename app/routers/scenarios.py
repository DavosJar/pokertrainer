from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.scenario import Scenario, ScenarioHand
from app.schemas.scenario import ScenarioListItem, ScenarioDetail, HandDetail
from app.services.importer import sync_all_scenarios
from app.services.training_service import (
    default_by_stack_key,
    resolve_by_stack_table,
)

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])


@router.get("", response_model=List[ScenarioListItem])
def list_scenarios(
    position: Optional[str] = Query(None, description="Filtrar por posición: BTN, SB, BB"),
    stack_range: Optional[str] = Query(None, description="Filtrar por rango de stack"),
    spot: Optional[str] = Query(None, description="Filtrar por spot"),
    tag: Optional[str] = Query(None, description="Filtrar por tag"),
    db: Session = Depends(get_db)
):
    query = select(Scenario)
    if position:
        query = query.where(Scenario.position == position.upper())
    if stack_range:
        query = query.where(Scenario.stack_range == stack_range)
    if spot:
        query = query.where(Scenario.spot == spot)

    scenarios = db.execute(query).scalars().all()

    result = []
    for sc in scenarios:
        if tag and tag.upper() not in [t.upper() for t in (sc.tags or [])]:
            continue

        # Contar manos por acción. En by_stack no hay filas: se cuenta el
        # corte del medio, el mismo que pinta el explorador por defecto.
        if sc.by_stack:
            middle = default_by_stack_key(sc)
            stack = float(middle) if middle is not None else 0.0
            by_table = resolve_by_stack_table(sc, stack)
            action_counts = {}
            for info in by_table.values():
                action_counts[info["action"]] = action_counts.get(info["action"], 0) + 1
            total = len(by_table)
        else:
            action_counts = {}
            for h in sc.hands:
                action_counts[h.action] = action_counts.get(h.action, 0) + 1
            total = len(sc.hands)

        result.append(
            ScenarioListItem(
                id=sc.id,
                name=sc.name,
                position=sc.position,
                stack_range=sc.stack_range,
                spot=sc.spot,
                game=sc.game or "SPIN_3MAX",
                tags=sc.tags or [],
                action_counts=action_counts,
                actions_config=sc.actions_config or {},
                total_hands=total
            )
        )
    return result


@router.get("/{scenario_id}", response_model=ScenarioDetail)
def get_scenario_detail(
    scenario_id: str,
    stack: Optional[str] = Query(
        None, description="Corte by_stack a pintar, ej. '6.5'. Por defecto el del medio."
    ),
    db: Session = Depends(get_db)
):
    scenario = db.execute(
        select(Scenario).where(Scenario.id == scenario_id)
    ).scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")

    hands_dict = {}
    by_stack_keys: List[str] = []
    hands_stack: Optional[str] = None

    if scenario.by_stack:
        by_stack_keys = sorted(scenario.by_stack.keys(), key=float)
        wanted = stack if stack in (scenario.by_stack or {}) else default_by_stack_key(scenario)
        hands_stack = wanted
        by_table = resolve_by_stack_table(scenario, float(wanted) if wanted else 0.0)
        for hand, info in by_table.items():
            hands_dict[hand] = HandDetail(
                hand=hand,
                action=info["action"],
                followup=None,
                frequency=100.0,
                marginal=bool(info["marginal"]),
            )
    else:
        for h in scenario.hands:
            hands_dict[h.hand] = HandDetail(
                hand=h.hand,
                action=h.action,
                followup=h.followup_action,
                frequency=h.frequency
            )

    return ScenarioDetail(
        id=scenario.id,
        name=scenario.name,
        position=scenario.position,
        stack_range=scenario.stack_range,
        spot=scenario.spot,
        game=scenario.game or "SPIN_3MAX",
        tags=scenario.tags or [],
        actions_config=scenario.actions_config or {},
        followups_config=scenario.followups_config or {},
        reference_stats=scenario.reference_stats,
        hands=hands_dict,
        by_stack_keys=by_stack_keys,
        hands_stack=hands_stack,
    )


@router.post("/sync")
def sync_scenarios_endpoint(db: Session = Depends(get_db)):
    """Re-sincroniza manualmente los archivos JSON de /data/scenarios hacia la base de datos."""
    summary = sync_all_scenarios(db)
    return {"status": "ok", "summary": summary}
