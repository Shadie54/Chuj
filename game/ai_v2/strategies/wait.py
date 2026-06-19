# game/ai_v2/strategies/wait.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class Wait(Strategy):
    name = "Wait"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_void:
            return False
        if ctx.is_last:
            return False
        if not ctx.lead_cards:
            return False

        escape = self._escape_candidates(ctx)
        return bool(escape)

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        escape = self._escape_candidates(ctx)
        if not escape:
            return []
        min_rank = min(c.rank_order for c in escape)
        bottom = [c for c in escape if c.rank_order == min_rank]
        return [(card, "WAIT", f"escape: {card}") for card in bottom]

    def _escape_candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []
        for c in ctx.lead_cards:
            if c.is_special:
                continue
            if self._is_safe(c, ctx):
                continue
            if self._is_trap(c, ctx):
                continue
            outcome = card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome != TrickOutcome.CERTAIN:
                candidates.append(c)
        return candidates

    def weight(self, ctx: AIContext) -> float:
        return 5.0