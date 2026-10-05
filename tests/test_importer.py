import os
import json
from sqlalchemy import select
from app.models.scenario import Scenario, ScenarioHand
from app.services.importer import sync_all_scenarios
from app.tools.validate_scenarios import validate_scenario_file


def test_validate_real_scenarios():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenarios_dir = os.path.join(base_dir, "data", "scenarios")

    json_files = [f for f in os.listdir(scenarios_dir) if f.endswith(".json")]
    assert len(json_files) >= 2, "Debe haber al menos 2 escenarios (btn_15-9 y btn_15plus)"

    for f in json_files:
        path = os.path.join(scenarios_dir, f)
        is_valid, errors, summary = validate_scenario_file(path)
        assert is_valid, f"Errores en {f}: {errors}"
        assert summary["total_hands"] == 169, f"{f} debe tener 169 manos"


def test_sync_scenarios_into_db(db):
    scenarios = db.execute(select(Scenario)).scalars().all()
    assert len(scenarios) >= 2

    btn_15_9 = db.execute(
        select(Scenario).where(Scenario.id == "btn_15-9_spin3")
    ).scalar_one_or_none()

    assert btn_15_9 is not None
    assert btn_15_9.position == "BTN"
    assert btn_15_9.stack_range == "15-9"
    assert len(btn_15_9.hands) == 169

    # Verificar manos clave
    hands_map = {h.hand: h for h in btn_15_9.hands}
    assert hands_map["AA"].action == "OR"
    assert hands_map["AA"].followup_action == "4BET_AI"
    assert hands_map["AKs"].action == "OPEN_SHOVE"
    assert hands_map["72o"].action == "FOLD"
