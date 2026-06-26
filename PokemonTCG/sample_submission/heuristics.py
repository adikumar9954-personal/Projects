"""Heuristic scoring engine for Pokemon TCG AI agent.

Scores each available option based on game state context,
enabling greedy "best move right now" decision making.
"""
from cg.api import (
    Observation, Option, OptionType, SelectContext, SelectType,
    AreaType, EnergyType, CardType, Pokemon, PlayerState, State, Card,
)
from card_db import get_card, get_attack


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def score_option(option: Option, obs: Observation) -> float:
    ctx = obs.select.context
    state = obs.current
    your = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]

    if ctx == SelectContext.MAIN:
        return _score_main(option, state, your, opp)
    elif ctx == SelectContext.ATTACK:
        return _score_attack(option, your, opp)
    elif ctx == SelectContext.SWITCH:
        return _score_switch(option, state)
    elif ctx in (SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.TO_ACTIVE):
        return _score_to_active(option, your, state)
    elif ctx in (SelectContext.SETUP_BENCH_POKEMON, SelectContext.TO_BENCH, SelectContext.TO_FIELD):
        return _score_to_bench(option, your, state)
    elif ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
        return _score_damage_target(option, state)
    elif ctx == SelectContext.IS_FIRST:
        return _score_is_first(option)
    elif ctx == SelectContext.ACTIVATE:
        return _score_activate(option, obs)
    elif ctx in (SelectContext.DISCARD, SelectContext.DISCARD_ENERGY_CARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
        return _score_discard(option, state)
    elif ctx in (SelectContext.TO_HAND, SelectContext.TO_HAND_ENERGY):
        return _score_to_hand(option, state)
    elif ctx == SelectContext.EVOLVES_FROM:
        return _score_evolve_from(option, your)
    elif ctx == SelectContext.EVOLVES_TO:
        return _score_evolve_to(option, state)
    elif ctx == SelectContext.ATTACH_TO:
        return _score_attach_to(option, your, state)
    elif ctx in (SelectContext.MULLIGAN,):
        return _score_mulligan(option, your)
    elif ctx == SelectContext.COIN_HEAD:
        return 100.0 if option.type == OptionType.YES else 0.0
    else:
        return 0.0


# ---------------------------------------------------------------------------
# Main phase scoring
# ---------------------------------------------------------------------------

def _score_main(option: Option, state: State, your: PlayerState, opp: PlayerState) -> float:
    otype = option.type

    if otype == OptionType.EVOLVE:
        return _score_main_evolve(option, state, your)

    if otype == OptionType.ATTACH:
        return _score_main_attach(option, state, your)

    if otype == OptionType.PLAY:
        return _score_main_play(option, your, state)

    if otype == OptionType.ABILITY:
        return 650.0

    if otype == OptionType.ATTACK:
        return _score_main_attack(option, your, opp)

    if otype == OptionType.RETREAT:
        return _score_main_retreat(your, opp)

    if otype == OptionType.DISCARD:
        return 50.0

    if otype == OptionType.END:
        return _score_main_end(your, opp, state)

    return 0.0


def _score_main_evolve(option: Option, state: State, your: PlayerState) -> float:
    return 900.0


def _score_main_attach(option: Option, state: State, your: PlayerState) -> float:
    if state.energyAttached:
        return 750.0

    target_poke = None
    if option.inPlayArea is not None:
        target_poke = _pokemon_at(your, option.inPlayArea, option.inPlayIndex)

    if target_poke:
        target_card = get_card(target_poke.id)
        if target_card:
            is_attacker = target_card.ex or target_card.stage2 or target_card.stage1
            is_active = option.inPlayArea == AreaType.ACTIVE

            for atk_id in target_card.attacks:
                atk = get_attack(atk_id)
                if atk and len(target_poke.energies) < len(atk.energies):
                    if is_attacker and is_active:
                        return 880.0
                    if is_attacker:
                        return 860.0
                    return 830.0

            if not is_attacker and target_card.basic and target_card.hp <= 70:
                return 750.0

    return 810.0


def _score_main_play(option: Option, your: PlayerState, state: State = None) -> float:
    if option.index is None or your.hand is None:
        return 700.0
    if option.index >= len(your.hand):
        return 700.0

    hand_card = your.hand[option.index]
    card_data = get_card(hand_card.id)
    if card_data is None:
        return 700.0

    if card_data.cardType == CardType.SUPPORTER:
        return 750.0
    if card_data.cardType == CardType.ITEM:
        return 720.0
    if card_data.cardType == CardType.STADIUM:
        return 710.0
    if card_data.cardType == CardType.POKEMON:
        return 680.0
    return 700.0


def _score_main_end(your: PlayerState, opp: PlayerState, state: State) -> float:
    return -1.0


def _estimate_damage_simple(base_damage: int, your: PlayerState, opp: PlayerState) -> int:
    damage = base_damage
    your_active = _get_active(your)
    opp_active = _get_active(opp)
    if your_active and opp_active:
        your_card = get_card(your_active.id)
        opp_card = get_card(opp_active.id)
        if your_card and opp_card and opp_card.weakness:
            if your_card.energyType == opp_card.weakness:
                damage *= 2
        if your_card and opp_card and opp_card.resistance:
            if your_card.energyType == opp_card.resistance:
                damage -= 30
    return max(damage, 0)


def _score_main_attack(option: Option, your: PlayerState, opp: PlayerState) -> float:
    atk = get_attack(option.attackId)
    if atk is None:
        return 400.0

    opp_active = _get_active(opp)
    if opp_active is None:
        return 400.0 + atk.damage

    damage = _estimate_damage(atk, your, opp)

    if damage >= opp_active.hp:
        opp_card = get_card(opp_active.id)
        ko_bonus = 200.0 if opp_card and opp_card.ex else 0.0
        return 1000.0 + damage + ko_bonus

    return 400.0 + damage


def _score_main_retreat(your: PlayerState, opp: PlayerState) -> float:
    active = _get_active(your)
    if active is None:
        return -10.0

    if len(your.bench) == 0:
        return -10.0

    hp_ratio = active.hp / max(active.maxHp, 1)

    card_data = get_card(active.id)
    can_attack = False
    best_damage = 0
    if card_data:
        for atk_id in card_data.attacks:
            atk = get_attack(atk_id)
            if atk and len(active.energies) >= len(atk.energies):
                can_attack = True
                best_damage = max(best_damage, atk.damage)

    bench_ready = None
    for p in your.bench:
        if p is None:
            continue
        pcd = get_card(p.id)
        if pcd:
            for atk_id in pcd.attacks:
                atk = get_attack(atk_id)
                if atk and len(p.energies) >= len(atk.energies):
                    if bench_ready is None or atk.damage > best_damage:
                        bench_ready = p
                    break

    if hp_ratio <= 0.2 and len(your.bench) > 0:
        return 500.0
    if hp_ratio <= 0.4 and not can_attack:
        return 300.0
    if not can_attack and bench_ready:
        return 250.0

    return -10.0


def _score_switch(option: Option, state: State) -> float:
    """Score a SWITCH target. Context determines if we're pulling an opponent's
    Pokemon (Boss's Orders) or choosing which of our own to send up."""
    your = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]

    if option.playerIndex is not None and option.playerIndex != state.yourIndex:
        poke = _pokemon_at(opp, option.area, option.index)
        if poke is None:
            return 0.0
        card_data = get_card(poke.id)
        score = 0.0
        if poke.hp <= 100:
            score += 500.0
        score += (1000.0 - poke.hp)
        has_energy = len(poke.energies) > 0
        if has_energy:
            score += 200.0
        if card_data and card_data.ex:
            score += 300.0
        if card_data and (card_data.stage2 or card_data.stage1):
            score += 100.0
        our_active = _get_active(your)
        if our_active and card_data:
            our_card = get_card(our_active.id)
            if our_card and card_data.weakness and our_card.energyType == card_data.weakness:
                score += 400.0
        return score

    poke = _pokemon_at(your, option.area, option.index)
    return _score_to_active(option, your, state)


# ---------------------------------------------------------------------------
# Attack selection
# ---------------------------------------------------------------------------

def _score_attack(option: Option, your: PlayerState, opp: PlayerState) -> float:
    atk = get_attack(option.attackId)
    if atk is None:
        return 0.0

    opp_active = _get_active(opp)
    damage = _estimate_damage(atk, your, opp)

    if opp_active and damage >= opp_active.hp:
        return 10000.0 + damage

    return damage


# ---------------------------------------------------------------------------
# Pokemon placement
# ---------------------------------------------------------------------------

def _score_to_active(option: Option, your: PlayerState, state: State = None) -> float:
    poke = _pokemon_from_option(option, your)
    if poke is not None:
        score = float(poke.hp)
        score += len(poke.energies) * 50
        card_data = get_card(poke.id)
        if card_data:
            for atk_id in card_data.attacks:
                atk = get_attack(atk_id)
                if atk and len(poke.energies) >= len(atk.energies):
                    score += 200.0 + atk.damage
        return score

    cid = _resolve_card_id(option, state) if state else (option.cardId if option.cardId else None)
    card_data = get_card(cid) if cid else None
    if card_data:
        return float(card_data.hp)
    return 0.0


def _score_to_bench(option: Option, your: PlayerState, state: State = None) -> float:
    cid = _resolve_card_id(option, state) if state else (option.cardId if option.cardId else None)
    card_data = get_card(cid) if cid else None
    if card_data is None:
        return 0.0

    if card_data.basic:
        if card_data.evolvesFrom is None and any(
            c.evolvesFrom == card_data.name for c in _get_evolution_targets(card_data)
        ):
            return 100.0
        return 50.0 + card_data.hp
    return float(card_data.hp)


def _get_evolution_targets(card_data):
    from card_db import get_all_cards
    return [c for c in get_all_cards().values() if c.evolvesFrom == card_data.name]


# ---------------------------------------------------------------------------
# Damage targeting
# ---------------------------------------------------------------------------

def _score_damage_target(option: Option, state: State) -> float:
    opp_index = 1 - state.yourIndex
    if option.playerIndex == opp_index:
        poke = _pokemon_at(state.players[option.playerIndex], option.area, option.index)
        if poke:
            return 1000.0 - poke.hp
        return 500.0
    return 0.0


# ---------------------------------------------------------------------------
# Yes/No decisions
# ---------------------------------------------------------------------------

def _score_is_first(option: Option) -> float:
    if option.type == OptionType.YES:
        return 100.0
    return 0.0


def _score_activate(option: Option, obs: Observation) -> float:
    if option.type == OptionType.YES:
        return 100.0
    return 0.0


def _score_mulligan(option: Option, your: PlayerState) -> float:
    if option.type == OptionType.YES:
        if your.hand:
            has_basic = any(
                get_card(c.id) and get_card(c.id).basic and get_card(c.id).cardType == CardType.POKEMON
                for c in your.hand
            )
            if has_basic:
                return 0.0
        return 100.0
    return 50.0


# ---------------------------------------------------------------------------
# Card selection (discard, to hand, evolve, attach)
# ---------------------------------------------------------------------------

def _score_discard(option: Option, state: State) -> float:
    cid = _resolve_card_id(option, state)
    card_data = get_card(cid) if cid else None
    if card_data is None:
        return 50.0

    your = state.players[state.yourIndex]

    if card_data.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        hand_energy = 0
        if your.hand:
            for c in your.hand:
                cd = get_card(c.id)
                if cd and cd.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
                    hand_energy += 1
        if hand_energy > 2 or state.energyAttached:
            return 90.0
        return 70.0

    if card_data.cardType == CardType.ITEM:
        return 65.0

    if card_data.cardType == CardType.STADIUM:
        return 60.0

    if card_data.cardType == CardType.TOOL:
        return 55.0

    if card_data.cardType == CardType.SUPPORTER:
        if card_data.name and "Boss" in card_data.name:
            return 5.0
        if card_data.name and "Lillie" in card_data.name:
            return 10.0
        return 30.0

    if card_data.cardType == CardType.POKEMON:
        if card_data.ex:
            return 5.0
        if card_data.stage2 or card_data.stage1:
            in_play = _get_in_play_names(your)
            if card_data.evolvesFrom and card_data.evolvesFrom in in_play:
                return 5.0
            return 25.0
        return 40.0

    return 50.0


def _score_to_hand(option: Option, state: State) -> float:
    cid = _resolve_card_id(option, state)
    card_data = get_card(cid) if cid else None
    if card_data is None:
        return 50.0

    your = state.players[state.yourIndex]
    in_play_names = _get_in_play_names(your)
    hand_ids = {c.id for c in your.hand} if your.hand else set()

    if card_data.cardType == CardType.POKEMON:
        if card_data.stage1 or card_data.stage2:
            if card_data.evolvesFrom and card_data.evolvesFrom in in_play_names:
                if card_data.ex:
                    return 150.0
                return 130.0
            if card_data.evolvesFrom and card_data.evolvesFrom not in in_play_names:
                return 40.0

        if card_data.basic:
            has_evolutions = bool(_get_evolution_targets(card_data))
            if has_evolutions and len(your.bench) < your.benchMax:
                return 110.0
            if not has_evolutions and card_data.ex:
                return 100.0
            return 60.0

        if card_data.ex:
            return 100.0
        return 70.0

    if card_data.cardType == CardType.SUPPORTER:
        if not state.supporterPlayed:
            return 120.0
        return 50.0

    if card_data.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        if not state.energyAttached:
            active = _get_active(your)
            if active:
                active_data = get_card(active.id)
                if active_data:
                    for atk_id in active_data.attacks:
                        atk = get_attack(atk_id)
                        if atk and len(active.energies) < len(atk.energies):
                            return 105.0
            return 85.0
        return 30.0

    if card_data.cardType == CardType.ITEM:
        return 75.0
    if card_data.cardType == CardType.TOOL:
        return 65.0
    if card_data.cardType == CardType.STADIUM:
        if not state.stadiumPlayed:
            return 70.0
        return 35.0
    return 50.0


def _get_in_play_names(player: PlayerState) -> set[str]:
    names = set()
    active = _get_active(player)
    if active:
        cd = get_card(active.id)
        if cd:
            names.add(cd.name)
        for pre in active.preEvolution:
            pcd = get_card(pre.id)
            if pcd:
                names.add(pcd.name)
    for bench_poke in player.bench:
        if bench_poke is None:
            continue
        cd = get_card(bench_poke.id)
        if cd:
            names.add(cd.name)
        for pre in bench_poke.preEvolution:
            pcd = get_card(pre.id)
            if pcd:
                names.add(pcd.name)
    return names


def _score_evolve_from(option: Option, your: PlayerState) -> float:
    poke = _pokemon_from_option(option, your)
    if poke is None:
        return 0.0
    if poke.hp <= poke.maxHp * 0.5:
        return 200.0
    return 100.0


def _score_evolve_to(option: Option, state: State = None) -> float:
    cid = _resolve_card_id(option, state) if state else option.cardId
    card_data = get_card(cid) if cid else None
    if card_data is None:
        return 0.0
    score = float(card_data.hp)
    if card_data.ex:
        score += 100.0
    return score


def _score_attach_to(option: Option, your: PlayerState, state: State = None) -> float:
    poke = _pokemon_from_option(option, your)
    if poke is None:
        return 0.0

    card_data = get_card(poke.id)
    if card_data is None:
        return 0.0

    area = option.inPlayArea if option.inPlayArea is not None else option.area
    is_active = area == AreaType.ACTIVE
    is_attacker = card_data.ex or card_data.stage2 or card_data.stage1
    score = 0.0

    if not is_attacker and card_data.basic and card_data.hp <= 70:
        return 10.0

    best_atk_score = 0.0
    for atk_id in card_data.attacks:
        atk = get_attack(atk_id)
        if atk is None:
            continue
        needed = len(atk.energies)
        have = len(poke.energies)
        remaining = needed - have

        if remaining == 1:
            atk_score = 500.0 + atk.damage
            if state:
                opp = state.players[1 - state.yourIndex]
                opp_active = _get_active(opp)
                if opp_active:
                    est = _estimate_damage(atk, your, opp)
                    if est >= opp_active.hp:
                        atk_score += 1000.0
        elif remaining <= 0:
            atk_score = 50.0
        else:
            atk_score = 200.0 / remaining + atk.damage * 0.5

        best_atk_score = max(best_atk_score, atk_score)

    score += best_atk_score

    if is_active:
        score += 150.0
    if is_attacker:
        score += 100.0
    if card_data.ex:
        score += 50.0
    if poke.hp > poke.maxHp * 0.5:
        score += 30.0

    return score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_active(player: PlayerState) -> Pokemon | None:
    if player.active and len(player.active) > 0:
        return player.active[0]
    return None


def _pokemon_at(player: PlayerState, area, index) -> Pokemon | None:
    if area == AreaType.ACTIVE:
        return _get_active(player)
    if area == AreaType.BENCH and index is not None and index < len(player.bench):
        return player.bench[index]
    return None


def _pokemon_from_option(option: Option, your: PlayerState) -> Pokemon | None:
    area = option.inPlayArea if option.inPlayArea is not None else option.area
    index = option.inPlayIndex if option.inPlayIndex is not None else option.index
    if area is None:
        return None
    return _pokemon_at(your, area, index)


def _resolve_card_id(option: Option, state: State) -> int | None:
    """Get the card ID from an option, looking it up from game state if needed."""
    if option.cardId is not None:
        return option.cardId

    if option.area is not None and option.index is not None and option.playerIndex is not None:
        player = state.players[option.playerIndex]
        if option.area == AreaType.HAND and player.hand and option.index < len(player.hand):
            return player.hand[option.index].id
        if option.area == AreaType.DISCARD and option.index < len(player.discard):
            return player.discard[option.index].id
        poke = _pokemon_at(player, option.area, option.index)
        if poke:
            return poke.id
        if option.area == AreaType.PRIZE and option.index < len(player.prize):
            p = player.prize[option.index]
            return p.id if p else None

    if option.area is not None and option.index is not None:
        your = state.players[state.yourIndex]
        if option.area == AreaType.HAND and your.hand and option.index < len(your.hand):
            return your.hand[option.index].id
        poke = _pokemon_at(your, option.area, option.index)
        if poke:
            return poke.id

    return None


def _estimate_damage(atk, your: PlayerState, opp: PlayerState) -> int:
    damage = atk.damage
    opp_active = _get_active(opp)
    if opp_active is None:
        return damage

    your_active = _get_active(your)
    if your_active is None:
        return damage

    your_card = get_card(your_active.id)
    opp_card = get_card(opp_active.id)

    if your_card and opp_card and opp_card.weakness:
        if your_card.energyType == opp_card.weakness:
            damage *= 2

    if your_card and opp_card and opp_card.resistance:
        if your_card.energyType == opp_card.resistance:
            damage -= 30

    return max(damage, 0)
