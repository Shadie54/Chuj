# game/ai_sweep_v2/risk.py
"""
Tier C — risk/EV odhad.

Keď Tier A aj Tier B vrátia UNRESOLVED, situácia je skutočne neurčitá —
nedá sa nič dokázať, len odhadnúť. Namiesto duplikovania trap/escape
logiky (jedna z otvorených dier starého systému) sa tu priamo využíva
AIMemory.build_suit_profile().

DÔLEŽITÉ: Tier C nikdy nevracia PROVEN_CERTAIN. Aj keď sa nakoniec
rozhodne COMMIT (pozri engine.py), certainty ostáva UNRESOLVED — ide
o odhad, nie dôkaz. Presne toto rozlíšenie ("viem" vs. "odhadujem")
bolo koreňom pôvodných bugov v starom systéme, kde P(sweep)=1.0
mohlo znamenať oboje.
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_sweep_v2.models import PenaltySource

# Confidence sa zámerne nikdy nevyšplhá na 1.0 — to je vyhradené
# pre skutočne dokázané prípady (Tier A/B).
MAX_HEURISTIC_CONFIDENCE = 0.95


def _suit_for_source(kind: str) -> str | None:
    return {"leaf_hornik": "leaf", "acorn_hornik": "acorn"}.get(kind)


def estimate_capacity(player: Player, memory: AIMemory,
                       unresolved: list[PenaltySource],
                       current_trick_cards: list[Card]) -> float:
    """
    Heuristický odhad "kontroly" nad farbami s nezaisteným zdrojom —
    pomer safe/escape kariet voči celkovému počtu mojich kariet v tej
    farbe, spriemerovaný naprieč všetkými relevantnými farbami.
    1.0 = plná kontrola všade, 0.0 = žiadna.
    """
    suits_to_check = set()
    for s in unresolved:
        if s.kind == "hearts":
            suits_to_check.add("heart")
        else:
            suit = _suit_for_source(s.kind)
            if suit:
                suits_to_check.add(suit)

    if not suits_to_check:
        return MAX_HEURISTIC_CONFIDENCE

    scores = []
    for suit in suits_to_check:
        profile = memory.build_suit_profile(suit, player.hand.cards, current_trick_cards)
        if profile.is_void:
            # Nemám v ruke túto farbu vôbec — kontrola závisí len na tom,
            # či niekoho neskôr donútim discardnúť. Nízka, nie nulová.
            scores.append(0.2)
            continue
        total = len(profile.my_cards)
        controllable = len(profile.safe_cards) + len(profile.escape_cards)
        scores.append(controllable / total if total else 0.0)

    return sum(scores) / len(scores)


def source_cost_points(source: PenaltySource, memory: AIMemory) -> int:
    """
    Odhad bodovej hodnoty aktuálne visiacej na danom zdroji — použité na
    zoradenie nezaistených zdrojov od najlacnejšieho po najdrahší (pozri
    engine._decide_tier_c). Hearts sú takmer vždy najlacnejšie (1-2b za
    kartu), horníci sú drahí (4-16b za jednu kartu) — presne preto sa
    najprv oplatí "otestovať" lacné zdroje, než sa odhalí drahý horník.
    """
    if source.kind == "hearts":
        both_lit = (
            memory.illuminated_by["leaf"] is not None
            and memory.illuminated_by["acorn"] is not None
        )
        per_card = 2 if both_lit else 1
        return len(memory.remaining["heart"]) * per_card
    if source.kind == "leaf_hornik":
        return 16 if memory.illuminated_by["leaf"] is not None else 8
    if source.kind == "acorn_hornik":
        return 8 if memory.illuminated_by["acorn"] is not None else 4
    return 0


def _location_risk_weight(location: str) -> float:
    """Vyššie číslo = rizikovejšie (menej isté). Škála 0.0-1.0."""
    return {
        "unknown": 1.0,   # netuším kto to drží — najhoršie
        "opponent": 0.6,  # viem kto, treba vynútiť discard
        "me": 0.3,        # mám to ja, len nechránené — najviac ovplyvniteľné
        "n/a": 0.0,
    }.get(location, 1.0)


def estimate_confidence(player: Player, memory: AIMemory,
                         unresolved: list[PenaltySource],
                         current_trick_cards: list[Card],
                         tricks_remaining: int) -> float:
    """
    Heuristický odhad pravdepodobnosti úspechu (0.0 – MAX_HEURISTIC_CONFIDENCE).
    Nikdy nie skutočná istota — pozri modul docstring.
    """
    if not unresolved:
        # Nemalo by nastať (Tier A by to už zachytilo), ale pre istotu.
        return MAX_HEURISTIC_CONFIDENCE

    capacity = estimate_capacity(player, memory, unresolved, current_trick_cards)

    risk_penalty = sum(
        _location_risk_weight(s.location) for s in unresolved
    ) / len(unresolved)

    # Málo štichov zostáva = menej priestoru na vynútenie -> znižuje confidence.
    # Každý nezaistený zdroj potrebuje rádovo ~2 štichy na vyriešenie.
    time_factor = min(1.0, tricks_remaining / max(1, len(unresolved) * 2))

    raw = capacity * (1.0 - risk_penalty) * time_factor
    return max(0.0, min(MAX_HEURISTIC_CONFIDENCE, raw))
