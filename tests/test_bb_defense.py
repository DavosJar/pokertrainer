"""
Tests de la defensa de la BB heads-up: VS_LIMP (CHECK/ISO/ISO_AI) y
VS_MIN_RAISE (FOLD/CALL/THREEBET/THREEBET_AI).

El SB ya actuo en el PASO 0 (limp 1 o min-raise 2) y ante un raise no-ai
siempre responde empujando. Los vs_mr traen el followup inline por mano.
"""

from sqlalchemy import select

from app.models.scenario import Scenario


def _start_session(client, scenario_id: str) -> str:
    res = client.post("/api/training/session", json={
        "scenario_ids": [scenario_id],
        "mode": "normal",
        "time_limit_seconds": 600,
        "hand_limit": 40,
    })
    assert res.status_code == 200, res.text
    return res.json()["session_id"]


def _answer(client, sid: str, scenario_id: str, hand: str, chosen: str,
            stack: float, level: int = 1, parent=None, villain=None):
    body = {
        "session_id": sid,
        "scenario_id": scenario_id,
        "hand": hand,
        "level": level,
        "chosen_action": chosen,
        "response_ms": 800,
        "effective_stack": stack,
    }
    if parent:
        body["parent_action"] = parent
    if villain:
        body["villain_actor"] = villain["actor"]
        body["villain_kind"] = villain["kind"]
    return client.post("/api/training/answer", json=body)


def test_vs_limp_opens_with_limp_on_the_table(client):
    sid = _start_session(client, "bb_hu_vs_limp_15-9")

    nxt = client.get("/api/training/next-hand", params={"session_id": sid})
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["heads_up"] is True
    assert [a["id"] for a in body["available_actions"]] == ["CHECK", "ISO_AI", "ISO"]
    assert body["table"]["bets"] == {"sb": 1.0, "bb": None, "hero": 1.0}
    assert body["table"]["pot"] == 2.0


def test_vs_limp_iso_followup_is_always_all_in(client):
    sid = _start_session(client, "bb_hu_vs_limp_15-9")

    # AA aisla y paga el 3bet all-in (followup CALL_AI del catalogo).
    r1 = _answer(client, sid, "bb_hu_vs_limp_15-9", "AA", "ISO", 12.5)
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_correct"] is True
    assert r1.json()["needs_level_2"] is True
    villain = r1.json()["villain"]
    assert villain["actor"] == "SB" and villain["kind"] == "ai"
    assert r1.json()["table"]["bets"]["hero"] == 3.0

    r2 = _answer(client, sid, "bb_hu_vs_limp_15-9", "AA", "CALL", 12.5,
                 level=2, parent="ISO", villain=villain)
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_correct"] is True
    assert "3bet all-in" in r2.json()["explanation"]


def test_vs_min_raise_uses_inline_followup(client, db):
    # El followup inline se guarda serializado (columna String).
    sc = db.execute(
        select(Scenario).where(Scenario.id == "bb_hu_vs_mr_15-9")
    ).scalar_one()
    assert sc.followups_config == {}
    aa = next(h for h in sc.hands if h.hand == "AA")
    assert aa.followup_action == '{"vs_4bet_ai": "CALL"}'

    sid = _start_session(client, "bb_hu_vs_mr_15-9")

    nxt = client.get("/api/training/next-hand", params={"session_id": sid})
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert [a["id"] for a in body["available_actions"]] == [
        "THREEBET_AI", "CALL", "THREEBET", "FOLD",
    ]
    assert body["table"]["bets"] == {"sb": 2.0, "bb": None, "hero": 1.0}
    assert body["table"]["pot"] == 3.0

    # AA 3betea y paga el 4bet all-in (followup inline).
    r1 = _answer(client, sid, "bb_hu_vs_mr_15-9", "AA", "THREEBET", 12.5)
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_correct"] is True
    assert r1.json()["needs_level_2"] is True
    villain = r1.json()["villain"]
    assert villain == {"actor": "SB", "kind": "ai", "label": "SB 4bet all-in"}
    assert r1.json()["table"]["bets"]["hero"] == 6.0

    r2 = _answer(client, sid, "bb_hu_vs_mr_15-9", "AA", "CALL", 12.5,
                 level=2, parent="THREEBET", villain=villain)
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_correct"] is True
    assert "4bet all-in" in r2.json()["explanation"]

    # La matriz muestra la respuesta resuelta, no el dict crudo.
    assert r2.json()["full_matrix"]["AA"]["followup"] == "CALL"


def test_vs_min_raise_call_and_fold_amounts(client):
    sid = _start_session(client, "bb_hu_vs_mr_15-9")

    call = _answer(client, sid, "bb_hu_vs_mr_15-9", "JTs", "CALL", 8.0)
    assert call.status_code == 200, call.text
    assert call.json()["is_correct"] is True
    assert call.json()["table"]["pot"] == 4.0

    fold = _answer(client, sid, "bb_hu_vs_mr_15-9", "72o", "FOLD", 8.0)
    assert fold.status_code == 200, fold.text
    assert fold.json()["table"]["dead"] == 1.0
