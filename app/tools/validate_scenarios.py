import os
import sys
import json
from typing import Dict, Any, List, Tuple
from app.tools.poker_utils import ALL_169_HANDS, ALL_169_HANDS_SET
from app.services.table_state import ACTION_STYLES, BY_STACK_LIST_KEYS, FOLLOWUP_VARIANT_KEYS, fmt_bb

DATA_SCENARIOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "scenarios"
)


def expected_stack_keys(data: Dict[str, Any]) -> List[str]:
    """Rejilla de stacks que declara el escenario: stack_min..stack_max en pasos de stack_step."""
    try:
        low = float(data["stack_min"])
        high = float(data["stack_max"])
        step = float(data.get("stack_step", 0.5))
    except (KeyError, TypeError, ValueError):
        return []

    keys = []
    value = low
    while value <= high + 1e-9:
        keys.append(fmt_bb(value))
        value += step
    return keys


def _validate_by_stack(
    data: Dict[str, Any],
    actions_catalog: Dict[str, Any],
    errors: List[str],
    summary: Dict[str, Any],
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Escenario por stack: en vez de 'hands' trae 'by_stack', una tabla
    { "7.5": {"shove": [...], "marginal": [...]}, ... }.

    La clave de la lista dice que hacer con esa mano a ese stack, y 'marginal'
    marca las manos que no se penalizan. El resto de manos toma la accion
    complementaria (lo que no sea shove ni call es fold).
    """
    by_stack = data.get("by_stack")
    if not isinstance(by_stack, dict) or not by_stack:
        errors.append("'by_stack' debe ser un diccionario con al menos una entrada de stack.")
        return False, errors, summary

    for field in ("stack_min", "stack_max", "stack_step"):
        if field not in data:
            errors.append(f"Falta el campo obligatorio de by_stack: '{field}'")

    # La clave se arma con floor(stack*2)/2 -> "7.5", "2", "9".
    expected = expected_stack_keys(data)
    actual = list(by_stack.keys())
    if expected:
        faltantes = sorted(set(expected) - set(actual))
        sobrantes = sorted(set(actual) - set(expected))
        if faltantes:
            errors.append(f"Faltan stacks en 'by_stack': {faltantes[:6]}")
        if sobrantes:
            errors.append(f"Stacks no esperados en 'by_stack': {sobrantes[:6]}")

    # Las listas deben usar nombres de mano válidos y claves conocidas.
    known_keys = set(BY_STACK_LIST_KEYS) | {"marginal"}
    unknown_hands = set()
    per_stack = {}

    for stack_key, entry in by_stack.items():
        if not isinstance(entry, dict) or not entry:
            errors.append(f"by_stack['{stack_key}'] debe ser un objeto con listas de manos.")
            continue

        for list_key, hands_list in entry.items():
            if list_key not in known_keys:
                errors.append(
                    f"by_stack['{stack_key}'] usa la lista desconocida '{list_key}'. "
                    f" permitidas: {sorted(known_keys)}"
                )
                continue
            if not isinstance(hands_list, list):
                errors.append(f"by_stack['{stack_key}']['{list_key}'] debe ser una lista de manos.")
                continue

            unknown_hands |= set(hands_list) - ALL_169_HANDS_SET
            per_stack.setdefault(list_key, []).append(len(hands_list))

        # Cada stack debe decidir al menos una mano activa ademas de las marginales.
        active = [k for k in entry if k in BY_STACK_LIST_KEYS]
        if not active:
            errors.append(f"by_stack['{stack_key}'] no declara ninguna lista de acción activa.")

    if unknown_hands:
        errors.append(f"Manos no reconocidas en 'by_stack': {sorted(unknown_hands)[:6]}")

    summary = {
        "id": data.get("id"),
        "name": data.get("name"),
        "position": str(data.get("position", "")).upper(),
        "stack_range": data.get("stack_range"),
        "total_hands": 169,
        "lookup": "by_stack",
        "stacks": len(by_stack),
        "action_counts": {
            k: {"min": min(v), "max": max(v)} for k, v in per_stack.items()
        },
    }
    return (len(errors) == 0), errors, summary


def validate_scenario_file(filepath: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors = []
    summary = {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Error al leer JSON: {str(e)}"], {}

    # 1. Campos obligatorios de nivel superior
    required_fields = ["id", "name", "position", "stack_range", "spot", "actions"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Falta el campo obligatorio: '{field}'")

    # Un escenario define el rango de manos de dos formas excluyentes: 'hands'
    # (respuesta fija) o 'by_stack' (la respuesta depende del stack). Se exige una.
    has_by_stack = "by_stack" in data
    if "hands" not in data and not has_by_stack:
        errors.append("Falta el campo obligatorio: 'hands' o 'by_stack'")

    if errors:
        return False, errors, summary

    scenario_id = data.get("id")
    name = data.get("name")
    position = str(data.get("position", "")).upper()
    valid_positions = {"BTN", "SB", "BB"}
    if position not in valid_positions:
        errors.append(f"Posición '{position}' no válida. Debe ser una de: {valid_positions}")

    # 2. Catálogo de acciones
    actions_catalog = data.get("actions", {})
    if not isinstance(actions_catalog, dict) or not actions_catalog:
        errors.append("El catálogo 'actions' debe ser un diccionario con al menos una acción.")

    followups_catalog = data.get("followups") or {}
    if data.get("followups") is not None and not isinstance(followups_catalog, dict):
        errors.append("El catálogo 'followups' debe ser un diccionario o null.")

    # 2-bis. Escenarios por stack: no tienen 'hands', la respuesta sale de una tabla.
    if has_by_stack:
        return _validate_by_stack(data, actions_catalog, errors, summary)

    # 3. Validación de las 169 manos
    hands_dict = data.get("hands", {})
    if not isinstance(hands_dict, dict):
        errors.append("'hands' debe ser un diccionario de 169 manos.")
        return False, errors, summary

    missing_hands = ALL_169_HANDS_SET - set(hands_dict.keys())
    extra_hands = set(hands_dict.keys()) - ALL_169_HANDS_SET

    if missing_hands:
        sample_missing = list(missing_hands)[:5]
        errors.append(
            f"Faltan {len(missing_hands)} manos de las 169 requeridas. Ejemplos faltantes: {sample_missing}"
        )

    if extra_hands:
        sample_extra = list(extra_hands)[:5]
        errors.append(
            f"Hay {len(extra_hands)} manos no reconocidas en el diccionario. Ejemplos: {sample_extra}"
        )

    # 4. Validar cada mano
    action_counts = {}
    followup_counts = {}

    for hand_name, hand_info in hands_dict.items():
        if not isinstance(hand_info, dict):
            errors.append(f"La mano '{hand_name}' debe ser un objeto/dict.")
            continue

        action = hand_info.get("action")
        if not action or action not in actions_catalog:
            errors.append(
                f"Mano '{hand_name}' tiene acción desconocida '{action}'. Acciones válidas: {list(actions_catalog.keys())}"
            )
        else:
            action_counts[action] = action_counts.get(action, 0) + 1

        followup = hand_info.get("followup")
        if followup:
            if isinstance(followup, dict):
                # Followup inline por mano (ej. {"vs_4bet_ai": "CALL"}): las
                # variantes deben ser conocidas y apuntar a una accion valida.
                bad_keys = [k for k in followup.keys() if k not in FOLLOWUP_VARIANT_KEYS]
                if bad_keys:
                    errors.append(
                        f"Mano '{hand_name}' usa variantes desconocidas: {bad_keys}."
                    )
                bad_values = [
                    v for v in followup.values()
                    if not isinstance(v, str) or not v.strip()
                ]
                if bad_values:
                    errors.append(
                        f"Mano '{hand_name}' tiene respuesta inline inválida: {bad_values}."
                    )
            elif not followups_catalog or followup not in followups_catalog:
                errors.append(
                    f"Mano '{hand_name}' tiene followup desconocido '{followup}'."
                )
            else:
                followup_counts[followup] = followup_counts.get(followup, 0) + 1

        freq = hand_info.get("frequency", 100)
        if not isinstance(freq, (int, float)) or freq < 0 or freq > 100:
            errors.append(f"Mano '{hand_name}' tiene frecuencia inválida: {freq}")

    summary = {
        "id": scenario_id,
        "name": name,
        "position": position,
        "total_hands": len(hands_dict),
        "action_counts": action_counts,
        "followup_counts": followup_counts
    }

    return (len(errors) == 0), errors, summary


def main():
    print("=" * 60)
    print("  VALIDADOR DE ESCENARIOS PREFLOP (SPIN & GO 3-MAX)")
    print("=" * 60)

    if not os.path.exists(DATA_SCENARIOS_DIR):
        print(f"[ERROR] Directorio no encontrado: {DATA_SCENARIOS_DIR}")
        sys.exit(1)

    json_files = [f for f in os.listdir(DATA_SCENARIOS_DIR) if f.endswith(".json")]

    if not json_files:
        print(f"[AVISO] No se encontraron archivos .json en {DATA_SCENARIOS_DIR}")
        sys.exit(1)

    print(f"Buscando escenarios en: {DATA_SCENARIOS_DIR}")
    print(f"Archivos encontrados: {len(json_files)}\n")

    has_failures = False

    for json_file in json_files:
        filepath = os.path.join(DATA_SCENARIOS_DIR, json_file)
        is_valid, errors, summary = validate_scenario_file(filepath)

        if is_valid:
            print(f"[OK] {json_file}")
            print(f"     ID: {summary.get('id')} | Nombre: {summary.get('name')} | Posicion: {summary.get('position')}")

            if summary.get("lookup") == "by_stack":
                print(f"     Rango: {summary.get('stack_range')} | Stacks: {summary.get('stacks')} (lookup por stack)")
                for key, rng in (summary.get("action_counts") or {}).items():
                    print(f"     Listas '{key}': min {rng['min']} / max {rng['max']} manos")
                continue

            print(f"     Manos: {summary.get('total_hands')}/169")
            actions_str = ", ".join(f"{k}: {v}" for k, v in summary.get('action_counts', {}).items())
            print(f"     Acciones: {actions_str}")
            if summary.get('followup_counts'):
                f_str = ", ".join(f"{k}: {v}" for k, v in summary.get('followup_counts', {}).items())
                print(f"     Followups: {f_str}")
        else:
            has_failures = True
            print(f"[ERROR] {json_file}")
            for err in errors[:10]:
                print(f"       - {err}")
            if len(errors) > 10:
                print(f"       ... y {len(errors) - 10} errores mas.")
        print("-" * 60)

    if has_failures:
        print("\n[RESULTADO] Uno o mas archivos tienen errores de validacion.")
        sys.exit(1)
    else:
        print("\n[EXITO] Todos los escenarios son validos.")
        sys.exit(0)


if __name__ == "__main__":
    main()
