# game/ai_v2/strategies/dump_heart.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpHeart(Strategy):
    name = "DumpHeart"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.trick_outcome == TrickOutcome.NEVER:
            return False

        hearts = [c for c in ctx.playable if c.suit == "heart"]
        if not hearts:
            return False

        if ctx.is_void:
            return True

        if ctx.current_best:
            underplay = [
                c for c in hearts
                if c.rank_order < ctx.current_best.rank_order
            ]
            if underplay:
                return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []
        hearts = [c for c in ctx.playable if c.suit == "heart"]
        if not hearts:
            return results

        if ctx.is_void:
            for card in self._ranked_hearts(hearts, ctx):
                results.append((card, "VOID", f"{card}"))
            return results

        if ctx.current_best:
            underplay = [
                c for c in hearts
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.NEVER
            ]
            for card in self._ranked_hearts(underplay, ctx):
                results.append((
                    card, "UNDERPLAY", f"{card} podlieza {ctx.current_best}"
                ))

        return results

    def _ranked_hearts(self, hearts: list[Card], ctx: AIContext) -> list[Card]:
        """Vráti všetky karty na rovnakej prioritnej úrovni (trap > non-safe > safe)."""
        if not hearts:
            return []
        trap = [c for c in hearts if self._is_trap(c, ctx)]
        if trap:
            return trap
        non_safe = [c for c in hearts if not self._is_safe(c, ctx)]
        if non_safe:
            return non_safe
        return hearts

    def _both_illuminated(self) -> bool:
        return (
            self.memory.illuminated_by["leaf"] is not None
            and self.memory.illuminated_by["acorn"] is not None
        )

    def weight(self, ctx: AIContext) -> float:
        if ctx.is_high_score:
            if self._both_illuminated():
                return 10.0
            return 7.0
        return 5.0