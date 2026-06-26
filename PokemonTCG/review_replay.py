"""Review a Kaggle episode replay to understand agent decisions.

Usage:
    python review_replay.py <episode_id>                    # Fetch + review
    python review_replay.py replays/episode-XXX-replay.json # Review local file
    python review_replay.py <episode_id> --losses-only      # Only show turns where we lost material
    python review_replay.py <episode_id> --verbose          # Show all options, not just top/bottom
"""
import json
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sample_submission"))

from cg.api import (
    Observation, to_observation_class, OptionType, SelectContext,
    AreaType, CardType, LogType,
)
from card_db import get_card, get_attack

REPLAYS_DIR = os.path.join(os.path.dirname(__file__), "replays")
COMPETITION = "pokemon-tcg-ai-battle"


def fetch_replay(episode_id: str) -> str:
    os.makedirs(REPLAYS_DIR, exist_ok=True)
    path = os.path.join(REPLAYS_DIR, f"episode-{episode_id}-replay.json")
    if os.path.exists(path):
        print(f"Using cached replay: {path}")
        return path
    print(f"Downloading replay {episode_id}...")
    venv_kaggle = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "kaggle.exe")
    subprocess.run([venv_kaggle, "competitions", "replay", episode_id, "-p", REPLAYS_DIR], check=True)
    return path


def load_replay(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def find_our_index(data: dict) -> int:
    teams = data["info"].get("TeamNames", [])
    for i, name in enumerate(teams):
        if "Adi Kumar" in name:
            return i
    return 0


def format_poke(poke_dict: dict | None) -> str:
    if poke_dict is None:
        return "(face-down)"
    cd = get_card(poke_dict["id"])
    name = cd.name if cd else f"#{poke_dict['id']}"
    energies = len(poke_dict.get("energies", []))
    return f"{name} {poke_dict['hp']}/{poke_dict['maxHp']}HP {energies}E"


def format_board(cur: dict, our_idx: int) -> str:
    lines = []
    for pi in range(2):
        label = "US " if pi == our_idx else "OPP"
        p = cur["players"][pi]
        active_str = "(none)"
        if p["active"] and p["active"][0]:
            active_str = format_poke(p["active"][0])
        bench_strs = [format_poke(b) for b in p.get("bench", []) if b]
        status = []
        if p.get("poisoned"):
            status.append("PSN")
        if p.get("burned"):
            status.append("BRN")
        if p.get("asleep"):
            status.append("SLP")
        if p.get("paralyzed"):
            status.append("PAR")
        if p.get("confused"):
            status.append("CNF")
        status_str = f" [{','.join(status)}]" if status else ""
        lines.append(
            f"  {label}: {active_str}{status_str} | "
            f"Bench({len(bench_strs)}): {', '.join(bench_strs) or 'empty'} | "
            f"Hand:{p['handCount']} Deck:{p['deckCount']} Prizes:{len(p['prize'])}"
        )
    return "\n".join(lines)


def describe_option(opt: dict, cur: dict) -> str:
    otype = opt["type"]

    if otype == OptionType.END:
        return "End turn"
    if otype == OptionType.RETREAT:
        return "Retreat"
    if otype == OptionType.YES:
        return "Yes"
    if otype == OptionType.NO:
        return "No"

    if otype == OptionType.ATTACK:
        atk = get_attack(opt.get("attackId"))
        if atk:
            return f"Attack: {atk.name} ({atk.damage}dmg)"
        return f"Attack #{opt.get('attackId')}"

    if otype == OptionType.PLAY:
        idx = opt.get("index")
        your_idx = cur.get("yourIndex", 0)
        hand = cur["players"][your_idx].get("hand")
        if hand and idx is not None and idx < len(hand) and hand[idx]:
            cd = get_card(hand[idx]["id"])
            if cd:
                return f"Play: {cd.name}"
        return "Play card"

    if otype == OptionType.EVOLVE:
        cd = get_card(opt.get("cardId")) if opt.get("cardId") else None
        return f"Evolve: {cd.name if cd else '?'}"

    if otype == OptionType.ATTACH:
        src = "?"
        area = opt.get("area")
        idx = opt.get("index")
        your_idx = cur.get("yourIndex", 0)
        if area == AreaType.HAND:
            hand = cur["players"][your_idx].get("hand")
            if hand and idx is not None and idx < len(hand) and hand[idx]:
                cd = get_card(hand[idx]["id"])
                src = cd.name if cd else f"hand[{idx}]"
        dst_area = opt.get("inPlayArea")
        dst_idx = opt.get("inPlayIndex")
        dst = f"{AreaType(dst_area).name}[{dst_idx}]" if dst_area is not None else "?"
        return f"Attach: {src} -> {dst}"

    if otype == OptionType.ABILITY:
        return "Use ability"

    if otype == OptionType.CARD:
        cid = opt.get("cardId")
        if cid is None:
            area = opt.get("area")
            idx = opt.get("index")
            pi = opt.get("playerIndex", cur.get("yourIndex", 0))
            player = cur["players"][pi]
            if area == AreaType.HAND and player.get("hand") and idx is not None and idx < len(player["hand"]) and player["hand"][idx]:
                cid = player["hand"][idx]["id"]
            elif area == AreaType.ACTIVE and player["active"] and player["active"][0]:
                cid = player["active"][0]["id"]
            elif area == AreaType.BENCH and idx is not None and idx < len(player["bench"]):
                cid = player["bench"][idx]["id"]
            elif area == AreaType.DISCARD and idx is not None and idx < len(player["discard"]):
                cid = player["discard"][idx]["id"]
        cd = get_card(cid) if cid else None
        area_str = AreaType(opt["area"]).name if opt.get("area") is not None else "?"
        return f"Card: {cd.name if cd else '?'} ({area_str}[{opt.get('index')}])"

    return OptionType(otype).name


def format_logs(logs: list[dict], our_idx: int) -> list[str]:
    lines = []
    for log in logs:
        lt = log["type"]
        pi = log.get("playerIndex")
        who = "US" if pi == our_idx else "OPP" if pi is not None else ""

        if lt == LogType.ATTACK:
            atk = get_attack(log.get("attackId"))
            cd = get_card(log.get("cardId"))
            poke = cd.name if cd else "?"
            atk_name = atk.name if atk else "?"
            lines.append(f"    {who} {poke} used {atk_name}")

        elif lt == LogType.HP_CHANGE:
            cd = get_card(log.get("cardId"))
            name = cd.name if cd else "?"
            val = log.get("value", 0)
            lines.append(f"    {who} {name} HP {'+' if val > 0 else ''}{val}")

        elif lt == LogType.SWITCH:
            cd_a = get_card(log.get("cardIdActive"))
            cd_b = get_card(log.get("cardIdBench"))
            a = cd_a.name if cd_a else "?"
            b = cd_b.name if cd_b else "?"
            lines.append(f"    {who} switched {a} <-> {b}")

        elif lt == LogType.EVOLVE:
            cd = get_card(log.get("cardId"))
            cd_t = get_card(log.get("cardIdTarget"))
            lines.append(f"    {who} evolved {cd_t.name if cd_t else '?'} -> {cd.name if cd else '?'}")

        elif lt == LogType.PLAY:
            cd = get_card(log.get("cardId"))
            lines.append(f"    {who} played {cd.name if cd else '?'}")

        elif lt == LogType.ATTACH:
            cd = get_card(log.get("cardId"))
            cd_t = get_card(log.get("cardIdTarget"))
            lines.append(f"    {who} attached {cd.name if cd else '?'} to {cd_t.name if cd_t else '?'}")

        elif lt == LogType.COIN:
            result = "HEADS" if log.get("head") else "TAILS"
            lines.append(f"    {who} coin flip: {result}")

        elif lt == LogType.RESULT:
            r = log.get("result")
            reason = log.get("reason")
            reasons = {1: "0 prizes", 2: "0 deck cards", 3: "no active", 4: "card effect"}
            lines.append(f"    RESULT: P{r} wins ({reasons.get(reason, f'reason {reason}')})")

        elif lt == LogType.TURN_START:
            lines.append(f"    --- {who} turn start ---")

        elif lt == LogType.TURN_END:
            lines.append(f"    --- {who} turn end ---")

        elif lt in (LogType.POISONED, LogType.BURNED, LogType.ASLEEP, LogType.PARALYZED, LogType.CONFUSED):
            cd = get_card(log.get("cardId"))
            name = cd.name if cd else "?"
            condition = LogType(lt).name
            recovered = " recovered" if log.get("isRecover") else ""
            lines.append(f"    {who} {name} {condition}{recovered}")

    return lines


def review(data: dict, verbose: bool = False, losses_only: bool = False):
    our_idx = find_our_index(data)
    teams = data["info"].get("TeamNames", ["P0", "P1"])
    rewards = data["rewards"]

    outcome = "WON" if rewards[our_idx] == 1 else "LOST" if rewards[our_idx] == -1 else "DRAW"
    print(f"Episode {data['id']}: {teams[our_idx]} (P{our_idx}) vs {teams[1-our_idx]} (P{1-our_idx})")
    print(f"Result: {outcome}")
    print(f"Steps: {len(data['steps'])}")
    print()

    last_turn = -1
    for step_num, step in enumerate(data["steps"]):
        our_step = step[our_idx]
        obs = our_step["observation"]
        action = our_step["action"]
        cur = obs.get("current")
        sel = obs.get("select")
        logs = obs.get("logs", [])

        if cur is None:
            continue

        turn = cur.get("turn", 0)
        is_our_turn = cur.get("yourIndex") == our_idx

        if turn != last_turn:
            last_turn = turn
            print(f"{'='*70}")
            print(f"TURN {turn}")
            print(format_board(cur, our_idx))

        if logs:
            log_lines = format_logs(logs, our_idx)
            if log_lines:
                for l in log_lines:
                    print(l)

        if sel is None:
            continue
        if not is_our_turn:
            continue

        ctx = SelectContext(sel["context"]).name
        options = sel.get("option", [])
        min_c = sel.get("minCount", 0)
        max_c = sel.get("maxCount", 0)

        effect = ""
        if sel.get("effect"):
            ecd = get_card(sel["effect"]["id"])
            effect = f" (effect: {ecd.name})" if ecd else ""

        print(f"  >> [{step_num}] {ctx}{effect} — pick {min_c}-{max_c} of {len(options)}")

        action_set = set(action) if isinstance(action, list) else set()

        for i, opt in enumerate(options):
            marker = ">>>" if i in action_set else "   "
            desc = describe_option(opt, cur)
            if verbose or i in action_set or len(options) <= 6:
                print(f"       {marker} [{i}] {desc}")
            elif i == 0:
                print(f"       {marker} [{i}] {desc}")

        if not verbose and len(options) > 6:
            selected_not_shown = [i for i in action_set if i > 0]
            for i in selected_not_shown:
                desc = describe_option(options[i], cur)
                print(f"       >>> [{i}] {desc}")
            print(f"       ... ({len(options)} options total)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python review_replay.py <episode_id|path> [--verbose] [--losses-only]")
        return

    target = sys.argv[1]
    verbose = "--verbose" in sys.argv
    losses_only = "--losses-only" in sys.argv

    if os.path.exists(target):
        path = target
    else:
        path = fetch_replay(target)

    data = load_replay(path)
    review(data, verbose=verbose, losses_only=losses_only)


if __name__ == "__main__":
    main()
