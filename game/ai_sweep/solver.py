# game/ai_sweep/solver.py
"""
Tier B — presné vyhľadávanie pre koncovku.

Keď Tier A nevie dokázať istotu (napr. horník je u súpera a treba ho
vynútiť cez discard), skúsime to dokázať presným prehľadávaním zvyšného
stromu hry — podobne ako "double dummy" solver v bridge.

2026-09-04: pôvodná verzia testovala len 2-3 RUČNE VYBRANÉ "najhoršie"
hypotézy (pre každého súpera "čo keby dostal všetky nebezpečné karty čo
mohol") a výsledok vyhlasovala za PROVEN_CERTAIN/confidence=1.0. To NEBOL
skutočný dôkaz — rozdelenie nebezpečných kariet MEDZI viacerých súperov
naraz (napr. každý dostane jednu) nie je pokryté žiadnou z tých 2-3
"koncentrovaných" hypotéz, a pritom môže poraziť kartu, ktorá "prežila"
všetky testované scenáre. To vysvetľovalo katastrofálnu reálnu úspešnosť
(3.8% na 200 hrách/seed 777, viď claude/03_SWEEP_V2_HANDOFF.md §5) — Tier
B "dokazoval" veci, ktoré neboli doopravdy dokázané, vo veľkom objeme
(oveľa viac pokusov než opatrná pipeline).

Teraz namiesto vzorky testujeme ÚPLNE VŠETKY platné rozdelenia zvyšných
neznámych kariet (rešpektujúc void_suits a presné veľkosti rúk) —
skutočný kompletný dôkaz, nie odhad. Toto je výpočtovo zvládnuteľné len
pri malom počte zvyšných kariet, preto MAX_SEARCH_TRICKS drží tento
rozsah nízko (štartujeme na 2 kolá — presne rozsah, ktorý sme predtým
riešili ručne cez pipeline.py opravy §6.3 a "posledná karta u súpera" —
neskôr možno opatrne rozšíriť na 3+, ak to výkonovo zvládne).

V rámci jedného rozdelenia (= plne known rozdanie) je vyhľadávanie presný
AND-OR strom:
- môj ťah = OR uzol (stačí JEDNA karta ktorá vedie k úspechu)
- súperov ťah = AND uzol (súper hrá nepriateľsky — VŠETKY jeho voľby
  musia viesť k úspechu, inak si vyberie tú čo ma porazí)
- zlyhanie = akýkoľvek štich s trestnou kartou vyhraný niekým iným než ja
"""

from __future__ import annotations
import itertools
from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.trick import Trick
from game.ai_sweep.models import SweepPlan
from config import SUITS, NUM_PLAYERS

MAX_SEARCH_TRICKS = 2   # nespúšťať keď zostáva viac štichov (príliš drahé
                        # pre ÚPLNÉ vyčerpanie priestoru rozložení — pozri
                        # docstring vyššie; zvyšovať postupne a opatrne)
MAX_SEARCH_NODES = 200_000  # bezpečnostný strop na jedno rozdelenie
MAX_DISTRIBUTIONS = 20_000  # bezpečnostný strop na počet vygenerovaných
                            # rozložení (obranné opatrenie — pri
                            # MAX_SEARCH_TRICKS=2/3 by sa nemal reálne
                            # nikdy vyčerpať, priestor je malý)


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


def _generate_all_distributions(opponents: list[int],
                                 hand_sizes: dict[int, int],
                                 void_suits: dict[int, set[str]],
                                 pool: list[Card]
                                 ) -> list[dict[int, list[Card]]]:
    """
    Vygeneruje ÚPLNE VŠETKY platné rozdelenia `pool` medzi `opponents`,
    rešpektujúc presné veľkosti rúk (`hand_sizes`) a známe voids
    (`void_suits`) — skutočné kompletné vyčerpanie priestoru, nie len
    vzorka "najhorších" scenárov (pozri modulový docstring prečo je toto
    dôležité pre to, aby PROVEN_CERTAIN bol naozaj dôkaz).

    Backtracking: pridelí kartám prvého súpera v `opponents`, potom
    rekurzívne pokračuje na ďalšieho so zvyšným poolom, atď. Pri
    MAX_SEARCH_TRICKS=2-3 je pool malý (rádovo jednotky kariet), takže
    toto je lacné — orezané cez MAX_DISTRIBUTIONS ako obranné poistenie.
    """
    def backtrack(remaining_pool: list[Card],
                  remaining_opponents: list[int]):
        if not remaining_opponents:
            if not remaining_pool:
                yield {}
            return

        opp = remaining_opponents[0]
        size = hand_sizes[opp]
        eligible = [c for c in remaining_pool if c.suit not in void_suits[opp]]
        if len(eligible) < size:
            return  # nedá sa splniť veľkosť ruky pri danom void obmedzení

        rest_opponents = remaining_opponents[1:]
        for combo in itertools.combinations(eligible, size):
            combo_set = set(combo)
            new_remaining = [c for c in remaining_pool if c not in combo_set]
            for rest_assignment in backtrack(new_remaining, rest_opponents):
                rest_assignment[opp] = list(combo)
                yield rest_assignment

    distributions = []
    for assignment in backtrack(pool, opponents):
        distributions.append(assignment)
        if len(distributions) >= MAX_DISTRIBUTIONS:
            break
    return distributions


def _generate_hypotheses(player: Player, memory: AIMemory, current_trick: Trick,
                          trick_number: int) -> list[dict[int, list[Card]]]:
    """Vygeneruje úplne všetky platné rozdelenia zvyšných kariet."""
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
    # Tier B by generoval nesprávne rozdelenia).
    if sum(hand_sizes.values()) != len(pool):
        return []  # niečo nesedí — radšej Tier B vôbec neskúšať

    void_suits = memory.void_suits

    return _generate_all_distributions(opponents, hand_sizes, void_suits, pool)


def _opponent_already_has_penalty(player: Player, memory: AIMemory) -> int:
    """
    Rovnaká kontrola ako pipeline.py `_gate1_no_opponent_penalty` —
    koľko trestných kariet už NEODVOLATEĽNE drží niekto iný (zo štichov
    odohraných PRED týmto rozhodnutím, v tomto kole).

    Kriticky dôležité pre Tier B: `_search` je čisto FORWARD-looking (rieši
    len štichy od `trick_number` do konca kola) — nič nevie o tom, či
    sweep nebol už dávno stratený kvôli skoršiemu štichu v tomto istom
    kole. Bez tejto kontroly vie Tier B "dokázať" PROVEN_CERTAIN aj vtedy,
    keď je celkový sweep matematicky nemožný — presne to spôsobovalo
    masívny výbuch neúspešných pokusov po opravení vzorkovania hypotéz
    (nájdené 2026-09-04 pri regresnom teste: sweep_failed vyskočilo na
    ~4900 namiesto očakávaného zlepšenia).
    """
    hand = player.hand.cards
    my_hand_penalty = sum(
        1 for c in hand
        if c.suit == "heart" or (c.is_special and c.suit in ("leaf", "acorn"))
    )
    remaining_penalty = len(memory.remaining["heart"])
    if not memory.is_special_gone("leaf"):
        if not any(c.is_special and c.suit == "leaf" for c in hand):
            remaining_penalty += 1
    if not memory.is_special_gone("acorn"):
        if not any(c.is_special and c.suit == "acorn" for c in hand):
            remaining_penalty += 1
    my_taken_penalty = len(player.penalty_cards)
    total_accounted = my_hand_penalty + remaining_penalty + my_taken_penalty
    return 10 - total_accounted


def solve(player: Player, memory: AIMemory, trick_number: int,
          current_trick: Trick, playable: list[Card]) -> SweepPlan:
    """
    Tier B hlavný vstupný bod. Vracia SweepPlan — buď PROVEN_CERTAIN
    s konkrétnou kartou (ak existuje ťah, ktorý prežije ÚPLNE VŠETKY
    platné rozdelenia zvyšných neznámych kariet — skutočný kompletný
    dôkaz, pozri modulový docstring), alebo UNRESOLVED (neoverené,
    necháva sa na Tier C).
    """
    already_taken = _opponent_already_has_penalty(player, memory)
    if already_taken > 0:
        return SweepPlan(
            certainty="PROVEN_IMPOSSIBLE", decision="ABANDON",
            reasoning=[f"Tier B: súper už má {already_taken} trestných "
                       f"kariet zo skoršieho štichu — sweep nemožný "
                       f"(forward search by to nevidel)"],
        )

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
            reasoning=["Tier B: nepodarilo sa zostaviť žiadne platné rozdelenie kariet"],
        )

    reasoning = [f"Tier B: {len(hypotheses)} možných rozložení (úplné vyčerpanie priestoru)"]

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
