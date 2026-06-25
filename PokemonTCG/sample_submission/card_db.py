"""Cached card and attack data lookups."""
from cg.api import all_card_data, all_attack, CardData, Attack

_card_cache: dict[int, CardData] | None = None
_attack_cache: dict[int, Attack] | None = None

def get_all_cards() -> dict[int, CardData]:
    global _card_cache
    if _card_cache is None:
        _card_cache = {c.cardId: c for c in all_card_data()}
    return _card_cache

def get_card(card_id: int) -> CardData | None:
    return get_all_cards().get(card_id)

def get_all_attacks() -> dict[int, Attack]:
    global _attack_cache
    if _attack_cache is None:
        _attack_cache = {a.attackId: a for a in all_attack()}
    return _attack_cache

def get_attack(attack_id: int) -> Attack | None:
    return get_all_attacks().get(attack_id)
