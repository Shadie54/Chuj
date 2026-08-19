# game/ai_sweep_v2/solver.py
"""
Tier B — presné vyhľadávanie pre koncovku.

Keď Tier A nevie dokázať istotu (napr. horník je u súpera a treba ho
vynútiť cez discard), skúsime to dokázať presným prehľadávaním zvyšného
stromu hry — podobne ako "double dummy" solver v bridge.

Keďže úplne kompletný dôkaz "pre VŠETKY možné rozloženia neznámych
kariet" je kombinatoricky drahý, používame pragmatický, stále 100%
deterministický kompromis: vygenerujeme niekoľko REPREZENTATÍVNYCH
NAJHORŠÍCH rozložení (pre každého súpera skúsime "tento súper dostal
všetky nebezpečné karty čo mohol"), a hľadáme JEDNU kartu, ktorá prežije
ÚPLNE VŠETKY tieto hypotézy naraz — nie že každá hypotéza má vlastnú
víťaznú kartu (to by nebolo robustné, lebo v skutočnosti neviem vopred
ktorá hypotéza platí).

V rámci jednej hypotézy (= plne známe rozdanie) je vyhľadávanie presný
AND-OR strom:
- môj ťah = OR uzol (stačí JEDNA karta ktorá vedie k úspechu)
- súperov ťah = AND uzol (súper hrá nepriateľsky — VŠETKY jeho voľby
  musia viesť k úspechu, inak si vyberie tú čo ma porazí)
- zlyhanie = akýkoľvek štich s trestnou kartou vyhraný niekým iným než ja
"""

from __future__ import annotations
from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.trick import Trick
from game.ai_sweep_v2.models import SweepPlan
from config import SUITS, NUM_PLAYERS

MAX_SEARCH_TRICKS = 5   # nespúšťať keď zostáva viac štichov (príliš drahé)
MAX_SEARCH_NODES = 200_000  # bezpečnostný strop na jednu hypotézu


class _SearchBudgetExceeded(Exception):
    """Interná — hypotéza sa nestihla dokázať v rozumnom čase, radšej sa vzdaj."""
    pass


class _NodeCounter:
    __slots__ = ("count",)

    def __init__(self):
        self.count = 0

    def tick(self):
        self.count += 1
        if self.count > MAX_SEARCH_NODES:
            raise _SearchBudgetExceeded()


def _legal_plays(hand: list[Card], lead_suit: str | None, trick_number: int) -> list[Card]:
    """Legálne karty pre daného hráča v danom štichu."""
    if lead_suit is None:
        playable = list(hand)
        # Pravidlo hry: v 1. štichu sa nesmie viesť červeň
        if trick_number == 0:
            non_heart = [c for c in playable if c.suit != "heart"]
            if non_heart:
                playable = non_heart
        return playable

    same_suit = [c for c in hand if c.suit == lead_suit]
    return same_suit if same_suit else list(hand)


def _trick_winner(trick_cards: list[tuple[int, Card]]) -> int:
    lead_suit = trick_cards[0][1].suit
    best_idx, best_card = trick_cards[0]
    for idx, card in trick_cards[1:]:
        if card.suit == lead_suit and card.rank_order > best_card.rank_order:
            best_idx, best_card = idx, card
    return best_idx


def _trick_has_penalty(trick_cards: list[tuple[int, Card]]) -> bool:
    return any(c.suit == "heart" or c.is_special for _, c in trick_cards)


def _search(hands: dict[int, list[Card]],
            trick_cards: list[tuple[int, Card]],
            next_player: int,
            my_idx: int,
            trick_number: int,
            counter: _NodeCounter) -> bool:
    """
    AND-OR search. Vracia True ak (z pohľadu next_player na rade a
    aktuálneho stavu) existuje pokračovanie, kde JA získam všetky
    zvyšné trestné karty.
    """
    counter.tick()

    lead_suit = trick_cards[0][1].suit if trick_cards else None
    playable = _legal_plays(hands[next_player], lead_suit, trick_number)

    is_me = (next_player == my_idx)
    outcomes = []

    for card in playable:
        new_hand = [c for c in hands[next_player] if c != card]
        new_hands = dict(hands)
        new_hands[next_player] = new_hand
        new_trick = trick_cards + [(next_player, card)]

        if len(new_trick) == NUM_PLAYERS:
            winner = _trick_winner(new_trick)
            if _trick_has_penalty(new_trick) and winner != my_idx:
                result = False  # štich s bodmi mi ušiel — táto vetva zlyhala
            elif not new_hands[winner] and all(not h for h in new_hands.values()):
                result = True  # koniec kola, žiadne zlyhanie po ceste
            else:
                result = _search(new_hands, [], winner, my_idx,
                                  trick_number + 1, counter)
        else:
            result = _search(new_hands, new_trick, (next_player + 1) % NUM_PLAYERS,
                              my_idx, trick_number, counter)

        if is_me and result:
            return True          # OR uzol — jedna stačí
        if not is_me and not result:
            return False          # AND uzol — jedna zlá stačí na zamietnutie
        outcomes.append(result)

    return all(outcomes) if not is_me else any(outcomes)


def _danger_score(card: Card) -> tuple:
    """Zoradenie kariet od najnebezpečnejšej (pre priradenie súperovi)."""
    return (
        1 if card.is_special else 0,
        1 if card.suit == "heart" else 0,
        card.rank_order,
    )


def _generate_hypothesis(target_opponent: int,
                          opponents: list[int],
                          hand_sizes: dict[int, int],
                          void_suits: dict[int, set[str]],
                          pool: list[Card]) -> dict[int, list[Card]] | None:
    """
    Postaví jedno "najhoršie rozloženie" — target_opponent dostane
    prednostne čo najviac nebezpečných kariet, zvyšok sa rozdelí medzi
    ostatných. Vracia None ak sa nepodarilo nájsť platné priradenie
    (konflikt s void_suits/kapacitou rúk).
    """
    remaining_slots = dict(hand_sizes)
    assignment = {i: [] for i in opponents}
    remaining_pool = sorted(pool, key=_danger_score, reverse=True)

    # 1. Cieľový súper dostane prednosť na nebezpečné karty
    still_unassigned = []
    for card in remaining_pool:
        if remaining_slots[target_opponent] > 0 and card.suit not in void_suits[target_opponent]:
            assignment[target_opponent].append(card)
            remaining_slots[target_opponent] -= 1
        else:
            still_unassigned.append(card)

    # 2. Zvyšok — greedy medzi ostatnými (preferuj toho s najviac voľnými slotmi)
    for card in still_unassigned:
        eligible = [
            i for i in opponents
            if remaining_slots[i] > 0 and card.suit not in void_suits[i]
        ]
        if not eligible:
            return None  # nedá sa validne priradiť — táto hypotéza je nekonzistentná
        best = max(eligible, key=lambda i: remaining_slots[i])
        assignment[best].append(card)
        remaining_slots[best] -= 1

    if any(remaining_slots[i] != 0 for i in opponents):
        return None  # niekomu ostali prázdne sloty — pool a hand_sizes nesedia

    return assignment


def _generate_hypotheses(player: Player, memory: AIMemory, current_trick: Trick,
                          trick_number: int) -> list[dict[int, list[Card]]]:
    """Vygeneruje reprezentatívne najhoršie rozloženia (max 1 na súpera)."""
    already_played = {c for _, c in current_trick.played_cards}
    pool = [
        c for suit in SUITS for c in memory.remaining[suit]
        if c not in already_played
    ]

    opponents = [i for i in range(NUM_PLAYERS) if i != player.index]
    played_by = {idx for idx, _ in current_trick.played_cards}

    # Priamy výpočet: každý hráč mal na začiatku kola 8 kariet, odohral
    # presne `trick_number` úplných štichov; ak už v rozohranom štichu
    # zahral, má o 1 kartu menej.
    hand_sizes = {
        i: (8 - trick_number) - (1 if i in played_by else 0)
        for i in opponents
    }

    # Konzistentnosť: súčet veľkostí rúk musí sedieť s poolom (defenzívna
    # kontrola — ak nesedí, niečo je vo AIMemory desynchronizované a
    # Tier B by generoval nesprávne hypotézy).
    if sum(hand_sizes.values()) != len(pool):
        return []  # niečo nesedí — radšej Tier B vôbec neskúšať

    void_suits = memory.void_suits

    hypotheses = []
    for target in opponents:
        hyp = _generate_hypothesis(target, opponents, hand_sizes, void_suits, pool)
        if hyp is not None:
            hypotheses.append(hyp)
    return hypotheses


def solve(player: Player, memory: AIMemory, trick_number: int,
          current_trick: Trick, playable: list[Card]) -> SweepPlan:
    """
    Tier B hlavný vstupný bod. Vracia SweepPlan — buď PROVEN_CERTAIN
    s konkrétnou kartou (ak existuje ťah čo prežije všetky testované
    najhoršie hypotézy), alebo UNRESOLVED (neoverené, necháva sa na
    Tier C).
    """
    tricks_remaining = 8 - trick_number
    if tricks_remaining > MAX_SEARCH_TRICKS:
        return SweepPlan(
            certainty="UNRESOLVED", decision="WATCH",
            reasoning=[f"Tier B: preskočené — {tricks_remaining} štichov "
                       f"zostáva (limit {MAX_SEARCH_TRICKS})"],
        )

    hypotheses = _generate_hypotheses(player, memory, current_trick, trick_number)
    if not hypotheses:
        return SweepPlan(
            certainty="UNRESOLVED", decision="WATCH",
            reasoning=["Tier B: nepodarilo sa zostaviť žiadnu platnú hypotézu rozloženia"],
        )

    reasoning = [f"Tier B: {len(hypotheses)} hypotéz(a) najhoršieho rozloženia"]

    for candidate in playable:
        survives_all = True
        for hyp in hypotheses:
            hands = dict(hyp)
            hands[player.index] = [c for c in player.hand.cards if c != candidate]

            trick_cards = list(current_trick.played_cards) + [(player.index, candidate)]
            counter = _NodeCounter()
            try:
                if len(trick_cards) == NUM_PLAYERS:
                    winner = _trick_winner(trick_cards)
                    if _trick_has_penalty(trick_cards) and winner != player.index:
                        ok = False
                    else:
                        ok = _search(hands, [], winner, player.index,
                                     trick_number + 1, counter)
                else:
                    next_player = (trick_cards[-1][0] + 1) % NUM_PLAYERS
                    ok = _search(hands, trick_cards, next_player,
                                 player.index, trick_number, counter)
            except _SearchBudgetExceeded:
                ok = False  # radšej konzervatívne — nedokázané, nie isté

            if not ok:
                survives_all = False
                break

        if survives_all:
            reasoning.append(f"karta {candidate} prežila všetky hypotézy")
            return SweepPlan(
                certainty="PROVEN_CERTAIN",
                decision="COMMIT",
                card=candidate,
                confidence=1.0,
                reasoning=reasoning,
            )

    reasoning.append("žiadna karta neprežila všetky hypotézy")
    return SweepPlan(
        certainty="UNRESOLVED", decision="WATCH",
        reasoning=reasoning,
    )
