"""Extract deck lists from daily episode datasets.

Scans episode replays, extracts 60-card decks, and clusters into archetypes.

Usage:
    python analysis/extract_decks.py                    # Use earliest (smallest) dataset
    python analysis/extract_decks.py 2026-06-24         # Use a specific date
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sample_submission"))
from card_db import get_card

ROOT = Path(__file__).parent.parent
OUTPUT = ROOT / "analysis" / "extracted_decks.json"


def get_episodes_path(date: str | None = None) -> Path:
    import kagglehub
    if date is None:
        manifest_path = Path(kagglehub.dataset_download("kaggle/pokemon-tcg-ai-battle-episodes-index"))
        import csv
        with open(manifest_path / "manifest.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        rows.sort(key=lambda r: int(r["total_bytes"]))
        date = rows[0]["date"]
        print(f"Using smallest dataset: {date} ({int(rows[0]['total_bytes'])/1e6:.0f} MB, {rows[0]['episode_count']} episodes)")

    slug = f"kaggle/pokemon-tcg-ai-battle-episodes-{date}"
    return Path(kagglehub.dataset_download(slug))


def extract_deck(episode_path: Path) -> list[dict]:
    with open(episode_path) as f:
        data = json.load(f)

    teams = data.get("info", {}).get("TeamNames", ["P0", "P1"])
    rewards = data.get("rewards", [0, 0])
    steps = data.get("steps", [])
    if len(steps) < 2:
        return []

    results = []
    for pi in range(2):
        action = steps[1][pi].get("action", [])
        if not isinstance(action, list) or len(action) != 60:
            continue

        deck_key = tuple(sorted(action))
        counts = Counter(action)

        results.append({
            "team": teams[pi] if pi < len(teams) else f"P{pi}",
            "won": rewards[pi] == 1 if pi < len(rewards) else False,
            "deck": action,
            "deck_key": deck_key,
            "card_counts": dict(counts.most_common()),
        })

    return results


def classify_archetype(card_counts: dict[int, int]) -> str:
    ids = set(card_counts.keys())

    signatures = {
        "dragapult_ex": {119, 120, 121},
        "mega_abomasnow": {722, 723},
        "mega_lucario": {1158},
        "hops_trevenant": {724, 725},
        "alakazam": {126, 127, 128},
        "mega_starmie": {77, 78},
        "ionos_bellibolt": {246, 247},
        "genesect": {219},
    }

    for archetype, sig in signatures.items():
        if sig & ids:
            return archetype

    for cid in ids:
        cd = get_card(cid)
        if cd and cd.ex and cd.cardType == 0:
            return cd.name.lower().replace(" ", "_").replace("'", "")

    return "unknown"


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    path = get_episodes_path(date)

    episode_files = list(path.glob("*.json"))
    print(f"Scanning {len(episode_files)} episodes...")

    unique_decks: dict[tuple, dict] = {}
    deck_wins: dict[tuple, int] = Counter()
    deck_games: dict[tuple, int] = Counter()

    for i, ep_file in enumerate(episode_files):
        if i % 200 == 0 and i > 0:
            print(f"  ...{i}/{len(episode_files)}")
        try:
            entries = extract_deck(ep_file)
        except Exception:
            continue
        for entry in entries:
            key = entry["deck_key"]
            deck_games[key] += 1
            if entry["won"]:
                deck_wins[key] += 1
            if key not in unique_decks:
                unique_decks[key] = entry

    print(f"\nFound {len(unique_decks)} unique decks across {sum(deck_games.values())} deck-games")

    archetypes: dict[str, list] = {}
    for key, entry in unique_decks.items():
        arch = classify_archetype(entry["card_counts"])
        games = deck_games[key]
        wins = deck_wins[key]
        entry["archetype"] = arch
        entry["games"] = games
        entry["wins"] = wins
        entry["win_rate"] = wins / games if games > 0 else 0
        del entry["deck_key"]

        if arch not in archetypes:
            archetypes[arch] = []
        archetypes[arch].append(entry)

    print("\nArchetype breakdown:")
    print(f"  {'Archetype':<25s} {'Decks':>5s} {'Games':>6s} {'WinRate':>7s}")
    print("  " + "-" * 45)
    for arch in sorted(archetypes, key=lambda a: -sum(e["games"] for e in archetypes[a])):
        entries = archetypes[arch]
        total_games = sum(e["games"] for e in entries)
        total_wins = sum(e["wins"] for e in entries)
        wr = total_wins / total_games if total_games > 0 else 0
        print(f"  {arch:<25s} {len(entries):5d} {total_games:6d} {wr:6.1%}")

    output_data = list(unique_decks.values())
    for d in output_data:
        d["card_counts"] = {str(k): v for k, v in d["card_counts"].items()}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(output_data)} decks to {OUTPUT}")

    best_decks = sorted(output_data, key=lambda d: (-d["win_rate"], -d["games"]))
    print("\nTop 10 decks by win rate (min 3 games):")
    shown = 0
    for d in best_decks:
        if d["games"] < 3:
            continue
        team = d["team"].encode("ascii", "replace").decode()
        print(f"  {d['archetype']:<25s} {d['win_rate']:.1%} ({d['wins']}/{d['games']}) - {team}")
        shown += 1
        if shown >= 10:
            break


if __name__ == "__main__":
    main()
