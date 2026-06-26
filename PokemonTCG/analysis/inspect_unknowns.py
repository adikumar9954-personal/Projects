import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sample_submission"))
from card_db import get_card

with open(os.path.join(os.path.dirname(__file__), "extracted_decks.json"), encoding="utf-8") as f:
    decks = json.load(f)

unknowns = [d for d in decks if d["archetype"] == "unknown"]
unknowns.sort(key=lambda d: (-d.get("win_rate", 0), -d.get("games", 0)))

for d in unknowns[:5]:
    team = d["team"]
    games = d.get("games", 0)
    wr = d.get("win_rate", 0)
    print(f"{team} - {games} games, {wr:.0%} WR")
    counts = {int(k): v for k, v in d["card_counts"].items()}
    for cid, n in sorted(counts.items(), key=lambda x: -x[1]):
        cd = get_card(cid)
        name = cd.name if cd else f"#{cid}"
        print(f"  {n}x {name} (#{cid})")
    print()
