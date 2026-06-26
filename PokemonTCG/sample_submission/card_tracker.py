"""Track known and unknown cards for search API predictions.

The search API requires us to predict hidden cards (our deck, prizes,
opponent's deck/hand/prizes). This module tracks what we've seen and
fills in the blanks with plausible guesses using extracted deck data.
"""
import json
import os
import random
from collections import Counter
from cg.api import Observation, PlayerState, AreaType, CardType
from card_db import get_card


DECK_LIST: list[int] = []
KNOWN_DECKS: list[dict] | None = None


def set_deck(deck: list[int]):
    global DECK_LIST
    DECK_LIST = list(deck)


def _load_known_decks() -> list[dict]:
    global KNOWN_DECKS
    if KNOWN_DECKS is not None:
        return KNOWN_DECKS

    paths = [
        os.path.join(os.path.dirname(__file__), "..", "analysis", "extracted_decks.json"),
        os.path.join(os.path.dirname(__file__), "extracted_decks.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                KNOWN_DECKS = json.load(f)
            return KNOWN_DECKS

    KNOWN_DECKS = []
    return KNOWN_DECKS


def predict_hidden_cards(obs: Observation) -> dict:
    """Generate predictions for all hidden card zones.

    Returns dict with keys: your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active
    """
    state = obs.current
    your_idx = state.yourIndex
    your = state.players[your_idx]
    opp = state.players[1 - your_idx]

    your_known = _collect_known_ids(your, is_self=True)
    your_remaining = list(DECK_LIST)
    for cid in your_known:
        if cid in your_remaining:
            your_remaining.remove(cid)
    random.shuffle(your_remaining)

    your_prize_count = len(your.prize)
    your_deck_count = your.deckCount

    your_prize_ids = []
    for i, p in enumerate(your.prize):
        if p is not None:
            your_prize_ids.append(p.id)
        elif your_remaining:
            your_prize_ids.append(your_remaining.pop())
        else:
            your_prize_ids.append(DECK_LIST[0] if DECK_LIST else 1)

    your_deck_ids = []
    if obs.select and obs.select.deck:
        your_deck_ids = [c.id for c in obs.select.deck]
    else:
        for _ in range(your_deck_count):
            if your_remaining:
                your_deck_ids.append(your_remaining.pop())
            else:
                your_deck_ids.append(DECK_LIST[0] if DECK_LIST else 1)

    opp_known = _collect_known_ids(opp, is_self=False)
    opp_full_deck = _guess_opponent_deck(opp)
    opp_remaining = list(opp_full_deck)
    for cid in opp_known:
        if cid in opp_remaining:
            opp_remaining.remove(cid)
    random.shuffle(opp_remaining)

    opp_hand_ids = []
    for _ in range(opp.handCount):
        if opp_remaining:
            opp_hand_ids.append(opp_remaining.pop())
        elif opp_full_deck:
            opp_hand_ids.append(random.choice(opp_full_deck))

    opp_prize_ids = []
    for p in opp.prize:
        if p is not None:
            opp_prize_ids.append(p.id)
        elif opp_remaining:
            opp_prize_ids.append(opp_remaining.pop())
        elif opp_full_deck:
            opp_prize_ids.append(random.choice(opp_full_deck))

    opp_deck_ids = []
    for _ in range(opp.deckCount):
        if opp_remaining:
            opp_deck_ids.append(opp_remaining.pop())
        elif opp_full_deck:
            opp_deck_ids.append(random.choice(opp_full_deck))

    opp_active = []
    if opp.active and len(opp.active) > 0 and opp.active[0] is None:
        basics = [cid for cid in opp_full_deck if get_card(cid) and get_card(cid).basic and get_card(cid).cardType == CardType.POKEMON]
        opp_active = [random.choice(basics)] if basics else []

    return {
        "your_deck": your_deck_ids,
        "your_prize": your_prize_ids,
        "opp_deck": opp_deck_ids,
        "opp_prize": opp_prize_ids,
        "opp_hand": opp_hand_ids,
        "opp_active": opp_active,
    }


def _collect_known_ids(player: PlayerState, is_self: bool) -> list[int]:
    """Collect all card IDs visible in a player's zones."""
    ids = []
    if player.active:
        for p in player.active:
            if p is not None:
                ids.append(p.id)
                ids.extend(c.id for c in p.energyCards)
                ids.extend(c.id for c in p.tools)
                ids.extend(c.id for c in p.preEvolution)
    for p in player.bench:
        if p is not None:
            ids.append(p.id)
            ids.extend(c.id for c in p.energyCards)
            ids.extend(c.id for c in p.tools)
            ids.extend(c.id for c in p.preEvolution)
    for c in player.discard:
        ids.append(c.id)
    if is_self and player.hand:
        for c in player.hand:
            ids.append(c.id)
    for p in player.prize:
        if p is not None:
            ids.append(p.id)
    return ids


def _guess_opponent_deck(opp: PlayerState) -> list[int]:
    """Match opponent's visible cards against known decks to predict full 60."""
    seen_ids = set(_collect_known_ids(opp, is_self=False))
    if not seen_ids:
        return _fallback_deck(seen_ids)

    known = _load_known_decks()
    if not known:
        return _fallback_deck(seen_ids)

    best_deck = None
    best_score = -1

    for entry in known:
        deck_ids = set(int(k) for k in entry.get("card_counts", {}).keys())
        overlap = len(seen_ids & deck_ids)
        games = entry.get("games", 1)
        wr = entry.get("win_rate", 0.5)
        score = overlap * 10 + games * 0.1 + wr * 5
        if overlap > 0 and score > best_score:
            best_score = score
            best_deck = entry

    if best_deck and best_score > 0:
        return best_deck["deck"][:60]

    return _fallback_deck(seen_ids)


def _fallback_deck(seen_ids: set) -> list[int]:
    deck = list(seen_ids)
    fill_cards = []
    for cid in seen_ids:
        cd = get_card(cid)
        if cd and cd.cardType in (CardType.BASIC_ENERGY,):
            fill_cards.append(cid)
    if not fill_cards:
        fill_cards = [1, 2, 3, 4, 5, 6, 7, 8]
    while len(deck) < 60:
        deck.append(random.choice(fill_cards))
    return deck[:60]
