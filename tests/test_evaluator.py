import pytest
from app.schemas.training import SessionStartRequest, AnswerSubmitRequest
from app.services.training_service import (
    start_training_session,
    get_next_training_hand,
    submit_training_answer
)
from app.tools.poker_utils import find_borderline_hands, get_169_hands


def test_169_hands_complete():
    hands = get_169_hands()
    assert len(hands) == 169
    assert "AA" in hands
    assert "22" in hands
    assert "AKs" in hands
    assert "AKo" in hands
    assert len(set(hands)) == 169


def test_session_lifecycle_and_evaluation(db):
    # 1. Iniciar sesión
    req = SessionStartRequest(
        scenario_ids=["btn_15-9_spin3"],
        mode="normal"
    )
    session = start_training_session(db, req)
    assert session.id is not None
    assert session.total_hands == 0

    # 2. Obtener siguiente mano (PASO 0 - reparto)
    hand_resp = get_next_training_hand(db, session_id=session.id)
    assert hand_resp.scenario_id == "btn_15-9_spin3"
    assert hand_resp.level == 1
    assert len(hand_resp.cards) == 2
    assert [a.id for a in hand_resp.available_actions] == ["OPEN_SHOVE", "OR", "FOLD"]
    assert [a.label for a in hand_resp.available_actions] == ["Open Shove", "OR 2 BB", "Fold"]

    # El reparto viene limpio: ciegas puestas, hero sin ficha, pot = 1.5
    table = hand_resp.table
    assert table.bets.hero is None
    assert table.bets.sb == 0.5
    assert table.bets.bb == 1
    assert table.pot == 1.5
    assert table.dead == 0
    assert table.stacks.hero == table.effective_stack
    assert table.folded.sb is False and table.folded.bb is False

    # 3. Evaluar respuesta correcta nivel 1 (AA -> OR)
    ans_req = AnswerSubmitRequest(
        session_id=session.id,
        scenario_id="btn_15-9_spin3",
        hand="AA",
        level=1,
        chosen_action="OR",
        response_ms=850,
        effective_stack=table.effective_stack,
    )
    res = submit_training_answer(db, ans_req)
    assert res.is_correct is True
    assert res.needs_level_2 is True
    assert res.correct_action == "OR"
    assert res.current_streak == 1
    assert res.session_accuracy_pct == 100.0

    # PASO 1 - el OR pone la ficha de hero. La tabla que vuelve ya trae el 3bet
    # del PASO 2, porque la respuesta del rival ocurre en el MISMO instante.
    assert res.table.bets.hero == 2

    # PASO 2 - el rival responde al azar y se ofrecen Fold/Call(/All-in)
    assert res.villain is not None
    assert res.villain.actor in ("SB", "BB")
    assert res.villain.kind in ("normal", "ai")
    expected_buttons = ["FOLD", "CALL"] if res.villain.kind == "ai" else ["FOLD", "CALL", "ALL_IN"]
    assert [a.id for a in res.next_actions] == expected_buttons

    # El rival sube a 3bet y el otro tira: su ciega pasa a dead, sin duplicar el monto
    villain_bet = res.table.effective_stack if res.villain.kind == "ai" else 4
    folded_seat = "bb" if res.villain.actor == "SB" else "sb"
    raised_seat = "sb" if res.villain.actor == "SB" else "bb"
    folded_blind = 1 if folded_seat == "bb" else 0.5
    assert getattr(res.table.bets, raised_seat) == villain_bet
    assert getattr(res.table.bets, folded_seat) is None
    assert res.table.dead == folded_blind
    assert res.table.pot == 2 + villain_bet + folded_blind
    assert getattr(res.table.folded, folded_seat) is True

    # 4. Nivel 2: se evalua contra vs_3bet o vs_3bet_ai segun el 3bet que ocurrio
    expected_level_2 = "CALL" if res.villain.kind == "ai" else "ALL_IN"  # AA -> followup 4BET_AI
    ans2_req = AnswerSubmitRequest(
        session_id=session.id,
        scenario_id="btn_15-9_spin3",
        hand="AA",
        level=2,
        chosen_action=expected_level_2,
        response_ms=620,
        effective_stack=table.effective_stack,
        villain_actor=res.villain.actor,
        villain_kind=res.villain.kind,
    )
    res2 = submit_training_answer(db, ans2_req)
    assert res2.is_correct is True
    assert res2.correct_action == expected_level_2
    assert res2.needs_level_2 is False
    assert res2.current_streak == 2

    # PASO 3 - la mesa refleja la respuesta de hero
    # Call iguala al rival; All-in pone el stack efectivo.
    hero_bet = table.effective_stack if expected_level_2 == "ALL_IN" else villain_bet
    assert res2.table.bets.hero == hero_bet
    assert res2.table.stacks.hero == pytest.approx(table.effective_stack - hero_bet)
    assert res2.table.pot == hero_bet + villain_bet + folded_blind
    assert res2.table.dead == folded_blind

    # 5. Respuesta incorrecta (72o -> OPEN_SHOVE cuando debe ser FOLD)
    ans_wrong = AnswerSubmitRequest(
        session_id=session.id,
        scenario_id="btn_15-9_spin3",
        hand="72o",
        level=1,
        chosen_action="OPEN_SHOVE",
        response_ms=1200,
    )
    res_wrong = submit_training_answer(db, ans_wrong)
    assert res_wrong.is_correct is False
    assert res_wrong.correct_action == "FOLD"
    assert res_wrong.current_streak == 0
    assert res_wrong.session_accuracy_pct == pytest.approx(66.7, 0.1)
    assert res_wrong.full_matrix is not None
    assert "72o" in res_wrong.full_matrix
    # OR incorrecto termina la mano: no hay respuesta del rival
    assert res_wrong.needs_level_2 is False
    assert res_wrong.villain is None


def test_level_2_answer_depends_on_villain_kind(db):
    """La misma mano pide CALL ante all-in y ALL_IN ante 3bet normal."""
    req = SessionStartRequest(scenario_ids=["btn_15-9_spin3"], mode="normal")
    session = start_training_session(db, req)

    def answer(chosen: str, kind: str):
        return submit_training_answer(db, AnswerSubmitRequest(
            session_id=session.id,
            scenario_id="btn_15-9_spin3",
            hand="AA",
            level=2,
            chosen_action=chosen,
            response_ms=500,
            effective_stack=12.5,
            villain_actor="SB",
            villain_kind=kind,
        ))

    # AA tiene followup 4BET_AI: vs_3bet = ALL_IN, vs_3bet_ai = CALL
    assert answer("ALL_IN", "normal").is_correct is True
    assert answer("CALL", "ai").is_correct is True
    assert answer("CALL", "normal").correct_action == "ALL_IN"
    assert answer("ALL_IN", "ai").correct_action == "CALL"
    # Fold nunca es la jugada establecida de AA
    assert answer("FOLD", "ai").is_correct is False


def test_level_2_rejects_unknown_villain(db):
    req = SessionStartRequest(scenario_ids=["btn_15-9_spin3"], mode="normal")
    session = start_training_session(db, req)

    with pytest.raises(ValueError):
        submit_training_answer(db, AnswerSubmitRequest(
            session_id=session.id,
            scenario_id="btn_15-9_spin3",
            hand="AA",
            level=2,
            chosen_action="CALL",
            response_ms=500,
            effective_stack=12.5,
            villain_actor="SB",
            villain_kind="rebuy",
        ))


def test_level_2_next_hand_returns_response_buttons(db):
    """El endpoint de nivel 2 ofrece Fold/Call(/All-in), no los followups."""
    req = SessionStartRequest(scenario_ids=["btn_15-9_spin3"], mode="normal")
    session = start_training_session(db, req)

    seen_normal = False
    seen_ai = False

    for _ in range(20):
        resp = get_next_training_hand(
            db, session_id=session.id, scenario_id="btn_15-9_spin3", hand="AA", level=2
        )
        ids = [a.id for a in resp.available_actions]
        assert resp.villain is not None
        if resp.villain.kind == "ai":
            assert ids == ["FOLD", "CALL"]
            seen_ai = True
        else:
            assert ids == ["FOLD", "CALL", "ALL_IN"]
            seen_normal = True

    # Con 20 sorteos deben aparecer ambos tipos de 3bet
    assert seen_normal and seen_ai


def test_borderline_detection(db):
    from app.models.scenario import Scenario
    from sqlalchemy import select

    sc = db.execute(select(Scenario).where(Scenario.id == "btn_15-9_spin3")).scalar_one()
    hands_dict = {h.hand: h for h in sc.hands}
    borderline = find_borderline_hands(hands_dict)

    # Las manos de frontera deben existir entre shove/fold o shove/or
    assert len(borderline) > 10
    assert "AA" in borderline or "K8s" in borderline or "A2s" in borderline
