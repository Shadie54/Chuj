# game/ai_sweep_v2/models.py
"""
Dátový model pre nový sweep systém (v2).

Kľúčový rozdiel oproti starému systému: stav hovorí o ISTOTE
(certainty), nie len o akcii — pri debugovaní je hneď vidno, či AI
niečo VIE (dokázané), alebo len ODHADUJE (Tier C, zatiaľ neimplementované).
"""

from dataclasses import dataclass, field
from game.card import Card


@dataclass
class PenaltySource:
    """
    Jeden z 3 zdrojov trestných bodov v kole (hearts / leaf_hornik /
    acorn_hornik).

    `secured` je symetrické — nezáleží či danú vec fyzicky držím ja
    alebo súper, len či je nad ňou dokázaná kontrola (nikto vyšší už
    nemôže padnúť inak než do mojej hromádky).
    """
    kind: str          # "hearts" | "leaf_hornik" | "acorn_hornik"
    secured: bool
    location: str       # "me" | "opponent" | "unknown" | "n/a"
    reason: str = ""


@dataclass
class SweepPlan:
    """Výstup SweepEngineV2.decide() pre jeden ťah."""
    certainty: str       # "PROVEN_CERTAIN" | "PROVEN_IMPOSSIBLE" | "UNRESOLVED"
    decision: str         # "COMMIT" | "ABANDON" | "WATCH"
    card: Card | None = None
    confidence: float = 0.0
    strategy_used: str | None = None
    sources: list[PenaltySource] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
