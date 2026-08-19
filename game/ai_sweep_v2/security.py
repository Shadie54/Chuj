# game/ai_sweep_v2/security.py
"""
Tier A — Security check.

Lacná, 100% deterministická kontrola: je daný zdroj trestných bodov už
BEZPEČNE zaistený (skončí v mojej hromádke bez ohľadu na to, ako sa
zvyšok kola odohrá)?

Pravidlo je symetrické voči tomu, kto kartu fyzicky drží — "zaistené"
znamená že žiadna vyššia karta v tej farbe už nemôže padnúť inak než
do mojej hromádky. Predtým (starý systém) sa "mám horníka v ruke"
mylne rovnalo "zaistené", bez ohľadu na A/K ochranu — to bol koreň
dvoch bugov, ktoré táto vrstva má z princípu vylúčiť.

Tier A nevie dokázať prípady, kde je potrebné vynútiť súperovi discard
(napr. horník u súpera, alebo časť červení stále vonku) — tie ostávajú
UNRESOLVED a čakajú na Tier B (presné vyhľadávanie) / Tier C (odhad).
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_sweep_v2.models import PenaltySource


def check_already_lost(player: Player, memory: AIMemory) -> bool:
    """
    True ak niektorý súper už drží aspoň jednu trestnú kartu.

    Odvodené nepriamo (bez nahliadnutia do cudzích kariet/hromádok) —
    porovnaním celkového počtu trestných kariet v hre (10 = 8 hearts +
    2 horníci) s tým, čo viem zúčtovať: moja ruka + karty ešte vonku
    (remaining) + moje už zozbierané. Rozdiel = u súperov.
    """
    hand = player.hand.cards
    my_hand_penalty = sum(
        1 for c in hand
        if c.suit == "heart" or (c.is_special and c.suit in ("leaf", "acorn"))
    )

    remaining_penalty = len(memory.remaining["heart"])
    for suit in ("leaf", "acorn"):
        if not memory.is_special_gone(suit):
            i_have = any(c.is_special and c.suit == suit for c in hand)
            if not i_have:
                remaining_penalty += 1

    my_taken_penalty = len(player.penalty_cards)
    total_accounted = my_hand_penalty + remaining_penalty + my_taken_penalty
    return (10 - total_accounted) > 0


def _suit_control_count(my_cards: list[Card], remaining: list[Card]) -> int:
    """Koľko najvyšších kariet v rade (odzhora) v tejto farbe je mojich."""
    all_alive = sorted(my_cards + remaining, key=lambda c: c.rank_order, reverse=True)
    count = 0
    for card in all_alive:
        if card in my_cards:
            count += 1
        else:
            break
    return count


def _hornik_source(suit: str, player: Player, memory: AIMemory) -> PenaltySource:
    hand = player.hand.cards

    if memory.is_special_gone(suit):
        my_penalty = any(
            c.is_special and c.suit == suit for c in player.penalty_cards
        )
        if my_penalty:
            return PenaltySource(
                kind=f"{suit}_hornik", secured=True, location="me",
                reason="už v mojej hromádke",
            )
        # Ak by to nebolo moje, check_already_lost() by to už zachytilo
        # skôr (evaluate_sources sa sem vtedy vôbec nedostane).
        return PenaltySource(
            kind=f"{suit}_hornik", secured=False, location="opponent",
            reason="padol súperovi",
        )

    my_suit_cards = [c for c in hand if c.suit == suit]
    remaining = memory.remaining[suit]
    i_have_hornik = any(c.is_special for c in my_suit_cards)

    if not i_have_hornik:
        return PenaltySource(
            kind=f"{suit}_hornik", secured=False, location="opponent",
            reason="horník je u súpera — vynútenie discardu vyžaduje Tier B",
        )

    hornik = next(c for c in my_suit_cards if c.is_special)
    higher_outside = [c for c in remaining if c.rank_order > hornik.rank_order]

    if not higher_outside:
        return PenaltySource(
            kind=f"{suit}_hornik", secured=True, location="me",
            reason="mám horníka, žiadne A/K vonku",
        )

    return PenaltySource(
        kind=f"{suit}_hornik", secured=False, location="me",
        reason=f"mám horníka bez ochrany — vonku {[str(c) for c in higher_outside]}",
    )


def _hearts_source(player: Player, memory: AIMemory) -> PenaltySource:
    remaining = memory.remaining["heart"]
    if not remaining:
        return PenaltySource(
            kind="hearts", secured=True, location="me",
            reason="žiadna červeň už nie je vonku",
        )
    return PenaltySource(
        kind="hearts", secured=False, location="unknown",
        reason=f"{len(remaining)} červení ešte vonku — vyžaduje Tier B/C",
    )


def evaluate_sources(player: Player, memory: AIMemory) -> list[PenaltySource]:
    """Vyhodnotí všetky 3 zdroje trestných bodov (Tier A, per-zdroj)."""
    return [
        _hearts_source(player, memory),
        _hornik_source("leaf", player, memory),
        _hornik_source("acorn", player, memory),
    ]
