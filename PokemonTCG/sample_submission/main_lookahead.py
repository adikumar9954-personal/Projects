import os
import random

from cg.api import Observation, to_observation_class, SelectContext
from heuristics import score_option
from lookahead import lookahead_main_scores
from card_tracker import set_deck

def read_deck_csv() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    deck = []
    for i in range(60):
        deck.append(int(csv[i]))
    return deck

_deck_loaded = False

def agent(obs_dict: dict) -> list[int]:
    global _deck_loaded
    obs: Observation = to_observation_class(obs_dict)

    if obs.select is None:
        deck = read_deck_csv()
        set_deck(deck)
        _deck_loaded = True
        return deck

    if not _deck_loaded:
        set_deck(read_deck_csv())
        _deck_loaded = True

    options = obs.select.option
    count = obs.select.maxCount

    scored = None
    if obs.select.context == SelectContext.MAIN:
        scored = lookahead_main_scores(obs)

    if scored is None:
        scored = []
        for i, opt in enumerate(options):
            try:
                s = score_option(opt, obs)
            except Exception:
                s = 0.0
            scored.append((i, s))

    scored.sort(key=lambda x: (-x[1], random.random()))
    return [i for i, _ in scored[:count]]
