# Spin & Go Preflop Range Trainer

Entrenador local para memorizar decisiones preflop en Spin & Go 3-max (BTN, SB, BB). El enfoque es entrenar rapidez y precisión antes que teoría avanzada.

## Secuencia de una mano

La mesa sigue un guion fijo. Nada ocurre antes de su paso.

| Paso | Qué pasa |
| --- | --- |
| 0 - Reparto | Fichas SB 0.5 y BB 1, hero sin ficha, pot 1.5. El cronómetro arranca aquí. Botones: Open Shove, OR 2 BB, Fold. |
| 1 - Hero elige | Al hacer clic se detiene el cronómetro y se evalúa contra la acción del JSON. Si el OR es correcto, la mano sigue. |
| 2 - Respuesta del rival | Solo si el OR fue correcto. El rival se sortea (SB o BB, 3bet o 3bet all-in), sube su ficha y el otro tira la mano: su ciega pasa a dinero muerto. Los botones cambian a Fold, Call y All-in, y el cronómetro se reinicia. |
| 3 - Hero responde | Se evalúa contra `vs_3bet` o `vs_3bet_ai` según el tipo de 3bet que ocurrió. |
| 4 - Feedback | Correcto o incorrecto con la acción correcta. La mesa se queda tal cual. Botón único Siguiente, atajo Espacio. |

Cada decisión se guarda en SQLite una sola vez con su propio tiempo: el nivel 1 en el paso 1 y el nivel 2 en el paso 3.

### Reglas de cálculo

- `Pot = fichas en mesa + dinero muerto`. Nunca se escribe a mano.
- `Stack mostrado = stack efectivo - ficha de ese jugador`.
- Ciegas, min raise (2) y 3bet (4) salen de `CONFIG` en `app/services/table_state.py`.
- El stack efectivo se sortea en pasos de 0.5 BB dentro del `stack_range` del escenario (`15-9` sortea entre 9 y 15, `15+` entre 15 y 25).

El backend es la única fuente de verdad de los montos: el frontend dibuja el estado de mesa que devuelve la API y no calcula ni pot, ni stacks, ni fichas.

Ejemplo con stack efectivo 12.5 BB:

```text
PASO 0  SB 0.5 · BB 1 · hero —                          pot 1.5
PASO 1  hero OR 2, stack 10.5                            pot 3.5
PASO 2  SB 3bet 4, stack 8.5 · BB tira, dead 1           pot 7
PASO 3  Fold -> dead 3                                   pot 7
        Call -> hero 4, stack 8.5                        pot 9
        All-in -> hero 12.5, stack 0                     pot 17.5
```

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- SQLite
- Jinja2
- React + Vite
- pytest

## Requisitos

Python 3.11 o superior y pip.

## Instalación

1. Clona el proyecto y entra a la carpeta:
   ```bash
   cd trainer
   ```
2. Crea un entorno virtual:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Arranque

Desde la raíz del proyecto:

```bash
python run.py
```

O bien:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

La app queda disponible en:

- http://127.0.0.1:8000

## Validación de escenarios

La validación de todos los JSON de escenarios está disponible con:

```bash
python -m app.tools.validate_scenarios
```

Este comando comprueba que cada archivo tenga 169 manos válidas y que las acciones/followups estén declarados correctamente.

Cada followup declara su respuesta contra los dos tipos de 3bet que pueden ocurrir:

```json
"4BET_AI": { "vs_3bet": "ALL_IN", "vs_3bet_ai": "CALL" }
```

- `vs_3bet`: qué responder cuando el rival hace un 3bet normal (hay botón All-in).
- `vs_3bet_ai`: qué responder cuando el rival hace 3bet all-in (solo Fold y Call).

Si el followup no declara la variante, el trainer usa el propio id del followup como respuesta.

## Agregar un escenario nuevo

1. Crea un archivo JSON en `data/scenarios/`.
2. Usa el esquema de ejemplo con:
   - `id`
   - `name`
   - `position`
   - `stack_range`
   - `spot`
   - `actions`
   - `followups`
   - `hands`
3. Lanza la validación:
   ```bash
   python -m app.tools.validate_scenarios
   ```
4. Al arrancar la app, el importador sincroniza automáticamente el JSON a SQLite.

## Ejemplo mínimo de JSON

```json
{
  "id": "btn_15-9_spin3",
  "name": "BTN 15-9",
  "position": "BTN",
  "stack_range": "15-9",
  "spot": "RFI",
  "game": "SPIN_3MAX",
  "tags": ["exploit", "3 jugadores"],
  "actions": {
    "OPEN_SHOVE": {"label": "Open Shove", "color": "#FF6B6B", "hotkey": "S"},
    "OR": {"label": "OR", "color": "#4ECDC4", "hotkey": "R", "has_followup": true},
    "FOLD": {"label": "Fold", "color": "#B0BEC5", "hotkey": "F"}
  },
  "followups": {
    "4BET_AI": {"label": "4Bet AI", "color": "#FFD166", "vs_3bet": "ALL_IN", "vs_3bet_ai": "CALL"},
    "FOLD_FOLD": {"label": "Fold → Fold", "color": "#9AA0A6", "vs_3bet": "FOLD", "vs_3bet_ai": "FOLD"}
  },
  "hands": {
    "AA": {"action": "OR", "followup": "4BET_AI", "frequency": 100},
    "AKs": {"action": "OPEN_SHOVE", "frequency": 100},
    "72o": {"action": "FOLD", "frequency": 100}
  }
}
```

## Tests

Ejecuta:

```bash
pytest -q
```

Si prefieres asegurar el contexto del proyecto:

```bash
python -m pytest -q
```

## Estructura principal

```text
app/
  database.py
  main.py
  models/
  routers/
  schemas/
  services/
    table_state.py      # CONFIG + maqueta de la mano: pot, stacks, fichas, rival
    training_service.py
    stats_service.py
    importer.py
  tools/
  templates/

data/
  scenarios/
frontend/
  src/

tests/
```

## Notas

- Los escenarios se cargan automáticamente a SQLite desde `data/scenarios` al iniciar la app.
- `app/services/table_state.py` es la única fuente de verdad de los montos de la mesa: pot, stacks y fichas se derivan de la secuencia de la mano, nunca se escriben a mano ni se calculan en el navegador.
- El esquema está preparado para soportar acciones configurables, followups y frecuencias futuras.
- El proyecto está pensado para un flujo de entrenamiento rápido, por mano, con feedback inmediato y métricas de sesión.
