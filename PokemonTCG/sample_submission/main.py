import os
import random

from cg.api import Observation, to_observation_class
from heuristics import score_option
from dragapult_strategy import adjust_score

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

def agent(obs_dict: dict) -> list[int]:
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    options = obs.select.option
    count = obs.select.maxCount

    scored = []
    for i, opt in enumerate(options):
        try:
            s = score_option(opt, obs)
            s = adjust_score(opt, obs, s)
        except Exception:
            s = 0.0
        scored.append((i, s))

    scored.sort(key=lambda x: (-x[1], random.random()))
    return [i for i, _ in scored[:count]]
