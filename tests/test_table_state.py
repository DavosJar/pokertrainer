"""
Tests de la maqueta de la mano (prompt.md).

Los montos esperados son los del enunciado con stack efectivo 12.5 BB:
  reparto pot 1.5 | OR pot 3.5 | 3bet normal pot 7 | 3bet all-in pot 15.5
  fold 7 | call 9 | all-in 17.5 | vs all-in: call 26, fold 15.5
"""

import random

import pytest

from app.services.table_state import (
    HU_RAISE,
    HU_THREE_BET,
    ISO,
    THREE_BET,
    build_table_payload,
    deal,
    followup_key_for_kind,
    heads_up_from_game,
    hero_commit,
    hero_respond,
    parse_stack_range,
    random_effective_stack,
    resolve_followup_action,
    response_actions_for_kind,
    villain_respond,
    villain_seats_for,
    roll_villain,
)


EFF = 12.5


# --- PASO 0 - REPARTO ---
def test_deal_is_clean():
    state = deal(EFF)

    assert state.bets == {"SB": 0.5, "BB": 1.0, "hero": None}
    assert state.pot == 1.5
    assert state.dead == 0
    assert state.stack("SB") == 12.0
    assert state.stack("BB") == 11.5
    assert state.stack("hero") == 12.5
    assert state.folded == {"SB": False, "BB": False}


# --- PASO 1 - HERO ELIGE ---
def test_hero_shove_puts_all_in():
    state = hero_commit(deal(EFF), "OPEN_SHOVE")

    assert state.bets["hero"] == EFF
    assert state.stack("hero") == 0
    assert state.pot == 14
    assert state.is_all_in("hero")


def test_hero_fold_shows_no_chip():
    state = hero_commit(deal(EFF), "FOLD")

    assert state.bets["hero"] is None
    assert state.pot == 1.5
    assert state.stack("hero") == EFF


def test_hero_or_commits_min_raise():
    state = hero_commit(deal(EFF), "OR")

    assert state.bets["hero"] == 2
    assert state.stack("hero") == 10.5
    assert state.pot == 3.5


# --- PASO 2 - RESPUESTA DEL RIVAL ---
def test_villain_respond_normal():
    """Ejemplo del prompt: SB hace 3bet normal, el BB tira."""
    state = villain_respond(hero_commit(deal(EFF), "OR"), "SB", "normal")

    assert state.bets["SB"] == 4
    assert state.stack("SB") == 8.5
    # El otro tira: la ciega del BB pasa integra a dinero muerto y su ficha desaparece
    assert state.bets["BB"] is None
    assert state.dead == 1
    assert state.folded["BB"] is True
    assert state.pot == 7


def test_villain_respond_all_in():
    """Ejemplo del prompt: SB hace 3bet all-in, el BB tira."""
    state = villain_respond(hero_commit(deal(EFF), "OR"), "SB", "ai")

    assert state.bets["SB"] == EFF
    assert state.stack("SB") == 0
    assert state.is_all_in("SB")
    assert state.bets["BB"] is None
    assert state.dead == 1
    assert state.pot == 15.5


def test_villain_bb_three_bet_moves_the_sb_blind():
    """Si responde el BB, la ciega que pasa a dead es la del SB (0.5)."""
    state = villain_respond(hero_commit(deal(EFF), "OR"), "BB", "normal")

    assert state.bets["BB"] == 4
    assert state.bets["SB"] is None
    assert state.dead == 0.5
    assert state.folded["SB"] is True
    assert state.pot == 6.5


def test_villain_kind_is_validated():
    with pytest.raises(ValueError):
        villain_respond(deal(EFF), "HERO", "normal")

    with pytest.raises(ValueError):
        villain_respond(deal(EFF), "SB", "rebuy")


def test_folded_blind_is_never_double_counted():
    """El monto del rival que tira vive solo en dead, no en fichas y dead."""
    for kind in ("normal", "ai"):
        state = villain_respond(hero_commit(deal(EFF), "OR"), "SB", kind)
        on_table = sum(v for v in state.bets.values() if v is not None)
        assert on_table + state.dead == state.pot


# --- PASO 3 - HERO RESPONDE ---
def test_hero_responses_vs_3bet_normal():
    base = villain_respond(hero_commit(deal(EFF), "OR"), "SB", "normal")

    folded = hero_respond(base, "FOLD", "SB")
    assert folded.bets["hero"] is None
    assert folded.dead == 3
    assert folded.pot == 7

    called = hero_respond(base, "CALL", "SB")
    assert called.bets["hero"] == 4
    assert called.stack("hero") == 8.5
    assert called.pot == 9

    shoved = hero_respond(base, "ALL_IN", "SB")
    assert shoved.bets["hero"] == EFF
    assert shoved.stack("hero") == 0
    assert shoved.pot == 17.5


def test_hero_responses_vs_3bet_all_in():
    base = villain_respond(hero_commit(deal(EFF), "OR"), "SB", "ai")

    called = hero_respond(base, "CALL", "SB")
    assert called.bets["hero"] == EFF
    assert called.pot == 26

    folded = hero_respond(base, "FOLD", "SB")
    assert folded.dead == 3
    assert folded.pot == 15.5


# --- Botones y followups ---
def test_buttons_change_with_villain_kind():
    assert response_actions_for_kind("ai") == ("FOLD", "CALL")
    assert response_actions_for_kind("normal") == ("FOLD", "CALL", "ALL_IN")


def test_followup_resolves_per_villain_kind():
    cfg = {"4BET_AI": {"label": "x", "vs_3bet": "ALL_IN", "vs_3bet_ai": "CALL"}}

    assert resolve_followup_action(cfg, "4BET_AI", "normal") == "ALL_IN"
    assert resolve_followup_action(cfg, "4BET_AI", "ai") == "CALL"
    # Sin followup no hay respuesta de nivel 2
    assert resolve_followup_action(cfg, None, "ai") is None


def test_roll_villain_covers_actors_and_kinds():
    actors, kinds = set(), set()
    for _ in range(200):
        v = roll_villain(random.Random())
        actors.add(v["actor"])
        kinds.add(v["kind"])

    assert actors == {"SB", "BB"}
    assert kinds == {"normal", "ai"}


# --- Stacks desde el stack_range ---
def test_stack_range_parsing():
    assert parse_stack_range("15-9") == (9.0, 15.0)
    assert parse_stack_range("9-15") == (9.0, 15.0)
    assert parse_stack_range("15+") == (15.0, 25.0)
    assert parse_stack_range("20") == (20.0, 20.0)


def test_effective_stack_stays_inside_range_in_half_steps():
    for _ in range(100):
        value = random_effective_stack("15-9")
        assert 9.0 <= value <= 15.0
        assert (value * 2) % 1 == 0

    for _ in range(100):
        value = random_effective_stack("15+")
        assert 15.0 <= value <= 25.0


# --- Payload de la secuencia completa ---
def test_build_table_payload_matches_prompt_numbers():
    # PASO 0
    assert build_table_payload(EFF, "15-9")["pot"] == 1.5

    # PASO 1 open shove
    shove = build_table_payload(EFF, "15-9", action="OPEN_SHOVE")
    assert shove["pot"] == 14
    assert shove["stacks"]["hero"] == 0

    # PASO 1 OR + PASO 2 3bet normal
    step2 = build_table_payload(EFF, "15-9", action="OR", villain={"actor": "SB", "kind": "normal"})
    assert step2["pot"] == 7

    # PASO 3 call
    step3 = build_table_payload(
        EFF, "15-9", action="OR", villain={"actor": "SB", "kind": "normal"}, hero_response="CALL"
    )
    assert step3["pot"] == 9

    # Un reparto nuevo no hereda nada de la mano anterior
    fresh = build_table_payload(EFF, "15-9")
    assert fresh["bets"]["hero"] is None
    assert fresh["dead"] == 0
    assert fresh["folded"] == {"sb": False, "bb": False}


def test_build_table_payload_rejects_unknown_input():
    with pytest.raises(ValueError):
        hero_commit(deal(EFF), "RAISE")

    with pytest.raises(ValueError):
        hero_respond(deal(EFF), "SPLIT", "SB")


def test_serialized_keys_match_the_api_contract():
    """El frontend lee bets.sb / stacks.bb / folded.sb en minusculas."""
    payload = villain_respond(hero_commit(deal(EFF), "OR"), "SB", "normal").to_dict()

    assert set(payload["bets"]) == {"sb", "bb", "hero"}
    assert set(payload["stacks"]) == {"sb", "bb", "hero"}
    assert set(payload["folded"]) == {"sb", "bb"}
    assert payload["bets"]["sb"] == 4
    assert payload["bets"]["bb"] is None
    assert payload["folded"]["bb"] is True
    assert payload["all_in"]["hero"] is False


# --- HEADS-UP: 2 asientos, hero en el SB y un solo rival en el BB ---
def test_heads_up_deal_has_hero_posting_the_sb_blind():
    """Hero es el SB: su ciega ya esta comprometida y no hay segundo rival."""
    state = deal(EFF, heads_up=True)

    assert state.bets["hero"] == 0.5
    assert state.bets["BB"] == 1
    assert state.bets["SB"] is None
    assert state.pot == 1.5
    assert state.stack("hero") == EFF - 0.5


def test_heads_up_limp_completes_to_one_bb():
    state = hero_commit(deal(EFF, heads_up=True), "LIMP")

    assert state.bets["hero"] == 1
    assert state.pot == 2
    assert state.stack("hero") == EFF - 1


def test_heads_up_raise_after_limp_comes_from_config():
    """Tras un limp el BB sube a hu_raise (3 BB) en total, no a 3 mas."""
    base = hero_commit(deal(EFF, heads_up=True), "LIMP")
    state = villain_respond(base, "BB", "normal", heads_up=True)

    assert state.bets["BB"] == HU_RAISE
    assert state.pot == 1 + HU_RAISE
    # No hay segundo rival cuya ciega pueda pasar a dinero muerto.
    assert state.dead == 0
    assert state.bets["SB"] is None
    assert state.folded["SB"] is False


def test_heads_up_three_bet_after_open_raise_is_still_four():
    state = villain_respond(hero_commit(deal(EFF, heads_up=True), "OR"), "BB", "normal", heads_up=True)

    assert state.bets["BB"] == THREE_BET
    assert state.pot == 2 + THREE_BET


def test_heads_up_all_in_raise_commits_the_effective_stack():
    state = villain_respond(hero_commit(deal(EFF, heads_up=True), "LIMP"), "BB", "ai", heads_up=True)

    assert state.bets["BB"] == EFF
    assert state.is_all_in("BB") is True


def test_heads_up_call_after_limp_raise_matches_the_rival():
    base = villain_respond(hero_commit(deal(EFF, heads_up=True), "LIMP"), "BB", "normal", heads_up=True)
    state = hero_respond(base, "CALL", "BB")

    assert state.bets["hero"] == state.bets["BB"] == HU_RAISE
    assert state.pot == HU_RAISE * 2


def test_villain_seats_follow_the_position_of_hero():
    assert villain_seats_for("BTN", False) == ("SB", "BB")
    assert villain_seats_for("SB", True) == ("BB",)
    assert villain_seats_for("BB", True) == ("SB",)


def test_heads_up_is_read_from_the_game_field():
    assert heads_up_from_game("SPIN_3MAX_HU") is True
    assert heads_up_from_game("SPIN_3MAX") is False
    assert heads_up_from_game(None) is False


def test_followup_key_depends_on_what_hero_did():
    """Tras OR el rival hace 3bet; tras LIMP hace raise. Son claves distintas."""
    assert followup_key_for_kind("normal", after_limp=False) == "vs_3bet"
    assert followup_key_for_kind("ai", after_limp=False) == "vs_3bet_ai"
    assert followup_key_for_kind("normal", after_limp=True) == "vs_raise"
    assert followup_key_for_kind("ai", after_limp=True) == "vs_raise_ai"


def test_resolve_followup_action_picks_the_limp_variant():
    followups = {"LIMP_CALL_FOLD": {"vs_raise": "CALL", "vs_raise_ai": "FOLD"}}

    assert resolve_followup_action(followups, "LIMP_CALL_FOLD", "normal", after_limp=True) == "CALL"
    assert resolve_followup_action(followups, "LIMP_CALL_FOLD", "ai", after_limp=True) == "FOLD"
    # Sin la variante de limp se resuelve por la de 3bet.
    assert resolve_followup_action(followups, "LIMP_CALL_FOLD", "normal", after_limp=False) == "LIMP_CALL_FOLD"


def test_heads_up_payload_keeps_the_api_keys():
    payload = build_table_payload(EFF, "15-9", action="LIMP", heads_up=True)

    assert set(payload["bets"]) == {"sb", "bb", "hero"}
    assert payload["bets"]["hero"] == 1
    assert payload["bets"]["sb"] is None
    assert payload["pot"] == 2


# --- HEADS-UP hero BB: el SB ya empujo y hero decide Call o Fold ---
def test_vs_shove_deal_shows_the_shove_and_hero_blind():
    state = deal(EFF, heads_up=True, hero_position="BB")

    assert state.bets["SB"] == EFF
    assert state.is_all_in("SB") is True
    assert state.bets["BB"] is None
    assert state.bets["hero"] == 1
    assert state.pot == EFF + 1


def test_vs_shove_call_matches_the_effective_stack():
    state = hero_commit(deal(EFF, heads_up=True, hero_position="BB"), "CALL")

    assert state.bets["hero"] == EFF
    assert state.pot == EFF * 2


def test_vs_shove_fold_moves_the_blind_to_dead():
    state = hero_commit(deal(EFF, heads_up=True, hero_position="BB"), "FOLD")

    assert state.bets["hero"] is None
    assert state.dead == 1
    assert state.pot == EFF + 1


def test_fold_with_a_posted_blind_keeps_the_money_in_the_pot():
    """Foldear desde el SB heads-up: la ciega 0.5 va a dead, no desaparece."""
    state = hero_commit(deal(EFF, heads_up=True, hero_position="SB"), "FOLD")

    assert state.bets["hero"] is None
    assert state.dead == 0.5
    assert state.pot == 1.5


# --- HEADS-UP hero BB en defensa: VS_LIMP y VS_MIN_RAISE ---
def test_vs_limp_deal_shows_limp_and_hero_blind():
    state = deal(EFF, heads_up=True, hero_position="BB", spot="VS_LIMP")

    assert state.bets["SB"] == 1
    assert state.bets["BB"] is None
    assert state.bets["hero"] == 1
    assert state.pot == 2


def test_vs_min_raise_deal_shows_the_raise_and_hero_blind():
    state = deal(EFF, heads_up=True, hero_position="BB", spot="VS_MIN_RAISE")

    assert state.bets["SB"] == 2
    assert state.bets["hero"] == 1
    assert state.pot == 3


def test_iso_and_threebet_come_from_config():
    iso = hero_commit(deal(EFF, heads_up=True, hero_position="BB", spot="VS_LIMP"), "ISO")
    assert iso.bets["hero"] == ISO
    assert iso.pot == 1 + ISO

    three = hero_commit(
        deal(EFF, heads_up=True, hero_position="BB", spot="VS_MIN_RAISE"), "THREEBET"
    )
    assert three.bets["hero"] == HU_THREE_BET
    assert three.pot == 2 + HU_THREE_BET


def test_check_keeps_hero_blind_and_ai_commits_the_stack():
    checked = hero_commit(deal(EFF, heads_up=True, hero_position="BB", spot="VS_LIMP"), "CHECK")
    assert checked.bets["hero"] == 1
    assert checked.pot == 2

    iso_ai = hero_commit(deal(EFF, heads_up=True, hero_position="BB", spot="VS_LIMP"), "ISO_AI")
    assert iso_ai.bets["hero"] == EFF

    three_ai = hero_commit(
        deal(EFF, heads_up=True, hero_position="BB", spot="VS_MIN_RAISE"), "THREEBET_AI"
    )
    assert three_ai.bets["hero"] == EFF


def test_defense_villain_always_shoves():
    """En defensa de la BB la data solo contempla el shove del SB: no se sortea."""
    for spot, label in (("VS_LIMP", "SB 3bet all-in"), ("VS_MIN_RAISE", "SB 4bet all-in")):
        for _ in range(20):
            villain = roll_villain(heads_up=True, seats=("SB",), spot=spot)
            assert villain == {"actor": "SB", "kind": "ai", "label": label}


def test_followup_key_for_fourbet_spot():
    assert followup_key_for_kind("ai", spot="VS_MIN_RAISE") == "vs_4bet_ai"
    assert followup_key_for_kind("ai", after_limp=True) == "vs_raise_ai"
    assert followup_key_for_kind("ai") == "vs_3bet_ai"


def test_resolve_followup_action_accepts_inline_dict():
    # En el spot de 4bet la clave siempre es vs_4bet_ai: el SB siempre empuja.
    assert (
        resolve_followup_action({}, {"vs_4bet_ai": "CALL"}, "ai", spot="VS_MIN_RAISE")
        == "CALL"
    )
    assert (
        resolve_followup_action({}, {"vs_4bet_ai": "CALL"}, "normal", spot="VS_MIN_RAISE")
        == "CALL"
    )
    assert resolve_followup_action({}, {"vs_4bet_ai": "CALL"}, "ai") is None