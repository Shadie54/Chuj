# game/ai_v2/strategies/dump_heart.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpHeart(Strategy):
    """
    Zbav sa červene.

    Varianty:
    - VOID      — som void na lead suit, hodím červeň
    - UNDERPLAY — červeň podlieza current_best

    Kontext (ovplyvňuje váhu):
    - is_high_score      → vyššia váha
    - both_illuminated   → ešte vyššia váha (červene = 2b každá)
    """

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

    def propose(self, ctx: AIContext) -> Card | None:
        hearts = [c for c in ctx.playable if c.suit == "heart"]
        if not hearts:
            return None

        # Void → najlepšia červeň
        if ctx.is_void:
            card = self._best_heart(hearts, ctx)
            self._set_log("VOID", f"{card}")
            return card

        # Underplay → červeň ktorá podlieza a dáva NEVER
        if ctx.current_best:
            underplay = [
                c for c in hearts
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if underplay:
                card = self._best_heart(underplay, ctx)
                self._set_log("UNDERPLAY", f"{card} podlieza {ctx.current_best}")
                return card

        return None

    def _best_heart(self, hearts: list[Card], ctx: AIContext) -> Card:
        """
        Vyber najlepšiu červeň na zahodenie.
        Priorita: trap → non-safe → safe
        """
        trap = [c for c in hearts if self._is_trap(c, ctx)]
        if trap:
            return max(trap, key=lambda c: c.rank_order)

        non_safe = [c for c in hearts if not self._is_safe(c, ctx)]
        if non_safe:
            return max(non_safe, key=lambda c: c.rank_order)

        return max(hearts, key=lambda c: c.rank_order)

    def _both_illuminated(self) -> bool:
        return (
            self.memory.illuminated_by["leaf"] is not None
            and self.memory.illuminated_by["acorn"] is not None
        )

    def weight(self, ctx: AIContext) -> float:
        """
        Váha DumpHeart.
        Štandard: nižšia ako DumpSpecial (horníci > červene).
        Pri 90+: vyššia ako DumpSpecial (červene > horníci).
        Both illuminated: ešte vyššia (červene = 2b každá).
        """
        if ctx.is_high_score:
            if self._both_illuminated():
                return 10.0
            return 7.0
        return 5.0