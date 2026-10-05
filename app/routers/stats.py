from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.stats import (
    StatsOverview,
    AccuracyPoint,
    CategoryAccuracy,
    HandHeatmapCell,
    TopFailedHand
)
from app.services.stats_service import (
    get_stats_overview,
    get_accuracy_over_time,
    get_accuracy_by_category,
    get_scenario_heatmap,
    get_top_failed_hands,
    get_strengths_and_weaknesses
)

router = APIRouter(prefix="/api/stats", tags=["Statistics"])


def parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


@router.get("/overview", response_model=StatsOverview)
def stats_overview(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dt_from = parse_iso_date(from_date)
    dt_to = parse_iso_date(to_date)
    return get_stats_overview(db, from_date=dt_from, to_date=dt_to)


@router.get("/over-time", response_model=List[AccuracyPoint])
def stats_over_time(
    group_by: str = Query("day", pattern="^(day|week)$"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dt_from = parse_iso_date(from_date)
    dt_to = parse_iso_date(to_date)
    return get_accuracy_over_time(db, group_by=group_by, from_date=dt_from, to_date=dt_to)


@router.get("/by-position", response_model=List[CategoryAccuracy])
def stats_by_position(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dt_from = parse_iso_date(from_date)
    dt_to = parse_iso_date(to_date)
    return get_accuracy_by_category(db, category="position", from_date=dt_from, to_date=dt_to)


@router.get("/by-stack-range", response_model=List[CategoryAccuracy])
def stats_by_stack_range(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dt_from = parse_iso_date(from_date)
    dt_to = parse_iso_date(to_date)
    return get_accuracy_by_category(db, category="stack_range", from_date=dt_from, to_date=dt_to)


@router.get("/by-scenario", response_model=List[CategoryAccuracy])
def stats_by_scenario(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dt_from = parse_iso_date(from_date)
    dt_to = parse_iso_date(to_date)
    return get_accuracy_by_category(db, category="scenario", from_date=dt_from, to_date=dt_to)


@router.get("/heatmap/{scenario_id}", response_model=List[HandHeatmapCell])
def stats_heatmap(scenario_id: str, db: Session = Depends(get_db)):
    try:
        return get_scenario_heatmap(db, scenario_id=scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/top-mistakes", response_model=List[TopFailedHand])
def stats_top_mistakes(
    limit: int = Query(20, ge=1, le=100),
    scenario_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return get_top_failed_hands(db, limit=limit, scenario_id=scenario_id)


@router.get("/strengths-weaknesses")
def stats_strengths_weaknesses(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return get_strengths_and_weaknesses(db)
