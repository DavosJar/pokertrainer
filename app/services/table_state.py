"""
Estado de mesa Spin & Go (3-max BTN/SB/BB y heads-up) y la SECUENCIA EXACTA DE UNA MANO.

Este modulo es la UNICA fuente de verdad de los montos de la mesa. El frontend
solo dibuja lo que devuelve aqui: nunca calcula pot, stack ni fichas a mano.

REGLAS DE CALCULO (prompt.md):
- Pot = suma de todas las fichas en mesa + dinero muerto. Nunca se escribe a mano.
- Stack mostrado = stack efectivo menos la ficha de ese jugador.
- Ciegas, min raise (2), 3bet (4), limp (1) y raise heads-up (3) salen de CONFIG.
- Stack sale del stack_range o del stack_min/stack_max del escenario.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

# CONFIG: ciegas, raises y respuestas, todo en BB.
CONFIG: Dict[str, object] = {
    "blinds": {"SB": 0.5, "BB": 1.0},
    "min_raise": 2.0,
    "three_bet": 4.0,
    # El limp heads-up completa la ciega del SB hasta la del BB.
    "limp": 1.0,
    # Raise del BB tras un limp: MONTO TOTAL de su ficha, no lo que sube.
    "hu_raise": 3.0,
    # Defensa de la BB heads-up: ISO sobre el limp (3x) y 3bet sobre el
    # min-raise (3x). Montos totales. Solo dibujan la ficha, no califican:
    # el entrenador decide por rangos fijos, no por equity.
    "iso": 3.0,
    "hu_three_bet": 6.0,
}

VILLAIN_SEATS = ("SB", "BB")
SEATS = ("SB", "BB", "hero")
VILLAIN_KINDS = ("normal", "ai")

# Escenarios por stack: en vez de 'hands' traen 'by_stack', donde cada lista
# dice que hacer con esas manos a ese stack.
#   "shove" -> la mano se empuja, "call" -> la mano iguala.
# Lo que no este en ninguna de esas listas se considera la accion complementaria
# (fold). La lista "marginal" no se penaliza en ningun caso.
BY_STACK_LIST_KEYS: Dict[str, str] = {
    "shove": "OPEN_SHOVE",
    "call": "CALL",
}
BY_STACK_MARGINAL_KEY = "marginal"

# Claves con las que se serializa la mesa hacia la API y el frontend.
SEAT_KEYS = {"SB": "sb", "BB": "bb", "hero": "hero"}

# Etiquetas y estilos de los botones, equivalentes a la maqueta.
ACTION_STYLES: Dict[str, Dict[str, object]] = {
    "OPEN_SHOVE": {"label": "Open Shove", "color": "#8B0A24", "hotkey": "S", "text": "#FFFFFF"},
    "OR": {"label": "OR", "color": "#E85A5A", "hotkey": "R", "text": "#FFFFFF"},
    "FOLD": {"label": "Fold", "color": "#ECECEC", "hotkey": "F", "text": "#333333"},
    "CALL": {"label": "Call", "color": "#3B6EA5", "hotkey": "C", "text": "#FFFFFF"},
    "ALL_IN": {"label": "All-in", "color": "#8B0A24", "hotkey": "A", "text": "#FFFFFF"},
    # Push/fold: misma pinta que Fold, otro nombre.
    "NO_SHOVE": {"label": "No empujar", "color": "#ECECEC", "hotkey": "F", "text": "#333333"},
    # Limp heads-up: el monto lo completa CONFIG.
    "LIMP": {"label": "Limp", "color": "#F5A623", "hotkey": "L", "text": "#FFFFFF"},
}


def fmt_bb(value: Optional[float]) -> str:
    """Formatea un monto en BB: 2.0 -> '2', 0.5 -> '0.5'."""
    if value is None:
        return ""
    rounded = round(float(value), 2)
    if float(rounded).is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def stack_key_for(effective_stack: float) -> str:
    """
    Clave by_stack de un stack: str(floor(stack*2)/2) -> '7.5', '2', '9'.

    Es la misma cuenta que usa el validador para exigir la grilla completa,
    asi que un stack sorteado del rango siempre cae en una clave existente.
    """
    return fmt_bb(math.floor(float(effective_stack) * 2) / 2)


def _clean(value: float) -> float:
    """Evita arrastrar error de coma flotante (ej. 12.5 - 0.5 -> 12.0)."""
    return round(float(value) + 0.0, 2)


# Stack efectivo minimo jugable. Un stack de 0 o 0.5 BB no describe una mano
# real, asi que los rangos que llegan por debajo se recortan aqui.
MIN_EFFECTIVE_STACK = 2.0
STACK_STEP = 0.5


def parse_stack_range(stack_range: str) -> Tuple[float, float]:
    """'15-9' -> (9.0, 15.0). '15+' -> (15.0, 25.0). '<9' -> (2.0, 9.0). '20' -> (20.0, 20.0)."""
    text = (stack_range or "").strip()

    if text.endswith("+"):
        low = float(text[:-1])
        return low, low + 10.0

    # '<9' y '<=9': todo lo que entra bajo ese techo, desde el minimo jugable.
    if text.startswith("<"):
        rest = text[1:]
        if rest.startswith("="):
            rest = rest[1:]
        return MIN_EFFECTIVE_STACK, float(rest)

    if "-" in text:
        a, b = text.split("-", 1)
        low, high = float(a), float(b)
        return min(low, high), max(low, high)

    single = float(text)
    return single, single


def resolve_stack_range(
    stack_range: str,
    stack_min: Optional[float] = None,
    stack_max: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Rango del stack efectivo de un escenario.

    Si el JSON declara stack_min/stack_max se usan esos, que son mas precisos
    que la etiqueta: '3.4-0' queria decir <=3.4 pero arrastraba un stack de 0.
    Si no, se parsea stack_range. El minimo nunca baja de MIN_EFFECTIVE_STACK.
    """
    if stack_min is not None and stack_max is not None:
        low, high = float(stack_min), float(stack_max)
    else:
        low, high = parse_stack_range(stack_range)

    low, high = min(low, high), max(low, high)
    return max(low, MIN_EFFECTIVE_STACK), high


def random_effective_stack(
    stack_range: str,
    stack_min: Optional[float] = None,
    stack_max: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> float:
    """
    Stack efectivo para la mano, en pasos de 0.5 BB dentro del rango resuelto.
    '15-9' sortea entre 9 y 15 BB; '<9' sortea entre 2 y 9 BB.
    """
    generator = rng or random
    low, high = resolve_stack_range(stack_range, stack_min, stack_max)
    steps = int(round((high - low) / STACK_STEP)) + 1
    offset = generator.randint(0, max(0, steps - 1))
    return _clean(low + offset * STACK_STEP)


@dataclass
class TableState:
    """
    Estado de la mesa. `bets` es la ficha COMPROMETIDA por cada asiento
    (None = sin ficha en mesa). `dead` es el dinero muerto.
    """

    effective_stack: float
    bets: Dict[str, Optional[float]] = field(default_factory=dict)
    dead: float = 0.0
    folded: Dict[str, bool] = field(default_factory=dict)

    # --- Derivados: nunca se almacenan, siempre se calculan ---
    @property
    def pot(self) -> float:
        """Pot = suma de todas las fichas en mesa + dinero muerto."""
        return _clean(
            sum(amount for amount in self.bets.values() if amount is not None) + self.dead
        )

    def stack(self, seat: str) -> float:
        """Stack mostrado = stack efectivo menos la ficha de ese jugador."""
        committed = self.bets.get(seat) or 0.0
        return _clean(max(0.0, self.effective_stack - committed))

    def is_all_in(self, seat: str) -> bool:
        amount = self.bets.get(seat)
        return amount is not None and amount >= self.effective_stack

    def copy(self) -> "TableState":
        return TableState(
            effective_stack=self.effective_stack,
            bets=dict(self.bets),
            dead=self.dead,
            folded=dict(self.folded),
        )

    def to_dict(self) -> Dict[str, object]:
        def amount(seat: str) -> Optional[float]:
            value = self.bets.get(seat)
            return None if value is None else _clean(value)

        return {
            "effective_stack": _clean(self.effective_stack),
            "pot": self.pot,
            "dead": _clean(self.dead),
            "bets": {SEAT_KEYS[seat]: amount(seat) for seat in SEATS},
            "stacks": {SEAT_KEYS[seat]: self.stack(seat) for seat in SEATS},
            "all_in": {SEAT_KEYS[seat]: self.is_all_in(seat) for seat in SEATS},
            "folded": {SEAT_KEYS[seat]: bool(self.folded.get(seat)) for seat in VILLAIN_SEATS},
        }


# --- CONFIG como amounts ---
BLINDS: Dict[str, float] = CONFIG["blinds"]  # type: ignore[assignment]
MIN_RAISE: float = CONFIG["min_raise"]  # type: ignore[assignment]
THREE_BET: float = CONFIG["three_bet"]  # type: ignore[assignment]
LIMP: float = CONFIG["limp"]  # type: ignore[assignment]
HU_RAISE: float = CONFIG["hu_raise"]  # type: ignore[assignment]
ISO: float = CONFIG["iso"]  # type: ignore[assignment]
HU_THREE_BET: float = CONFIG["hu_three_bet"]  # type: ignore[assignment]

# Claves de variante que un followup puede declarar (catalogo o inline).
FOLLOWUP_VARIANT_KEYS: Tuple[str, ...] = (
    "vs_3bet",
    "vs_3bet_ai",
    "vs_raise",
    "vs_raise_ai",
    "vs_4bet_ai",
)

# Cuanto abre el SB segun el spot, cuando hero BB ya no habla primero.
VILLAIN_OPENS: Dict[str, float] = {
    "VS_LIMP": LIMP,
    "VS_MIN_RAISE": MIN_RAISE,
}


def heads_up_from_game(game: Optional[str]) -> bool:
    """True si el escenario es heads-up. El JSON lo marca en 'game': SPIN_3MAX_HU."""
    return str(game or "").strip().upper().endswith("_HU")


def villain_seats_for(position: Optional[str], heads_up: bool) -> Tuple[str, ...]:
    """
    Que asientos de rival existen en la mesa.

    En 3-handed hero es el BTN y los dos rivales son SB y BB. En heads-up solo
    hay un rival, y se sienta en la ciega que NO postinga hero.
    """
    if not heads_up:
        return VILLAIN_SEATS

    pos = str(position or "").strip().upper()
    return ("BB",) if pos == "SB" else ("SB",)


def deal(
    effective_stack: float,
    heads_up: bool = False,
    hero_position: Optional[str] = None,
    spot: Optional[str] = None,
) -> TableState:
    """
    PASO 0 - REPARTO (estado inicial). El timer arranca aqui.

    3-handed: hero es el BTN y no posta ciega; las dos ciegas son de los
    rivales. Pot = 1.5 BB.
    Heads-up hero SB: hero YA posteo su ciega (0.5) y el unico rival es el BB
    (1). Pot = 1.5 pero la ficha de hero no es 0.
    Heads-up hero BB: el SB ya actuo y hero tiene su ciega (1) comprometida.
    No es una reaccion al azar, es el planteo del spot: el limp deja pot 2,
    el min-raise deja pot 3. Hero solo decide su respuesta.
    """
    if heads_up and str(hero_position or "").strip().upper() == "BB":
        villain_open = VILLAIN_OPENS.get(str(spot or "").strip().upper(), _clean(effective_stack))
        return TableState(
            effective_stack=_clean(effective_stack),
            bets={"SB": _clean(villain_open), "BB": None, "hero": BLINDS["BB"]},
            dead=0.0,
            folded={"SB": False, "BB": False},
        )

    if heads_up:
        return TableState(
            effective_stack=_clean(effective_stack),
            bets={"SB": None, "BB": BLINDS["BB"], "hero": BLINDS["SB"]},
            dead=0.0,
            folded={ "SB": False, "BB": False},
        )

    return TableState(
        effective_stack=_clean(effective_stack),
        bets={"SB": BLINDS["SB"], "BB": BLINDS["BB"], "hero": None},
        dead=0.0,
        folded={"SB": False, "BB": False},
    )


def hero_commit(state: TableState, action: str) -> TableState:
    """
    PASO 1 - HERO ELIGE. Se refleja la ficha de hero segun la accion.
    OPEN_SHOVE -> ficha ALL-IN. OR -> min raise. LIMP -> completa a 1 BB.
    ISO -> aisla el limp (CONFIG). THREEBET -> 3bet sobre el min-raise (CONFIG).
    ISO_AI / THREEBET_AI -> stack efectivo.
    CHECK -> no agrega nada, hero se queda con su ciega.
    CALL -> iguala la apuesta rival mas alta (tope: stack efectivo).
    FOLD / NO_SHOVE -> la ficha desaparece y lo comprometido pasa a dead:
    foldear con la ciega puesta no hace desaparecer ese dinero del pot.
    """
    new_state = state.copy()
    key = str(action).upper()

    if key in ("OPEN_SHOVE", "ISO_AI", "THREEBET_AI"):
        new_state.bets["hero"] = new_state.effective_stack
    elif key == "OR":
        new_state.bets["hero"] = MIN_RAISE
    elif key == "LIMP":
        new_state.bets["hero"] = LIMP
    elif key == "ISO":
        new_state.bets["hero"] = ISO
    elif key == "THREEBET":
        new_state.bets["hero"] = HU_THREE_BET
    elif key == "CHECK":
        pass
        pass
    elif key == "CALL":
        rival_max = max(
            [amount or 0.0 for seat, amount in new_state.bets.items() if seat != "hero"]
            + [0.0]
        )
        new_state.bets["hero"] = _clean(min(new_state.effective_stack, rival_max))
    elif key in ("FOLD", "NO_SHOVE"):
        new_state.dead = _clean(new_state.dead + (new_state.bets.get("hero") or 0.0))
        new_state.bets["hero"] = None
    else:
        raise ValueError(f"Accion de hero no reconocida en el reparto: {action}")

    return new_state


def villain_respond(
    state: TableState, actor: str, kind: str, heads_up: bool = False
) -> TableState:
    """
    PASO 2 - RESPUESTA DEL RIVAL (solo si la accion de hero fue correcta).

    El rival que responde sube. El tamano sale de CONFIG y depende de lo que
    hizo hero: tras un OR es el 3bet (4), tras un LIMP el raise del BB (3).
    En all-in sube el stack efectivo.

    En 3-handed el otro rival tira la mano: su ciega pasa integra a dinero
    muerto y desaparece de `bets`, para no contar ese monto dos veces.
    En heads-up no hay otro rival, asi que solo sube el suyo.
    """
    if actor not in VILLAIN_SEATS:
        raise ValueError(f"Rival desconocido: {actor}")
    if kind not in VILLAIN_KINDS:
        raise ValueError(f"Tipo de respuesta desconocido: {kind}")

    new_state = state.copy()
    after_limp = _clean(new_state.bets.get("hero") or 0.0) == _clean(LIMP)

    if kind == "ai":
        new_state.bets[actor] = new_state.effective_stack
    elif after_limp:
        new_state.bets[actor] = HU_RAISE
    else:
        new_state.bets[actor] = THREE_BET

    if not heads_up:
        other = "BB" if actor == "SB" else "SB"
        folded_blind = new_state.bets.get(other) or 0.0
        new_state.dead = _clean(new_state.dead + folded_blind)
        new_state.bets[other] = None
        new_state.folded[other] = True

    return new_state


def hero_respond(state: TableState, action: str, actor: str) -> TableState:
    """
    PASO 3 - HERO RESPONDE AL raise del rival.
    FOLD -> su ficha pasa integra a dead. CALL -> iguala al rival. ALL_IN -> stack efectivo.
    """
    new_state = state.copy()
    key = str(action).upper()
    rival_bet = new_state.bets.get(actor) or THREE_BET

    if key == "FOLD":
        new_state.dead = _clean(new_state.dead + (new_state.bets.get("hero") or 0.0))
        new_state.bets["hero"] = None
    elif key == "CALL":
        new_state.bets["hero"] = _clean(rival_bet)
    elif key == "ALL_IN":
        new_state.bets["hero"] = new_state.effective_stack
    else:
        raise ValueError(f"Respuesta al raise no reconocida: {action}")

    return new_state


def roll_villain(
    heads_up: bool = False,
    seats: Optional[Tuple[str, ...]] = None,
    after_limp: bool = False,
    spot: Optional[str] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, str]:
    """
    PASO 2 - El rival se elige AL AZAR: quien responde y que tipo de raise.

    En 3-handed compite entre SB y BB. En heads-up solo hay un rival, asi que
    su asiento ya esta fijo por la posicion de hero. En los spots de defensa
    de la BB (vs limp / vs min-raise) la data solo contempla que el SB responda
    empujando: el tipo no se sortea, siempre es all-in.
    """
    generator = rng or random
    candidates = seats or VILLAIN_SEATS
    actor = generator.choice(candidates) if len(candidates) > 1 else candidates[0]

    spot_key = str(spot or "").strip().upper()
    if spot_key in ("VS_LIMP", "VS_MIN_RAISE"):
        kind = "ai"
    else:
        kind = generator.choice(VILLAIN_KINDS)

    if kind == "ai":
        label = "4bet all-in" if spot_key == "VS_MIN_RAISE" else (
            "3bet all-in" if not after_limp else "raise all-in"
        )
    else:
        label = "raise" if after_limp else "3bet"
    return {
        "actor": actor,
        "kind": kind,
        "label": f"{actor} {label}",
    }


def response_actions_for_kind(kind: str) -> Tuple[str, ...]:
    """
    Botones del PASO 2/3.
    vs raise all-in: solo Fold y Call. vs raise normal: Fold, Call y All-in.
    """
    if kind == "ai":
        return ("FOLD", "CALL")
    return ("FOLD", "CALL", "ALL_IN")


def build_action_options(action_ids: Tuple[str, ...], has_followup: bool = False) -> list:
    """
    Convierte ids de accion en ActionOption usando CONFIG/ACTION_STYLES.
    El label de OR incluye el monto del min raise (2 BB).
    """
    from app.schemas.training import ActionOption

    options = []
    for action_id in action_ids:
        style = ACTION_STYLES.get(action_id, {})
        label = str(style.get("label", action_id))
        if action_id == "OR":
            label = f"{label} {fmt_bb(MIN_RAISE)} BB"

        options.append(
            ActionOption(
                id=action_id,
                label=label,
                color=str(style.get("color", "#E85A5A")),
                hotkey=str(style.get("hotkey")) if style.get("hotkey") else None,
                has_followup=has_followup,
            )
        )
    return options


def action_label(action_id: str, fallback: Optional[str] = None) -> str:
    """Etiqueta legible de una accion, respetando el label del escenario si existe."""
    if fallback:
        return fallback
    style = ACTION_STYLES.get(str(action_id).upper())
    if not style:
        return str(action_id)
    label = str(style.get("label", action_id))
    if str(action_id).upper() == "OR":
        label = f"{label} {fmt_bb(MIN_RAISE)} BB"
    return label


def followup_key_for_kind(
    kind: str, after_limp: bool = False, spot: Optional[str] = None
) -> str:
    """
    Que clave del followup decide la respuesta correcta.

    Un OR se responde a un 3bet -> 'vs_3bet'. Un limp se responde a un raise
    -> 'vs_raise'. Un 3bet de la BB se responde a un 4bet -> 'vs_4bet_ai'
    (la data solo contempla que el SB responda empujando). El sufijo _ai es
    cuando el rival se va all-in.
    """
    spot_key = str(spot or "").strip().upper()
    if spot_key == "VS_MIN_RAISE":
        return "vs_4bet_ai"
    base = "vs_raise" if after_limp else "vs_3bet"
    return f"{base}_ai" if kind == "ai" else base


def resolve_followup_action(
    followups_cfg: Dict[str, object],
    followup_ref: Optional[object],
    kind: str,
    after_limp: bool = False,
    spot: Optional[str] = None,
) -> Optional[str]:
    """
    Resuelve la accion correcta del followup contra el tipo de raise que ocurrio.

    Los JSON declaran por followup:
        "4BET_AI": {"vs_3bet": "ALL_IN", "vs_3bet_ai": "CALL"}
        "LIMP_CALL_FOLD": {"vs_raise": "CALL", "vs_raise_ai": "FOLD"}
    Asi la misma mano puede pedir CALL ante all-in y ALL_IN ante 3bet normal.
    Algunos escenarios traen el followup inline por mano, sin catalogo:
        "followup": {"vs_4bet_ai": "CALL"}
    Si el followup no declara la variante, se usa el propio id como fallback.
    """
    if not followup_ref:
        return None

    if isinstance(followup_ref, dict):
        entry = followup_ref
        fallback = None
    else:
        entry = (followups_cfg or {}).get(str(followup_ref))
        fallback = str(followup_ref).strip().upper()

    if isinstance(entry, dict):
        value = entry.get(followup_key_for_kind(kind, after_limp, spot))
        if isinstance(value, str) and value:
            return value.strip().upper()

    return fallback


def build_table_payload(
    effective_stack: float,
    stack_range: str,
    action: Optional[str] = None,
    villain: Optional[Dict[str, str]] = None,
    hero_response: Optional[str] = None,
    heads_up: bool = False,
    hero_position: Optional[str] = None,
    spot: Optional[str] = None,
) -> Dict[str, object]:
    """
    Reproduce la secuencia completa de la mano y devuelve el estado final.
    Si no se pasa accion, devuelve el reparto inicial (PASO 0).
    """
    state = deal(effective_stack, heads_up=heads_up, hero_position=hero_position, spot=spot)

    if action is None:
        return state.to_dict()

    state = hero_commit(state, action)

    if villain is not None and hero_response is not None:
        state = villain_respond(state, villain["actor"], villain["kind"], heads_up=heads_up)
        state = hero_respond(state, hero_response, villain["actor"])
    elif villain is not None:
        state = villain_respond(state, villain["actor"], villain["kind"], heads_up=heads_up)

    return state.to_dict()
