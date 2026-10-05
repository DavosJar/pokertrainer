import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.scenario import Scenario, ScenarioHand
from app.tools.validate_scenarios import validate_scenario_file

SCENARIOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "scenarios"
)


def sync_all_scenarios(db: Session, scenarios_dir: str = SCENARIOS_DIR) -> Dict[str, Any]:
    """
    Sincroniza todos los archivos JSON de escenarios en SQLite (upsert por ID).
    Permite agregar o modificar archivos JSON sin tocar código y sin reiniciar la DB.
    """
    if not os.path.exists(scenarios_dir):
        os.makedirs(scenarios_dir, exist_ok=True)
        return {"synced": 0, "errors": [f"Directorio creado: {scenarios_dir}"]}

    json_files = [f for f in os.listdir(scenarios_dir) if f.endswith(".json")]
    synced_count = 0
    errors = []

    for file_name in json_files:
        filepath = os.path.join(scenarios_dir, file_name)
        is_valid, validation_errors, _ = validate_scenario_file(filepath)

        if not is_valid:
            errors.append(f"Archivo inválido {file_name}: {'; '.join(validation_errors[:3])}")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            scenario_id = data["id"]
            existing_scenario = db.execute(
                select(Scenario).where(Scenario.id == scenario_id)
            ).scalar_one_or_none()

            now = datetime.now(timezone.utc)

            if existing_scenario:
                # Actualizar metadatos
                existing_scenario.name = data["name"]
                existing_scenario.position = str(data["position"]).upper()
                existing_scenario.stack_range = data["stack_range"]
                existing_scenario.spot = data["spot"]
                existing_scenario.game = data.get("game", "SPIN_3MAX")
                existing_scenario.tags = data.get("tags", [])
                existing_scenario.actions_config = data.get("actions", {})
                existing_scenario.followups_config = data.get("followups") or {}
                existing_scenario.reference_stats = data.get("reference_stats")
                existing_scenario.stack_min = data.get("stack_min")
                existing_scenario.stack_max = data.get("stack_max")
                existing_scenario.stack_step = data.get("stack_step")
                existing_scenario.by_stack = data.get("by_stack")
                existing_scenario.updated_at = now
                scenario_obj = existing_scenario
            else:
                # Insertar nuevo escenario
                scenario_obj = Scenario(
                    id=scenario_id,
                    name=data["name"],
                    position=str(data["position"]).upper(),
                    stack_range=data["stack_range"],
                    spot=data["spot"],
                    game=data.get("game", "SPIN_3MAX"),
                    tags=data.get("tags", []),
                    actions_config=data.get("actions", {}) ,
                    followups_config=data.get("followups") or {},
                    reference_stats=data.get("reference_stats"),
                    stack_min=data.get("stack_min"),
                    stack_max=data.get("stack_max"),
                    stack_step=data.get("stack_step"),
                    by_stack=data.get("by_stack"),
                    created_at=now,
                    updated_at=now
                )
                db.add(scenario_obj)

            db.flush()

            # Sincronizar las 169 manos. Los escenarios 'by_stack' no tienen
            # 'hands': su respuesta se resuelve contra la tabla, no por fila.
            hands_data = data.get("hands") or {}

            if hands_data:
                existing_hands_res = db.execute(
                    select(ScenarioHand).where(ScenarioHand.scenario_id == scenario_id)
                ).scalars().all()
                existing_hands_map = {h.hand: h for h in existing_hands_res}

                for hand_name, hand_info in hands_data.items():
                    action = hand_info.get("action")
                    followup = hand_info.get("followup")
                    # Algunos escenarios traen el followup inline por mano
                    # ({"vs_4bet_ai": "CALL"}) en vez de una clave al catalogo:
                    # se guarda serializado y el servicio lo interpreta.
                    if isinstance(followup, dict):
                        followup = json.dumps(followup, sort_keys=True)
                    freq = float(hand_info.get("frequency", 100.0))

                    if hand_name in existing_hands_map:
                        h_obj = existing_hands_map[hand_name]
                        h_obj.action = action
                        h_obj.followup_action = followup
                        h_obj.frequency = freq
                    else:
                        new_hand = ScenarioHand(
                            scenario_id=scenario_id,
                            hand=hand_name,
                            action=action,
                            followup_action=followup,
                            frequency=freq
                        )
                        db.add(new_hand)
            else:
                # El escenario paso de 'hands' a 'by_stack': sus filas sobran.
                for stale in db.execute(
                    select(ScenarioHand).where(ScenarioHand.scenario_id == scenario_id)
                ).scalars().all():
                    db.delete(stale)

            db.commit()
            synced_count += 1

        except Exception as e:
            db.rollback()
            errors.append(f"Error procesando {file_name}: {str(e)}")

    return {
        "total_files": len(json_files),
        "synced": synced_count,
        "errors": errors
    }
