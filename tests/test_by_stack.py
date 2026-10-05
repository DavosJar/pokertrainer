"""
Tests de los escenarios by_stack (respuesta por stack, sin filas en scenario_hands).

La respuesta correcta sale de by_stack[floor(stack*2)/2]: si la mano esta en
la lista activa (shove/call) se juega, si no se foldea. La lista 'marginal'
no se penaliza. Se usan escenarios sinteticos: no dependen de los JSON.
"""

from types import SimpleNamespace

from app.models.scenario import Scenario
from app.services.table_state import stack_key_for
from app.services.training_service import (
    build_full_matrix_dict,
    default_by_stack_key,
    resolve_by_stack_action,
    resolve_by_stack_table,
)

TEST_GRID = {
    "2": {"shove": ["AA", "KK"], "marginal": ["72o"]},
    "2.5": {"shove": ["AA", "KK"], "marginal": ["72o"]},
    "3": {"shove": ["AA"], "marginal": []},
}

TEST_ACTIONS = {
    "OPEN_SHOVE": {"label": "Open Shove", "color": "#8B0A24", "hotkey": "S"},
    "FOLD": {"label": "Fold", "color": "#EDEDED", "hotkey": "F"},
}


def _stub(by_stack=None):
    """Lo unico que leen los resolvers del escenario es .by_stack."""
    return SimpleNamespace(by_stack=by_stack if by_stack is not None else dict(TEST_GRID))


def _insert_test_scenario(db):
    sc = Scenario(
        id="zz_test_pushfold",
        name="ZZ Test Pushfold",
        position="SB",
        stack_range="<9",
        spot="RFI",
        game="SPIN_3MAX_HU",
        tags=["SB", "HU"],
        actions_config=dict(TEST_ACTIONS),
        followups_config={},
        stack_min=2.0,
        stack_max=3.0,
        stack_step=0.5,
        by_stack={k: {"shove": list(v["shove"]), "marginal": list(v["marginal"])}
                  for k, v in TEST_GRID.items()},
    )
    db.add(sc)
    db.commit()
    return sc


# --- Clave de stack ---
def test_stack_key_is_floor_half_bb_as_text():
    assert stack_key_for(6.5) == "6.5"
    assert stack_key_for(6.0) == "6"
    assert stack_key_for(9) == "9"
    assert stack_key_for(2) == "2"
    assert stack_key_for(2.5) == "2.5"


# --- Resolucion push/fold ---
def test_active_list_means_play_rest_means_fold():
    sc = _stub()

    assert resolve_by_stack_action(sc, "AA", 2.5) == ("OPEN_SHOVE", False)
    assert resolve_by_stack_action(sc, "KK", 2.5) == ("OPEN_SHOVE", False)
    assert resolve_by_stack_action(sc, "AKs", 2.5) == ("FOLD", False)


def test_marginal_means_no_penalty_not_a_different_action():
    sc = _stub()

    assert resolve_by_stack_action(sc, "72o", 2.5) == ("FOLD", True)
    # En otro corte sin marginales, la misma mano foldea y si penaliza.
    assert resolve_by_stack_action(sc, "72o", 3.0) == ("FOLD", False)


def test_table_covers_all_169_with_counts_matching_the_lists():
    sc = _stub()
    table = resolve_by_stack_table(sc, 2.5)

    assert len(table) == 169
    assert sum(1 for v in table.values() if v["action"] == "OPEN_SHOVE") == 2
    assert sum(1 for v in table.values() if v["marginal"]) == 1


def test_call_list_resolves_to_call():
    sc = _stub({"2.5": {"call": ["AA"], "marginal": []}})

    assert resolve_by_stack_action(sc, "AA", 2.5) == ("CALL", False)
    assert resolve_by_stack_action(sc, "KK", 2.5) == ("FOLD", False)


def test_stack_outside_the_grid_falls_back_without_crashing():
    sc = _stub()

    action, _ = resolve_by_stack_action(sc, "AA", 25.0)
    assert action == "OPEN_SHOVE"


def test_default_cut_is_the_middle_of_the_grid():
    assert default_by_stack_key(_stub()) == "2.5"
    assert default_by_stack_key(_stub({})) is None


# --- Matriz pintada con los colores del escenario ---
def test_matrix_uses_scenario_colors(db):
    sc = _insert_test_scenario(db)
    matrix = build_full_matrix_dict(sc, 2.5)

    assert len(matrix) == 169
    assert matrix["AA"]["action"] == "OPEN_SHOVE"
    assert matrix["AA"]["color"] == "#8B0A24"
    assert matrix["AKs"]["action"] == "FOLD"
    assert matrix["AKs"]["color"] == "#EDEDED"
    assert matrix["72o"]["marginal"] is True
    assert matrix["AA"]["stack"] == "2.5"


# --- API de punta a punta ---
def _start_session(client, scenario_id: str) -> str:
    res = client.post("/api/training/session", json={
        "scenario_ids": [scenario_id],
        "mode": "normal",
        "time_limit_seconds": 600,
        "hand_limit": 40,
    })
    assert res.status_code == 200, res.text
    return res.json()["session_id"]


def _answer(client, session_id: str, scenario_id: str, hand: str,
            chosen: str, stack: float):
    return client.post("/api/training/answer", json={
        "session_id": session_id,
        "scenario_id": scenario_id,
        "hand": hand,
        "level": 1,
        "chosen_action": chosen,
        "response_ms": 800,
        "effective_stack": stack,
    })


def test_next_hand_and_answer_without_hand_rows(client, db):
    _insert_test_scenario(db)
    sid = _start_session(client, "zz_test_pushfold")

    nxt = client.get("/api/training/next-hand", params={"session_id": sid})
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["heads_up"] is True
    assert [a["id"] for a in body["available_actions"]] == ["OPEN_SHOVE", "FOLD"]

    # AA a 2.5 empuja: foldear es incorrecto, empujar es correcto.
    wrong = _answer(client, sid, "zz_test_pushfold", "AA", "FOLD", 2.5)
    assert wrong.status_code == 200, wrong.text
    assert wrong.json()["is_correct"] is False
    assert len(wrong.json()["full_matrix"]) == 169

    right = _answer(client, sid, "zz_test_pushfold", "AA", "OPEN_SHOVE", 2.5)
    assert right.status_code == 200, right.text
    assert right.json()["is_correct"] is True
    assert right.json()["needs_level_2"] is False


def test_marginal_hand_is_not_penalized(client, db):
    _insert_test_scenario(db)
    sid = _start_session(client, "zz_test_pushfold")

    # 72o a 2.5 es marginal: vale Shove y vale Fold.
    for chosen in ("OPEN_SHOVE", "FOLD"):
        res = _answer(client, sid, "zz_test_pushfold", "72o", chosen, 2.5)
        assert res.status_code == 200, res.text
        assert res.json()["is_correct"] is True, chosen
        assert "Marginal" in res.json()["explanation"]


def test_scenario_detail_paints_a_cut_and_accepts_stack_param(client, db):
    _insert_test_scenario(db)

    default = client.get("/api/scenarios/zz_test_pushfold")
    assert default.status_code == 200
    body = default.json()
    assert len(body["hands"]) == 169
    assert body["by_stack_keys"] == ["2", "2.5", "3"]
    assert body["hands_stack"] == "2.5"
    assert body["hands"]["AA"]["action"] == "OPEN_SHOVE"

    cut = client.get("/api/scenarios/zz_test_pushfold", params={"stack": "3"})
    assert cut.status_code == 200
    body2 = cut.json()
    assert body2["hands_stack"] == "3"
    assert body2["hands"]["KK"]["action"] == "FOLD"


def test_scenario_list_counts_by_stack_actions(client, db):
    _insert_test_scenario(db)

    res = client.get("/api/scenarios")
    assert res.status_code == 200
    item = {s["id"]: s for s in res.json()}["zz_test_pushfold"]
    assert item["total_hands"] == 169
    assert item["action_counts"] == {"OPEN_SHOVE": 2, "FOLD": 167}
