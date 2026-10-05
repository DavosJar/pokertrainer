from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.session import TrainingSession
from app.schemas.training import (
    SessionStartRequest,
    SessionStartResponse,
    SessionStatusResponse,
    NextHandResponse,
    AnswerSubmitRequest,
    AnswerSubmitResponse
)
from app.services.training_service import (
    start_training_session,
    get_next_training_hand,
    submit_training_answer,
    get_session_summary,
)

router = APIRouter(prefix="/api/training", tags=["Training"])


@router.post("/session", response_model=SessionStartResponse)
def create_session(req: SessionStartRequest, db: Session = Depends(get_db)):
    try:
        session_obj = start_training_session(db, req)
        return SessionStartResponse(
            session_id=session_obj.id,
            mode=session_obj.mode,
            started_at=session_obj.started_at.isoformat(),
            scenario_ids=req.scenario_ids,
            total_scenarios=len(req.scenario_ids),
            time_limit_seconds=req.time_limit_seconds,
            hand_limit=req.hand_limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
def get_session_status(session_id: str, db: Session = Depends(get_db)):
    try:
        summary = get_session_summary(db, session_id)
        return SessionStatusResponse(
            session_id=summary["session_id"],
            mode=summary["mode"],
            started_at=summary["started_at"],
            ended_at=summary["ended_at"],
            scenario_ids=summary["scenario_ids"],
            total_hands=summary["total_hands"],
            correct_hands=summary["correct_hands"],
            accuracy_pct=summary["accuracy_pct"],
            median_response_ms=summary["median_response_ms"],
            correct_fast_pct=summary["correct_fast_pct"],
            time_limit_seconds=summary["time_limit_seconds"],
            hand_limit=summary["hand_limit"],
            remaining_time_seconds=summary["remaining_time_seconds"],
            has_reached_time_limit=summary["has_reached_time_limit"],
            has_reached_hand_limit=summary["has_reached_hand_limit"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/next-hand", response_model=NextHandResponse)
def next_hand(
    session_id: str = Query(...),
    scenario_id: Optional[str] = Query(None),
    hand: Optional[str] = Query(None),
    level: int = Query(1, ge=1, le=2),
    parent_action: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        return get_next_training_hand(
            db=db,
            session_id=session_id,
            scenario_id=scenario_id,
            hand=hand,
            level=level,
            parent_action=parent_action
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/answer", response_model=AnswerSubmitResponse)
def submit_answer(req: AnswerSubmitRequest, db: Session = Depends(get_db)):
    try:
        return submit_training_answer(db, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/session/{session_id}/finish")
def finish_session(session_id: str, db: Session = Depends(get_db)):
    session_obj = db.execute(
        select(TrainingSession).where(TrainingSession.id == session_id)
    ).scalar_one_or_none()

    if not session_obj:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    session_obj.ended_at = datetime.now(timezone.utc)
    db.commit()
    summary = get_session_summary(db, session_id)
    return {
        "status": "finished",
        "session_id": session_id,
        "total_hands": summary["total_hands"],
        "correct_hands": summary["correct_hands"],
        "accuracy_pct": summary["accuracy_pct"],
        "median_response_ms": summary["median_response_ms"],
        "correct_fast_pct": summary["correct_fast_pct"],
        "time_limit_seconds": summary["time_limit_seconds"],
        "hand_limit": summary["hand_limit"],
    }
