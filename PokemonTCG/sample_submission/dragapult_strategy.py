"""Deck-aware strategy layer for the Dragapult ex / Dusknoir deck.

Overrides generic heuristic scores to prioritize the Dragapult game plan:
1. Get Dragapult ex powered up with 3 energy for Phantom Dive (200dmg + bench snipe)
2. Use Dusknoir's Cursed Blast (130dmg suicide) to finish high-value targets
3. Use Munkidori to move damage counters onto opponent's Pokemon
4. Never waste energy on utility Pokemon (Budew, Meowth ex, Fezandipiti ex)
"""
from cg.api import (
    Observation, Option, OptionType, SelectContext,
    AreaType, EnergyType, CardType, Pokemon, PlayerState, State,
)
from card_db import get_card, get_attack

# Card IDs for our deck
DREEPY = 119
DRAKLOAK = 120
DRAGAPULT_EX = 121
DUSKULL = 131
DUSCLOPS = 132
DUSKNOIR = 133
MUNKIDORI = 112
BUDEW = 235
FEZANDIPITI_EX = 140
MEOWTH_EX = 1071

DRAGAPULT_LINE = {DREEPY, DRAKLOAK, DRAGAPULT_EX}
DUSKNOIR_LINE = {DUSKULL, DUSCLOPS, DUSKNOIR}
UTILITY_POKEMON = {BUDEW, FEZANDIPITI_EX, MEOWTH_EX}
ALL_ATTACKERS = {DRAGAPULT_EX, DUSKNOIR, DUSCLOPS}

PHANTOM_DIVE_ENERGY = 3  # 1 Fire + 1 Psychic + 1 any = 3 total


def adjust_score(option: Option, obs: Observation, base_score: float) -> float:
    """Adjust a heuristic score based on Dragapult strategy. Returns modified score."""
    ctx = obs.select.context
    state = obs.current
    if state is None:
        return base_score

    your = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]
    board = _read_board(your, opp)

    if ctx == SelectContext.MAIN:
        return _adjust_main(option, base_score, board, state)
    elif ctx == SelectContext.SWITCH:
        return _adjust_switch(option, base_score, board, state)
    elif ctx == SelectContext.ATTACH_TO:
        return _adjust_attach_to(option, base_score, board, your)
    elif ctx in (SelectContext.TO_HAND, SelectContext.TO_HAND_ENERGY):
        return _adjust_to_hand(option, base_score, board, state)
    elif ctx in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.TO_ACTIVE):
        return _adjust_to_active(option, base_score, board, your)
    elif ctx in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH, SelectContext.TO_FIELD):
        return _adjust_to_bench(option, base_score, board, state)
    elif ctx in (SelectContext.DAMAGE_COUNTER_ANY,):
        return _adjust_damage_counter_placement(option, base_score, board, state)
    elif ctx == SelectContext.ACTIVATE:
        return _adjust_activate(option, base_score, board, state, obs)

    return base_score


# ---------------------------------------------------------------------------
# Board state reader
# ---------------------------------------------------------------------------

class BoardState:
    def __init__(self):
        self.has_dragapult_active = False
        self.dragapult_active_energy = 0
        self.dragapult_active_hp = 0
        self.dragapult_active_maxhp = 0
        self.dragapult_can_phantom_dive = False
        self.dragapult_on_bench = []
        self.drakloak_anywhere = []
        self.dreepy_anywhere = []
        self.dusknoir_ready = False
        self.dusclops_ready = False
        self.has_munkidori = False
        self.munkidori_has_dark = False
        self.active_id = 0
        self.active_is_utility = False
        self.active_can_attack = False
        self.bench_dragapults_with_energy = 0
        self.total_dragapult_energy = 0
        self.opp_active_hp = 0
        self.opp_active_id = 0
        self.opp_bench_pokemon = []
        self.opp_lowest_bench_hp = 999


def _read_board(your: PlayerState, opp: PlayerState) -> BoardState:
    b = BoardState()

    active = your.active[0] if your.active and your.active[0] else None
    if active:
        b.active_id = active.id
        b.active_is_utility = active.id in UTILITY_POKEMON
        cd = get_card(active.id)
        if cd:
            for atk_id in cd.attacks:
                atk = get_attack(atk_id)
                if atk and len(active.energies) >= len(atk.energies):
                    b.active_can_attack = True
                    break

        if active.id == DRAGAPULT_EX:
            b.has_dragapult_active = True
            b.dragapult_active_energy = len(active.energies)
            b.dragapult_active_hp = active.hp
            b.dragapult_active_maxhp = active.maxHp
            b.dragapult_can_phantom_dive = len(active.energies) >= PHANTOM_DIVE_ENERGY
            b.total_dragapult_energy = len(active.energies)

    for p in your.bench:
        if p is None:
            continue
        if p.id == DRAGAPULT_EX:
            b.dragapult_on_bench.append(p)
            b.total_dragapult_energy += len(p.energies)
            if len(p.energies) > 0:
                b.bench_dragapults_with_energy += 1
        elif p.id == DRAKLOAK:
            b.drakloak_anywhere.append(p)
        elif p.id == DREEPY:
            b.dreepy_anywhere.append(p)
        elif p.id == DUSKNOIR:
            b.dusknoir_ready = True
        elif p.id == DUSCLOPS:
            b.dusclops_ready = True
        elif p.id == MUNKIDORI:
            b.has_munkidori = True
            if any(e == EnergyType.DARKNESS for e in p.energies):
                b.munkidori_has_dark = True

    if active and active.id == DRAKLOAK:
        b.drakloak_anywhere.append(active)
    if active and active.id == DREEPY:
        b.dreepy_anywhere.append(active)

    opp_active = opp.active[0] if opp.active and opp.active[0] else None
    if opp_active:
        b.opp_active_hp = opp_active.hp
        b.opp_active_id = opp_active.id
    for p in opp.bench:
        if p and p.hp > 0:
            b.opp_bench_pokemon.append(p)
            b.opp_lowest_bench_hp = min(b.opp_lowest_bench_hp, p.hp)

    return b


# ---------------------------------------------------------------------------
# Main phase adjustments
# ---------------------------------------------------------------------------

def _adjust_main(option: Option, score: float, board: BoardState, state: State) -> float:
    otype = option.type

    if otype == OptionType.EVOLVE:
        evo_target_area = option.inPlayArea
        if option.cardId:
            cd = get_card(option.cardId)
        else:
            cd = None
            if option.area is not None and option.index is not None:
                your = state.players[state.yourIndex]
                if option.area == AreaType.HAND and your.hand and option.index < len(your.hand):
                    cd = get_card(your.hand[option.index].id)

        target_poke = None
        if evo_target_area is not None:
            your = state.players[state.yourIndex]
            if evo_target_area == AreaType.ACTIVE and your.active and your.active[0]:
                target_poke = your.active[0]
            elif evo_target_area == AreaType.BENCH and option.inPlayIndex is not None:
                if option.inPlayIndex < len(your.bench):
                    target_poke = your.bench[option.inPlayIndex]

        if target_poke and target_poke.id in DRAGAPULT_LINE:
            score += 200.0
            if evo_target_area == AreaType.ACTIVE:
                score += 100.0

        if target_poke and target_poke.id in DUSKNOIR_LINE:
            score += 50.0

        return score

    if otype == OptionType.ATTACH:
        target_poke = None
        if option.inPlayArea is not None and option.inPlayIndex is not None:
            your = state.players[state.yourIndex]
            if option.inPlayArea == AreaType.ACTIVE and your.active and your.active[0]:
                target_poke = your.active[0]
            elif option.inPlayArea == AreaType.BENCH and option.inPlayIndex < len(your.bench):
                target_poke = your.bench[option.inPlayIndex]

        if target_poke:
            if target_poke.id == DRAGAPULT_EX:
                energy_count = len(target_poke.energies)
                if energy_count < PHANTOM_DIVE_ENERGY:
                    score += 500.0
                    if energy_count == PHANTOM_DIVE_ENERGY - 1:
                        score += 300.0
                else:
                    score += 50.0
            elif target_poke.id == DRAKLOAK:
                score += 100.0
            elif target_poke.id == MUNKIDORI:
                src_card = None
                if option.area == AreaType.HAND and option.index is not None:
                    your = state.players[state.yourIndex]
                    if your.hand and option.index < len(your.hand):
                        src_card = get_card(your.hand[option.index].id)
                if src_card and src_card.energyType == EnergyType.DARKNESS:
                    score += 200.0
                else:
                    score -= 200.0
            elif target_poke.id in UTILITY_POKEMON:
                score -= 500.0
            elif target_poke.id in DUSKNOIR_LINE:
                score -= 300.0

        return score

    if otype == OptionType.ATTACK:
        atk = get_attack(option.attackId)
        if atk and atk.name == "Phantom Dive":
            score += 500.0
        elif atk and atk.name == "Jet Headbutt" and board.has_dragapult_active:
            if board.dragapult_active_energy < PHANTOM_DIVE_ENERGY:
                score -= 200.0
        elif atk and atk.damage <= 10:
            if not board.dragapult_can_phantom_dive:
                score -= 300.0

        return score

    if otype == OptionType.ABILITY:
        ability_poke = None
        if option.area is not None and option.index is not None:
            your = state.players[state.yourIndex]
            if option.area == AreaType.ACTIVE and your.active and your.active[0]:
                ability_poke = your.active[0]
            elif option.area == AreaType.BENCH and option.index < len(your.bench):
                ability_poke = your.bench[option.index]

        if ability_poke:
            if ability_poke.id == DUSKNOIR:
                opp = state.players[1 - state.yourIndex]
                opp_active = opp.active[0] if opp.active and opp.active[0] else None
                if opp_active:
                    opp_cd = get_card(opp_active.id)
                    if opp_active.hp <= 130:
                        score += 800.0
                        if opp_cd and opp_cd.ex:
                            score += 500.0
                    elif opp_cd and opp_cd.ex and opp_active.hp <= 130:
                        score += 600.0
                for bp in board.opp_bench_pokemon:
                    if bp.hp <= 130:
                        bcd = get_card(bp.id)
                        if bcd and bcd.ex:
                            score += 400.0
                            break

            elif ability_poke.id == DUSCLOPS:
                for bp in board.opp_bench_pokemon:
                    if bp.hp <= 50:
                        score += 300.0
                        break

            elif ability_poke.id == MUNKIDORI and board.munkidori_has_dark:
                score += 200.0

            elif ability_poke.id == DRAKLOAK:
                score += 100.0

        return score

    if otype == OptionType.END:
        if not board.has_dragapult_active and board.dragapult_on_bench:
            score += 50.0
        if board.active_is_utility and not board.active_can_attack:
            score += 100.0

        return score

    if otype == OptionType.RETREAT:
        if board.active_is_utility and board.dragapult_on_bench:
            score += 400.0
        if board.active_id in (DREEPY, DRAKLOAK) and board.dragapult_on_bench:
            best_bench_energy = max((len(p.energies) for p in board.dragapult_on_bench), default=0)
            if best_bench_energy > 0:
                score += 300.0

        return score

    return score


# ---------------------------------------------------------------------------
# Card selection adjustments
# ---------------------------------------------------------------------------

def _adjust_attach_to(option: Option, score: float, board: BoardState, your: PlayerState) -> float:
    poke = None
    area = option.inPlayArea if option.inPlayArea is not None else option.area
    index = option.inPlayIndex if option.inPlayIndex is not None else option.index
    if area == AreaType.ACTIVE and your.active and your.active[0]:
        poke = your.active[0]
    elif area == AreaType.BENCH and index is not None and index < len(your.bench):
        poke = your.bench[index]

    if poke is None:
        return score

    if poke.id == DRAGAPULT_EX:
        energy = len(poke.energies)
        if energy < PHANTOM_DIVE_ENERGY:
            score += 500.0
            if energy == PHANTOM_DIVE_ENERGY - 1:
                score += 300.0
    elif poke.id == DRAKLOAK:
        score += 50.0
    elif poke.id in UTILITY_POKEMON:
        score -= 500.0
    elif poke.id in DUSKNOIR_LINE:
        score -= 300.0

    return score


def _adjust_to_hand(option: Option, score: float, board: BoardState, state: State) -> float:
    cid = _resolve_card_id_simple(option, state)
    if cid is None:
        return score

    cd = get_card(cid)
    if cd is None:
        return score

    if cid == DRAGAPULT_EX:
        if not board.has_dragapult_active and not board.dragapult_on_bench:
            score += 300.0
        else:
            score += 100.0
    elif cid == DRAKLOAK and board.dreepy_anywhere:
        score += 150.0
    elif cid == DREEPY and len(board.dreepy_anywhere) + len(board.drakloak_anywhere) == 0:
        score += 100.0
    elif cid == DUSKNOIR:
        score += 80.0
    elif cid == DUSCLOPS and any(p.id == DUSKULL for p in _all_pokemon(state)):
        score += 70.0
    elif cd.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        if board.has_dragapult_active and board.dragapult_active_energy < PHANTOM_DIVE_ENERGY:
            score += 200.0
        elif board.dragapult_on_bench and board.total_dragapult_energy < PHANTOM_DIVE_ENERGY:
            score += 150.0

    return score


def _adjust_to_active(option: Option, score: float, board: BoardState, your: PlayerState) -> float:
    poke = None
    if option.area == AreaType.BENCH and option.index is not None and option.index < len(your.bench):
        poke = your.bench[option.index]

    if poke is None:
        return score

    if poke.id == DRAGAPULT_EX:
        score += 500.0
        if len(poke.energies) >= PHANTOM_DIVE_ENERGY:
            score += 500.0
    elif poke.id in UTILITY_POKEMON:
        score -= 300.0

    return score


def _adjust_to_bench(option: Option, score: float, board: BoardState, state: State) -> float:
    cid = _resolve_card_id_simple(option, state)
    if cid is None:
        return score

    if cid == DREEPY:
        score += 100.0
    elif cid == DUSKULL:
        score += 50.0
    elif cid in UTILITY_POKEMON:
        score -= 50.0

    return score


def _adjust_switch(option: Option, score: float, board: BoardState, state: State) -> float:
    your_idx = state.yourIndex
    opp = state.players[1 - your_idx]

    if option.playerIndex is not None and option.playerIndex != your_idx:
        poke = None
        if option.area == AreaType.BENCH and option.index is not None and option.index < len(opp.bench):
            poke = opp.bench[option.index]
        if poke:
            cd = get_card(poke.id)
            if cd and cd.ex and poke.hp <= 200 and board.dragapult_can_phantom_dive:
                score += 500.0
            if poke.hp <= 70 and board.dragapult_can_phantom_dive:
                score += 300.0

    return score


def _adjust_damage_counter_placement(option: Option, score: float, board: BoardState, state: State) -> float:
    opp_idx = 1 - state.yourIndex
    if option.playerIndex == opp_idx:
        poke = None
        opp = state.players[opp_idx]
        if option.area == AreaType.ACTIVE and opp.active and opp.active[0]:
            poke = opp.active[0]
        elif option.area == AreaType.BENCH and option.index is not None and option.index < len(opp.bench):
            poke = opp.bench[option.index]

        if poke:
            cd = get_card(poke.id)
            if poke.hp <= 60:
                score += 500.0
                if cd and cd.ex:
                    score += 300.0
            if cd and cd.ex:
                score += 200.0
            if poke.hp <= 130 and board.dusknoir_ready:
                score += 150.0

    return score


def _adjust_activate(option: Option, score: float, board: BoardState, state: State, obs: Observation) -> float:
    if obs.select and obs.select.contextCard:
        card_id = obs.select.contextCard.id
        if card_id == DUSKNOIR:
            opp = state.players[1 - state.yourIndex]
            opp_active = opp.active[0] if opp.active and opp.active[0] else None
            has_good_target = False
            if opp_active and opp_active.hp <= 130:
                has_good_target = True
            for bp in board.opp_bench_pokemon:
                if bp.hp <= 130:
                    cd = get_card(bp.id)
                    if cd and cd.ex:
                        has_good_target = True
            if option.type == OptionType.YES and has_good_target:
                score += 500.0
            elif option.type == OptionType.YES and not has_good_target:
                score -= 300.0
        elif card_id == DUSCLOPS:
            has_low_target = any(bp.hp <= 50 for bp in board.opp_bench_pokemon)
            opp_active = state.players[1 - state.yourIndex].active
            if opp_active and opp_active[0] and opp_active[0].hp <= 50:
                has_low_target = True
            if option.type == OptionType.YES and has_low_target:
                score += 300.0
            elif option.type == OptionType.YES:
                score -= 200.0

    return score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_card_id_simple(option: Option, state: State) -> int | None:
    if option.cardId is not None:
        return option.cardId
    if option.area is not None and option.index is not None:
        your = state.players[state.yourIndex]
        if option.area == AreaType.HAND and your.hand and option.index < len(your.hand):
            return your.hand[option.index].id
        if option.area == AreaType.ACTIVE and your.active and your.active[0]:
            return your.active[0].id
        if option.area == AreaType.BENCH and option.index < len(your.bench) and your.bench[option.index]:
            return your.bench[option.index].id
        if option.playerIndex is not None:
            player = state.players[option.playerIndex]
            if option.area == AreaType.HAND and player.hand and option.index < len(player.hand):
                return player.hand[option.index].id
            if option.area == AreaType.DISCARD and option.index < len(player.discard):
                return player.discard[option.index].id
    return None


def _all_pokemon(state: State) -> list:
    result = []
    for pi in range(2):
        p = state.players[pi]
        if p.active and p.active[0]:
            result.append(p.active[0])
        result.extend(bp for bp in p.bench if bp)
    return result
