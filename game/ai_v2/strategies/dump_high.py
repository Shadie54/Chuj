# game/ai_v2/strategies/dump_high.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class DumpHigh(Strategy):
    """
    Zbav sa najvyššej dostupnej karty keď som void.
    Posledná možnosť pred globálnym fallbackom.

    Varianty:
    - HIGH_CARD — najvyššia non-special non-heart karta
    """

    name = "DumpHigh"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if not ctx.is_void:
            return False
        if ctx.trick_outcome == TrickOutcome.NEVER:
            return False
        return bool(self._candidates(ctx))

    def propose(self, ctx: AIContext) -> Card | None:
        candidates = self._candidates(ctx)
        if not candidates:
            return None
        card = max(candidates, key=lambda c: c.rank_order)
        self._set_log("HIGH_CARD", f"{card}")
        return card

    @staticmethod
    def _candidates(ctx: AIContext) -> list[Card]:
        """Non-special, non-heart karty."""
        return [
            c for c in ctx.playable
            if not c.is_special
               and c.suit != "heart"
        ]

    def weight(self, ctx: AIContext) -> float:
        return 2.0