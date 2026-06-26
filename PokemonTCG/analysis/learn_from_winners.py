"""Extract winning players' decisions and compare against our heuristic.

Finds where our heuristic disagrees with winners' actual choices
to identify weaknesses in our scoring.

Usage:
    python analysis/learn_from_winners.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sample_submission"))

from cg.api import (
    Observation, to_observation_class, SelectContext, SelectType,
    OptionType, AreaType,
)
from heuristics import score_option
from card_db import get_card

EPISODES_PATH = "C:/Users/adiku/.cache/kagglehub/datasets/kaggle/pokemon-tcg-ai-battle-episodes-2026-06-16/versions/1"


def analyze_episode(filepath: str) -> list[dict]:
    with open(filepath) as f:
        data = json.load(f)

    rewards = data.get("rewards", [0, 0])
    winner = None
    for pi in range(2):
        if pi < len(rewards) and rewards[pi] == 1:
            winner = pi
            break
    if winner is None:
        return []

    teams = data["info"].get("TeamNames", ["P0", "P1"])
    disagreements = []

    for step_num, step in enumerate(data["steps"]):
        if step_num < 2:
            continue

        player_data = step[winner]
        obs_dict = player_data["observation"]
        action = player_data["action"]

        if not isinstance(action, list) or len(action) == 0:
            continue

        cur = obs_dict.get("current")
        sel = obs_dict.get("select")
        if cur is None or sel is None:
            continue
        if cur.get("yourIndex") != winner:
            continue

        try:
            obs = to_observation_class(obs_dict)
        except Exception:
            continue

        if obs.select is None or obs.current is None:
            continue

        options = obs.select.option
        if len(options) <= 1:
            continue

        scored = []
        for i, opt in enumerate(options):
            try:
                s = score_option(opt, obs)
            except Exception:
                s = 0.0
            scored.append((i, s))

        scored.sort(key=lambda x: -x[1])
        our_best = scored[0][0]
        their_pick = action[0] if len(action) >= 1 else -1

        if their_pick < 0 or their_pick >= len(options):
            continue

        if our_best != their_pick:
            our_score = next(s for i, s in scored if i == our_best)
            their_score = next(s for i, s in scored if i == their_pick)

            ctx = SelectContext(obs.select.context).name
            our_type = OptionType(options[our_best].type).name
            their_type = OptionType(options[their_pick].type).name

            disagreements.append({
                "context": ctx,
                "our_pick": our_type,
                "our_score": our_score,
                "their_pick": their_type,
                "their_score": their_score,
                "score_gap": our_score - their_score,
                "n_options": len(options),
                "team": teams[winner],
                "step": step_num,
            })

    return disagreements


def main():
    files = sorted(os.listdir(EPISODES_PATH))
    print(f"Analyzing {len(files)} episodes...")

    all_disagreements = []
    total_decisions = 0
    episodes_analyzed = 0

    for i, fname in enumerate(files):
        if i % 200 == 0 and i > 0:
            print(f"  ...{i}/{len(files)}")
        filepath = os.path.join(EPISODES_PATH, fname)
        try:
            disags = analyze_episode(filepath)
        except Exception:
            continue
        all_disagreements.extend(disags)
        episodes_analyzed += 1

    print(f"\nAnalyzed {episodes_analyzed} episodes")
    print(f"Total disagreements: {len(all_disagreements)}")

    # Group by context
    by_context = defaultdict(list)
    for d in all_disagreements:
        by_context[d["context"]].append(d)

    print(f"\nDisagreements by context:")
    print(f"  {'Context':<30s} {'Count':>6s} {'Avg Gap':>8s}")
    print("  " + "-" * 46)
    for ctx in sorted(by_context, key=lambda c: -len(by_context[c])):
        entries = by_context[ctx]
        avg_gap = sum(d["score_gap"] for d in entries) / len(entries)
        print(f"  {ctx:<30s} {len(entries):6d} {avg_gap:8.1f}")

    # For MAIN context, show what winners prefer vs what we prefer
    main_disags = by_context.get("MAIN", [])
    if main_disags:
        print(f"\nMAIN phase: What winners pick vs what we pick:")
        our_picks = Counter(d["our_pick"] for d in main_disags)
        their_picks = Counter(d["their_pick"] for d in main_disags)
        all_types = set(our_picks.keys()) | set(their_picks.keys())
        print(f"  {'Action':<15s} {'We pick':>8s} {'They pick':>10s} {'Delta':>7s}")
        print("  " + "-" * 42)
        for t in sorted(all_types, key=lambda x: -(their_picks.get(x, 0) - our_picks.get(x, 0))):
            ours = our_picks.get(t, 0)
            theirs = their_picks.get(t, 0)
            print(f"  {t:<15s} {ours:8d} {theirs:10d} {theirs-ours:+7d}")

    # Show biggest disagreements (where score gap is large but winner chose differently)
    big_disags = [d for d in all_disagreements if d["context"] == "MAIN" and d["score_gap"] > 100]
    big_disags.sort(key=lambda d: -d["score_gap"])
    if big_disags:
        print(f"\nLargest MAIN disagreements (our score >> winner's pick):")
        for d in big_disags[:15]:
            team = d["team"][:20]
            print(
                f"  We: {d['our_pick']:<12s} ({d['our_score']:7.0f}) vs "
                f"Winner: {d['their_pick']:<12s} ({d['their_score']:7.0f}) "
                f"gap={d['score_gap']:.0f} [{team}]"
            )

    # Save for further analysis
    output = os.path.join(os.path.dirname(__file__), "disagreements.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_disagreements, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(all_disagreements)} disagreements to {output}")


if __name__ == "__main__":
    main()
