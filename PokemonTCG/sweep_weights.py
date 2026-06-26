"""Sweep lookahead delta weights to find optimal balance.

Tests different weight values for: heuristic_score + delta * weight
Runs each weight against the pure heuristic agent.
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sample_submission"))

from cg.api import Observation, to_observation_class, SelectContext
from cg.game import battle_start, battle_select, battle_finish
from heuristics import score_option
from lookahead import lookahead_main_scores, evaluate_state
from card_tracker import set_deck
import lookahead as la_module

ROOT = os.path.dirname(__file__)

def read_deck() -> list[int]:
    with open(os.path.join(ROOT, "sample_submission", "deck.csv")) as f:
        return [int(line.strip()) for line in f if line.strip()]

def heuristic_agent(obs: Observation) -> list[int]:
    scored = []
    for i, opt in enumerate(obs.select.option):
        try:
            s = score_option(opt, obs)
        except Exception:
            s = 0.0
        scored.append((i, s))
    scored.sort(key=lambda x: (-x[1], random.random()))
    return [i for i, _ in scored[:obs.select.maxCount]]

def make_lookahead_agent(weight: float):
    def agent(obs: Observation) -> list[int]:
        scored = None
        if obs.select.context == SelectContext.MAIN:
            scored = lookahead_main_scores(obs)
        if scored is None:
            scored = []
            for i, opt in enumerate(obs.select.option):
                try:
                    s = score_option(opt, obs)
                except Exception:
                    s = 0.0
                scored.append((i, s))
        scored.sort(key=lambda x: (-x[1], random.random()))
        return [i for i, _ in scored[:obs.select.maxCount]]
    return agent

def run_game(agents, deck):
    obs_dict, start_data = battle_start(deck, deck)
    if obs_dict is None:
        return -1
    step = 0
    while True:
        obs = to_observation_class(obs_dict)
        if obs.current and obs.current.result >= 0:
            battle_finish()
            return obs.current.result
        if obs.select is None:
            obs_dict = battle_select(deck)
            continue
        player = obs.current.yourIndex
        action = agents[player](obs)
        obs_dict = battle_select(action)
        step += 1
        if step > 2000:
            battle_finish()
            return 2

def patch_weight(weight: float):
    """Monkey-patch the lookahead module to use a specific delta weight."""
    original_fn = la_module.lookahead_main_scores.__code__

    # We'll modify the module-level function by replacing it
    import cg.api as api_module
    from card_tracker import predict_hidden_cards

    def patched_lookahead(obs):
        if obs.select is None or obs.current is None:
            return None
        if obs.select.context != SelectContext.MAIN:
            return None
        if obs.search_begin_input is None:
            return None

        options = obs.select.option
        if len(options) <= 1:
            return None

        from cg.api import OptionType, search_begin, search_step, search_end, search_release

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
                results.append((i, score_option(opt, obs) + (0 - 50.0) * weight))
                continue
            try:
                next_state = search_step(root.searchId, [i])
                future_score = evaluate_state(next_state.observation)
                search_release(next_state.searchId)
                heuristic_score = score_option(opt, obs)
                delta = future_score - base_score
                combined = heuristic_score + delta * weight
                results.append((i, combined))
            except (ValueError, RuntimeError):
                heuristic_score = score_option(opt, obs)
                results.append((i, heuristic_score))

        try:
            search_end()
        except Exception:
            pass

        return results

    la_module.lookahead_main_scores = patched_lookahead


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    weights = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]

    if len(sys.argv) > 2:
        weights = [float(w) for w in sys.argv[2].split(",")]

    deck = read_deck()
    set_deck(deck)

    print(f"Sweeping {len(weights)} weights, {n_games} games each vs heuristic")
    print(f"{'Weight':>8s}  {'Wins':>4s}  {'Losses':>6s}  {'Draws':>5s}  {'Win%':>5s}")
    print("-" * 40)

    for w in weights:
        patch_weight(w)
        la_agent = make_lookahead_agent(w)
        agents = {0: la_agent, 1: heuristic_agent}

        wins = {0: 0, 1: 0, 2: 0}
        for i in range(n_games):
            result = run_game(agents, deck)
            wins[result] = wins.get(result, 0) + 1

        wr = 100 * wins[0] / n_games
        print(f"{w:8.2f}  {wins[0]:4d}  {wins[1]:6d}  {wins[2]:5d}  {wr:5.1f}%")

if __name__ == "__main__":
    main()
