"""Run test battles to compare agents.

Usage:
    python test_battle.py                          # heuristic vs random, 10 games
    python test_battle.py 50                       # heuristic vs random, 50 games
    python test_battle.py 50 random random         # random vs random, 50 games
    python test_battle.py 20 heuristic heuristic   # heuristic vs heuristic, 20 games

Available agents: random, heuristic
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sample_submission"))

ROOT = os.path.dirname(__file__)

from cg.api import Observation, to_observation_class
from cg.game import battle_start, battle_select, battle_finish
from heuristics import score_option
from dragapult_strategy import adjust_score
from lookahead import lookahead_main_scores
from mcts import mcts_search
from card_tracker import set_deck
from cg.api import SelectContext


def read_deck() -> list[int]:
    with open(os.path.join(ROOT, "sample_submission", "deck.csv")) as f:
        return [int(line.strip()) for line in f if line.strip()]


_deck_initialized = False

def _ensure_deck():
    global _deck_initialized
    if not _deck_initialized:
        set_deck(read_deck())
        _deck_initialized = True


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

def random_agent(obs: Observation) -> list[int]:
    return random.sample(range(len(obs.select.option)), obs.select.maxCount)


def heuristic_agent(obs: Observation) -> list[int]:
    scored = []
    for i, opt in enumerate(obs.select.option):
        try:
            s = score_option(opt, obs)
            s = adjust_score(opt, obs, s)
        except Exception:
            s = 0.0
        scored.append((i, s))
    scored.sort(key=lambda x: (-x[1], random.random()))
    return [i for i, _ in scored[:obs.select.maxCount]]


def lookahead_agent(obs: Observation) -> list[int]:
    _ensure_deck()
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


def mcts_agent(obs: Observation) -> list[int]:
    _ensure_deck()
    scored = None
    if obs.select.context == SelectContext.MAIN:
        scored = mcts_search(obs)
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


AGENTS = {
    "random": random_agent,
    "heuristic": heuristic_agent,
    "lookahead": lookahead_agent,
    "mcts": mcts_agent,
}


# ---------------------------------------------------------------------------
# Battle runner
# ---------------------------------------------------------------------------

def run_game(agents: dict[int, callable], deck: list[int]) -> int:
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


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    p0_name = sys.argv[2] if len(sys.argv) > 2 else "heuristic"
    p1_name = sys.argv[3] if len(sys.argv) > 3 else "random"

    if p0_name not in AGENTS:
        print(f"Unknown agent '{p0_name}'. Available: {', '.join(AGENTS)}")
        return
    if p1_name not in AGENTS:
        print(f"Unknown agent '{p1_name}'. Available: {', '.join(AGENTS)}")
        return

    agents = {0: AGENTS[p0_name], 1: AGENTS[p1_name]}
    deck = read_deck()

    print(f"{p0_name} (P0) vs {p1_name} (P1) — {n_games} games\n")

    wins = {0: 0, 1: 0, 2: 0}
    for i in range(n_games):
        result = run_game(agents, deck)
        wins[result] = wins.get(result, 0) + 1
        markers = {0: p0_name[0].upper(), 1: p1_name[0].upper(), 2: "D"}
        print(f"  Game {i+1}/{n_games}: {markers.get(result, '?')}")

    print(f"\nResults over {n_games} games:")
    print(f"  {p0_name:12s} (P0): {wins[0]} wins ({100*wins[0]/n_games:.0f}%)")
    print(f"  {p1_name:12s} (P1): {wins[1]} wins ({100*wins[1]/n_games:.0f}%)")
    print(f"  {'Draws':12s}     : {wins[2]} ({100*wins[2]/n_games:.0f}%)")


if __name__ == "__main__":
    main()
