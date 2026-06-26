"""Generate detailed per-game summaries from all replays of a submission."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sample_submission"))
from cg.api import LogType, AreaType
from card_db import get_card, get_attack

REPLAYS_DIR = os.path.join(os.path.dirname(__file__), "..", "replays")
EPISODES = [
    "82073046", "82068844", "82068394", "82064620", "82063675",
    "82052353", "82048455", "82045165", "82044703", "82044236",
    "82043745", "82043272", "82042615", "82041947", "82041483",
    "82041119", "82040971", "82040493", "82039988",
]


def analyze_game(filepath):
    with open(filepath) as f:
        data = json.load(f)

    teams = data["info"].get("TeamNames", ["P0", "P1"])
    rewards = data.get("rewards", [0, 0])
    steps = data.get("steps", [])

    our_idx = next((i for i, t in enumerate(teams) if "Adi" in t), 0)
    opp_idx = 1 - our_idx
    result = "WIN" if rewards[our_idx] == 1 else "LOSS" if rewards[our_idx] == -1 else "DRAW"

    # Extract decks
    our_deck = steps[1][our_idx]["action"] if len(steps) > 1 else []
    opp_deck = steps[1][opp_idx]["action"] if len(steps) > 1 else []
    opp_counts = Counter(opp_deck)
    opp_pokemon = []
    for cid, n in opp_counts.most_common():
        cd = get_card(cid)
        if cd and cd.cardType == 0:
            opp_pokemon.append(f"{n}x {cd.name}")
    opp_top = []
    for cid, n in opp_counts.most_common(3):
        cd = get_card(cid)
        opp_top.append(f"{n}x {cd.name if cd else cid}")

    # Walk through all steps collecting events
    kos_scored = {0: 0, 1: 0}
    prizes_taken = {0: 6, 1: 6}
    attacks = {0: [], 1: []}
    total_damage_dealt = {0: 0, 1: 0}
    total_damage_taken = {0: 0, 1: 0}
    cards_played = {0: [], 1: []}
    evolutions = {0: [], 1: []}
    final_turn = 0
    win_reason = ""
    energy_attached_to = {0: Counter(), 1: Counter()}
    retreats = {0: 0, 1: 0}

    for step_num, step in enumerate(steps):
        for pi in range(2):
            obs = step[pi]["observation"]
            logs = obs.get("logs", [])
            cur = obs.get("current")

            if cur:
                final_turn = max(final_turn, cur.get("turn", 0))
                for ji, p in enumerate(cur["players"]):
                    prizes_taken[ji] = len(p.get("prize", []))

            for log in logs:
                lt = log.get("type")
                lpi = log.get("playerIndex")

                if lt == LogType.ATTACK:
                    atk = get_attack(log.get("attackId"))
                    cd = get_card(log.get("cardId"))
                    if lpi is not None and atk:
                        attacks[lpi].append(atk.name)

                elif lt == LogType.HP_CHANGE:
                    val = log.get("value", 0)
                    if val < 0 and lpi is not None:
                        attacker = 1 - lpi
                        total_damage_dealt[attacker] += abs(val)
                        total_damage_taken[lpi] += abs(val)

                elif lt == LogType.PLAY:
                    cd = get_card(log.get("cardId"))
                    if lpi is not None and cd:
                        cards_played[lpi].append(cd.name)

                elif lt == LogType.EVOLVE:
                    cd = get_card(log.get("cardId"))
                    cd_t = get_card(log.get("cardIdTarget"))
                    if lpi is not None and cd and cd_t:
                        evolutions[lpi].append(f"{cd_t.name} -> {cd.name}")

                elif lt == LogType.ATTACH:
                    cd = get_card(log.get("cardId"))
                    cd_t = get_card(log.get("cardIdTarget"))
                    if lpi is not None and cd and cd_t:
                        energy_attached_to[lpi][cd_t.name] += 1

                elif lt == LogType.SWITCH:
                    if lpi is not None:
                        retreats[lpi] += 1

                elif lt == LogType.RESULT:
                    r = log.get("result")
                    reason = log.get("reason")
                    reasons = {1: "0 prizes", 2: "0 deck cards", 3: "no active Pokemon", 4: "card effect"}
                    win_reason = reasons.get(reason, f"reason {reason}")

    # Final board state
    last_step = steps[-1]
    final_boards = {}
    for pi in range(2):
        cur = last_step[pi]["observation"].get("current")
        if cur:
            p = cur["players"][pi]
            active = "(none)"
            if p["active"] and p["active"][0]:
                a = p["active"][0]
                cd = get_card(a["id"])
                active = f"{cd.name if cd else '?'} {a['hp']}/{a['maxHp']}HP"
            bench_count = len([b for b in p.get("bench", []) if b])
            final_boards[pi] = {
                "active": active,
                "bench": bench_count,
                "hand": p["handCount"],
                "deck": p["deckCount"],
                "prizes": len(p.get("prize", [])),
            }

    our_board = final_boards.get(our_idx, {})
    opp_board = final_boards.get(opp_idx, {})

    our_attacks = Counter(attacks[our_idx])
    opp_attacks = Counter(attacks[opp_idx])
    our_evos = evolutions[our_idx]
    our_energy = energy_attached_to[our_idx]

    return {
        "episode": os.path.basename(filepath).replace("episode-", "").replace("-replay.json", ""),
        "result": result,
        "opponent": teams[opp_idx],
        "opp_deck_summary": ", ".join(opp_top),
        "opp_pokemon": opp_pokemon,
        "turns": final_turn,
        "steps": len(steps),
        "win_reason": win_reason,
        "our_damage_dealt": total_damage_dealt[our_idx],
        "our_damage_taken": total_damage_taken[our_idx],
        "opp_damage_dealt": total_damage_dealt[opp_idx],
        "our_prizes_remaining": our_board.get("prizes", "?"),
        "opp_prizes_remaining": opp_board.get("prizes", "?"),
        "our_final_active": our_board.get("active", "?"),
        "our_final_bench": our_board.get("bench", "?"),
        "our_final_deck": our_board.get("deck", "?"),
        "opp_final_active": opp_board.get("active", "?"),
        "opp_final_bench": opp_board.get("bench", "?"),
        "our_attacks": our_attacks.most_common(5),
        "opp_attacks": opp_attacks.most_common(5),
        "our_evolutions": our_evos,
        "our_energy_targets": our_energy.most_common(5),
        "our_cards_played": Counter(cards_played[our_idx]).most_common(5),
        "our_retreats": retreats[our_idx],
    }


def main():
    results = []
    for ep_id in EPISODES:
        path = os.path.join(REPLAYS_DIR, f"episode-{ep_id}-replay.json")
        if not os.path.exists(path):
            continue
        try:
            r = analyze_game(path)
            results.append(r)
        except Exception as e:
            print(f"Error analyzing {ep_id}: {e}")

    wins = sum(1 for r in results if r["result"] == "WIN")
    losses = sum(1 for r in results if r["result"] == "LOSS")
    draws = sum(1 for r in results if r["result"] == "DRAW")
    print(f"OVERALL: {wins}W {losses}L {draws}D ({len(results)} games)\n")

    for r in results:
        marker = "WIN " if r["result"] == "WIN" else "LOSS" if r["result"] == "LOSS" else "DRAW"
        print(f"{'='*70}")
        print(f"[{marker}] Episode {r['episode']} vs {r['opponent']}")
        print(f"  Opp deck: {r['opp_deck_summary']}")
        print(f"  Opp Pokemon: {', '.join(r['opp_pokemon'][:5])}")
        print(f"  Turns: {r['turns']} | Steps: {r['steps']} | Reason: {r['win_reason']}")
        print(f"  Damage: us {r['our_damage_dealt']} dealt / {r['our_damage_taken']} taken | opp {r['opp_damage_dealt']} dealt")
        print(f"  Prizes remaining: us {r['our_prizes_remaining']} | opp {r['opp_prizes_remaining']}")
        print(f"  Final board:")
        print(f"    US:  {r['our_final_active']} | bench:{r['our_final_bench']} | deck:{r['our_final_deck']}")
        print(f"    OPP: {r['opp_final_active']} | bench:{r['opp_final_bench']}")
        if r['our_attacks']:
            atks = ", ".join(f"{name}x{n}" for name, n in r['our_attacks'])
            print(f"  Our attacks: {atks}")
        if r['opp_attacks']:
            atks = ", ".join(f"{name}x{n}" for name, n in r['opp_attacks'])
            print(f"  Opp attacks: {atks}")
        if r['our_evolutions']:
            print(f"  Our evolutions: {', '.join(r['our_evolutions'][:5])}")
        if r['our_energy_targets']:
            tgts = ", ".join(f"{name}x{n}" for name, n in r['our_energy_targets'])
            print(f"  Energy attached to: {tgts}")
        if r['our_cards_played']:
            played = ", ".join(f"{name}x{n}" for name, n in r['our_cards_played'])
            print(f"  Cards played: {played}")
        print()

    # Loss analysis
    loss_archetypes = Counter()
    for r in results:
        if r["result"] == "LOSS":
            for p in r["opp_pokemon"]:
                loss_archetypes[p] += 1

    if loss_archetypes:
        print(f"{'='*70}")
        print("LOSS BREAKDOWN - Opponent Pokemon we lose to:")
        for p, n in loss_archetypes.most_common(10):
            print(f"  {p}: {n} losses")


if __name__ == "__main__":
    main()
