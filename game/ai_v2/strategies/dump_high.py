# game/ai_v2/strategies/dump_high.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class DumpHigh(Strategy):
    name = "DumpHigh"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if not ctx.is_void:
            return False
        if ctx.trick_outcome == TrickOutcome.NEVER:
            return False
        return bool(self._candidates(ctx))

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        candidates = self._candidates(ctx)
        if not candidates:
            return []
        max_rank = max(c.rank_order for c in candidates)
        top = [c for c in candidates if c.rank_order == max_rank]
        return [(card, "HIGH_CARD", f"{card}") for card in top]

    @staticmethod
    def _candidates(ctx: AIContext) -> list[Card]:
        return [
            c for c in ctx.playable
            if not c.is_special and c.suit != "heart"
        ]

    def weight(self, ctx: AIContext) -> float:
        return 2.0