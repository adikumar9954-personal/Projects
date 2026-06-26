"""One-step lookahead using the SDK search API.

For MAIN phase decisions, simulates each option one step ahead
to evaluate the resulting board state. Falls back to heuristics
if search fails or for non-MAIN decisions.
"""
import random
from cg.api import (
    Observation, SearchState, SelectContext, SelectType, OptionType,
    search_begin, search_step, search_end, search_release,
)
from card_tracker import predict_hidden_cards
from heuristics import score_option, _get_active, _estimate_damage
from card_db import get_card, get_attack


def evaluate_state(obs: Observation) -> float:
    """Score a board state from our perspective. Higher = better for us."""
    state = obs.current
    if state is None:
        return 0.0

    if state.result >= 0:
        if state.result == state.yourIndex:
            return 100000.0
        elif state.result == 2:
            return 0.0
        else:
            return -100000.0

    your = state.players[state.yourIndex]
    opp = state.players[1 - state.yourIndex]
    score = 0.0

    our_prizes = len(your.prize)
    opp_prizes = len(opp.prize)
    score += (opp_prizes - our_prizes) * 500.0

    our_active = _get_active(your)
    opp_active = _get_active(opp)

    if our_active:
        score += our_active.hp * 2.0
        score += len(our_active.energies) * 80.0
        card_data = get_card(our_active.id)
        if card_data and card_data.ex:
            score += 100.0
        if card_data:
            for atk_id in card_data.attacks:
                atk = get_attack(atk_id)
                if atk and len(our_active.energies) >= len(atk.energies):
                    score += 150.0 + atk.damage
                    break

    if opp_active:
        score -= opp_active.hp * 1.5
        score -= len(opp_active.energies) * 60.0

    score += len(your.bench) * 30.0
    score -= len(opp.bench) * 20.0

    for p in your.bench:
        if p:
            score += len(p.energies) * 40.0

    if our_active is None:
        score -= 500.0
    if opp_active is None:
        score += 300.0

    score += your.deckCount * 2.0
    score -= (6 - our_prizes) * 100.0

    return score


def lookahead_main_scores(obs: Observation) -> list[tuple[int, float]] | None:
    """Try one-step lookahead for MAIN phase options.

    Returns list of (option_index, score) or None if search fails.
    """
    if obs.select is None or obs.current is None:
        return None
    if obs.select.context != SelectContext.MAIN:
        return None
    if obs.search_begin_input is None:
        return None

    options = obs.select.option
    if len(options) <= 1:
        return None

    try:
        predictions = predict_hidden_cards(obs)
        root = search_begin(
            obs,
            predictions["your_deck"],
            predictions["your_prize"],
            predictions["opp_deck"],
            predictions["opp_prize"],
            predictions["opp_hand"],
            predictions["opp_active"],
        )
    except (ValueError, RuntimeError):
        return None

    base_score = evaluate_state(root.observation)
    results = []

    for i, opt in enumerate(options):
        if opt.type == OptionType.END:
            results.append((i, base_score - 50.0))
            continue

        try:
            next_state = search_step(root.searchId, [i])
            future_score = evaluate_state(next_state.observation)
            search_release(next_state.searchId)

            heuristic_score = score_option(opt, obs)
            delta = future_score - base_score
            combined = heuristic_score + delta * 0.3

            results.append((i, combined))
        except (ValueError, RuntimeError):
            heuristic_score = score_option(opt, obs)
            results.append((i, heuristic_score))

    try:
        search_end()
    except Exception:
        pass

    return results
