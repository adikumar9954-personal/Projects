import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sample_submission"))
from card_db import get_card
from collections import Counter

replays_dir = os.path.join(os.path.dirname(__file__), "..", "replays")
for f in sorted(os.listdir(replays_dir)):
    if not f.startswith("episode-8204"):
        continue
    with open(os.path.join(replays_dir, f)) as fh:
        data = json.load(fh)
    teams = data["info"].get("TeamNames", ["P0", "P1"])
    rewards = data.get("rewards", [0, 0])
    our_idx = next((i for i, t in enumerate(teams) if "Adi" in t), 0)
    result = "WIN" if rewards[our_idx] == 1 else "LOSS" if rewards[our_idx] == -1 else "DRAW"
    opp = teams[1 - our_idx]
    opp_deck = data["steps"][1][1 - our_idx]["action"]
    opp_counts = Counter(opp_deck)
    top_cards = []
    for cid, n in opp_counts.most_common(3):
        cd = get_card(cid)
        top_cards.append(f"{n}x {cd.name if cd else cid}")
    print(f"{f}: {result} vs {opp} [{', '.join(top_cards)}]")
