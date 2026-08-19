# game/ai_sweep_v2/strategies/force_resolution.py
"""
FORCE_RESOLUTION — "leverage" hra s vlastným nechráneným vysvieteným
horníkom, plus dve sondy pred ňou (ACE_PROBE, KING_PROBE).

Poradie v rámci tejto stratégie (pre daný konkrétny horník):
1. Ak držím aj ESO tej istej farby, vediem ho PRVÉ (`ACE_PROBE`) — je
   to BEZRIZIKOVÉ (eso vždy vyhráva, nič ho neporazí). Ak súper drží
   kráľa ako JEDINÚ zvyšnú kartu tej farby, musí ho zahrať (musí
   priznať farbu) → kráľ padne zadarmo a horník je odvtedy istý. Ak má
   iné karty tej farby, len podlezie — žiadna strata.
2. Ak eso nemám, ale mám KRÁĽA, skúsim najprv jeho (`KING_PROBE`) —
   ALE toto už nie je bezrizikové ako eso: ak niekto drží eso, môže
   kráľa prebiť. Keďže samotný kráľ (ani iné ne-horník karty tej
   farby) nemá žiadnu bodovú hodnotu, priama strata je nulová — RIZIKO
   je nepriame: ak je v tom štichu aj hráč bez tejto farby (void), ktorý
   zahodí inú trestnú kartu (napr. srdce), a ja štich prehrám, tie body
   pripadnú súperovi namiesto mne. Preto nižší confidence bonus než pri
   ACE_PROBE. Ak sa to podarí (súper prebije esom, alebo je nútený ho
   zahrať), eso sa "minie" a horník je odvtedy istý — presne ako pri
   ACE_PROBE, len s menšou istotou vopred.
3. Až keď ani eso ani kráľ nie sú k dispozícii, vediem samotného
   horníka ako páku (`FORCE_RESOLUTION`). Keďže sa smie podliezať,
   súper s A/K nie je NÚTENÝ ho zobrať — ak ho nikto neprebije,
   vyhrávam vlastný štich a horník sa mi tým zaisťuje.

Volajúci (engine.py) zodpovedá za to, že táto stratégia sa vyvolá len
pre zdroj, ktorý je momentálne najlacnejší medzi AKTUÁLNE TESTOVATEĽNÝMI
nezaistenými zdrojmi (pozri risk.source_cost_points + kaskáda v
engine._decide_tier_c) — inak riskujeme presne to, čo spôsobilo pôvodný
problém: predčasné odhalenie drahej karty, kým lacnejšie riziká (napr.
hearts) ešte visia vo vzduchu a súper by ich mohol lacno prebiť.
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_sweep_v2.models import PenaltySource

STRATEGY_NAME = "FORCE_RESOLUTION"
ACE_PROBE_NAME = "FORCE_RESOLUTION_ACE_PROBE"
KING_PROBE_NAME = "FORCE_RESOLUTION_KING_PROBE"

_BASE_BONUS = 0.5
_PER_HIGHER_CARD_PENALTY = 0.1
_ACE_PROBE_BONUS = 0.6   # bezrizikový ťah — vysoká dôvera
_KING_PROBE_BONUS = 0.35  # reálne (aj keď nepriame) riziko — nižšia dôvera


def _find_card(player: Player, suit: str, rank: str) -> Card | None:
    return next(
        (c for c in player.hand.cards if c.suit == suit and c.rank == rank), None
    )


def find_candidate(player: Player, memory: AIMemory,
                    source: PenaltySource,
                    playable: list[Card],
                    is_leader: bool) -> tuple[Card, float, str] | None:
    """
    source: konkrétny nezaistený horník-zdroj (kind in {"leaf_hornik",
    "acorn_hornik"}, location=="me"), o ktorom volajúci už rozhodol, že
    je momentálne na rade. Vráti (karta, confidence_bonus, meno_stratégie)
    alebo None, ak sa stratégia neuplatňuje / nedá sa práve teraz zahrať.
    """
    if not is_leader or source.location != "me":
        return None

    suit = {"leaf_hornik": "leaf", "acorn_hornik": "acorn"}.get(source.kind)
    if suit is None:
        return None

    hornik = next(
        (c for c in player.hand.cards if c.is_special and c.suit == suit), None
    )
    if hornik is None or hornik not in playable:
        return None

    higher_outside = [
        c for c in memory.remaining[suit] if c.rank_order > hornik.rank_order
    ]
    if not higher_outside:
        # Toto by už Tier A zachytil ako secured — obranná kontrola.
        return None

    # ACE_PROBE: ak držím aj eso tej istej farby, sonduj s ním prvé —
    # bezrizikovo (eso vždy vyhráva).
    ace = _find_card(player, suit, "ace")
    if ace is not None and ace in playable:
        return ace, _ACE_PROBE_BONUS, ACE_PROBE_NAME

    # KING_PROBE: eso nemám, ale mám kráľa — skús jeho. Nie je to úplne
    # bezrizikové (pozri modul docstring), preto nižší bonus.
    king = _find_card(player, suit, "king")
    if king is not None and king in playable:
        return king, _KING_PROBE_BONUS, KING_PROBE_NAME

    n_higher = len(higher_outside)
    bonus = max(0.0, _BASE_BONUS - _PER_HIGHER_CARD_PENALTY * n_higher)
    return hornik, bonus, STRATEGY_NAME
