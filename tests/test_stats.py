from datetime import datetime, timezone

from app.schemas.training import SessionStartRequest, AnswerSubmitRequest
from app.services.training_service import (
    start_training_session,
    submit_training_answer,
    build_hand_sampling_weight,
    get_session_summary,
    get_next_training_hand,
)
from app.services.stats_service import (
    get_stats_overview,
    get_accuracy_by_category,
    get_scenario_heatmap,
    get_top_failed_hands,
    get_strengths_and_weaknesses
)


def test_statistics_calculations(db):
    req = SessionStartRequest(scenario_ids=["btn_15-9_spin3"], mode="normal")
    session = start_training_session(db, req)

    # Añadir 3 respuestas correctas y 2 incorrectas
    hands_test = [
        ("AA", 1, "OR", 500),         # Correcto
        ("AKs", 1, "OPEN_SHOVE", 600), # Correcto
        ("72o", 1, "FOLD", 450),       # Correcto
        ("22", 1, "FOLD", 700),        # Incorrecto (22 es OPEN_SHOVE en 15-9)
        ("K5o", 1, "OPEN_SHOVE", 900)  # Incorrecto (K5o es FOLD en 15-9)
    ]

    for hand, level, choice, ms in hands_test:
        ans = AnswerSubmitRequest(
            session_id=session.id,
            scenario_id="btn_15-9_spin3",
            hand=hand,
            level=level,
            chosen_action=choice,
            response_ms=ms
        )
        submit_training_answer(db, ans)

    # 1. Overview
    overview = get_stats_overview(db)
    assert overview.total_answers == 5
    assert overview.total_correct == 3
    assert overview.global_accuracy_pct == 60.0
    assert overview.avg_response_ms > 0
    assert overview.median_response_ms == 600
    assert overview.correct_fast_pct == 100.0

    # 2. Categorías
    pos_stats = get_accuracy_by_category(db, "position")
    assert len(pos_stats) >= 1
    assert pos_stats[0].category == "BTN"
    assert pos_stats[0].total_hands == 5
    assert pos_stats[0].accuracy_pct == 60.0

    # 3. Heatmap
    heatmap = get_scenario_heatmap(db, "btn_15-9_spin3")
    assert len(heatmap) == 169
    cell_map = {c.hand: c for c in heatmap}
    assert cell_map["AA"].total_attempts == 1
    assert cell_map["AA"].accuracy_pct == 100.0
    assert cell_map["22"].total_attempts == 1
    assert cell_map["22"].accuracy_pct == 0.0
    assert cell_map["32o"].total_attempts == 0
    assert cell_map["32o"].accuracy_pct is None

    # 4. Top failed hands
    failed = get_top_failed_hands(db)
    assert len(failed) == 2
    failed_hands = [f.hand for f in failed]
    assert "22" in failed_hands
    assert "K5o" in failed_hands

    # 5. Fortalezas y debilidades
    sw = get_strengths_and_weaknesses(db)
    assert "positions" in sw
    assert "scenarios" in sw


def test_session_summary_and_limits(db):
    req = SessionStartRequest(
        scenario_ids=["btn_15-9_spin3"],
        mode="normal",
        time_limit_seconds=180,
        hand_limit=2,
    )
    session = start_training_session(db, req)
    assert session.filter_config["time_limit_seconds"] == 180
    assert session.filter_config["hand_limit"] == 2

    for hand, choice, ms in [
        ("AA", "OR", 500),
        ("22", "FOLD", 900),
    ]:
        submit_training_answer(
            db,
            AnswerSubmitRequest(
                session_id=session.id,
                scenario_id="btn_15-9_spin3",
                hand=hand,
                level=1,
                chosen_action=choice,
                response_ms=ms,
            ),
        )

    summary = get_session_summary(db, session.id)
    assert summary["total_hands"] == 2
    assert summary["correct_hands"] == 1
    assert summary["accuracy_pct"] == 50.0
    assert summary["time_limit_seconds"] == 180
    assert summary["hand_limit"] == 2


def test_finished_session_is_frozen_and_blocks_new_hands(db):
    req = SessionStartRequest(
        scenario_ids=["btn_15-9_spin3"],
        mode="normal",
        time_limit_seconds=180,
    )
    session = start_training_session(db, req)
    session.ended_at = datetime.now(timezone.utc)
    db.commit()

    summary = get_session_summary(db, session.id)
    assert summary["ended_at"] is not None
    assert summary["remaining_time_seconds"] == 0
    assert summary["has_reached_time_limit"] is True

    try:
        get_next_training_hand(db, session.id)
        assert False, "La sesión ya estaba finalizada y no debería permitir más manos"
    except ValueError as exc:
        assert "finalizada" in str(exc).lower()


def test_sampling_weight_prefers_action_borderline_and_unpracticed():
    assert build_hand_sampling_weight(
        hand_action="OPEN_SHOVE",
        is_borderline=True,
        total_attempts=0,
    ) == 12

    assert build_hand_sampling_weight(
        hand_action="FOLD",
        is_borderline=False,
        total_attempts=0,
    ) == 2

    assert build_hand_sampling_weight(
        hand_action="OR",
        is_borderline=False,
        total_attempts=2,
    ) == 3


def test_strengths_weaknesses_exposes_insufficient_data_flag(db):
    sw = get_strengths_and_weaknesses(db)

    for group in (sw["positions"], sw["stack_ranges"], sw["scenarios"]):
        assert "insufficient_data" in group
        assert isinstance(group["insufficient_data"], bool)
