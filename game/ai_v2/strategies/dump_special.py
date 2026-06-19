# game/ai_v2/strategies/dump_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpSpecial(Strategy):
    name = "DumpSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False

        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return False

        if ctx.is_void:
            if ctx.trick_outcome == TrickOutcome.NEVER:
                return False
            return True

        if ctx.current_best:
            underplay_specials = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
            ]
            if underplay_specials:
                return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []
        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return results

        if ctx.is_high_score:
            return self._propose_high_score(ctx, specials)

        if ctx.is_void:
            for card in specials:
                results.append((
                    card, "VOID",
                    f"{card} ({self._special_points(card)}b)"
                ))
            return results

        if ctx.current_best:
            underplay = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.NEVER
            ]
            for card in underplay:
                results.append((
                    card, "UNDERPLAY",
                    f"{card} podlieza {ctx.current_best}"
                ))

        return results

    def _propose_high_score(self, ctx: AIContext,
                             specials: list[Card]) -> list[tuple[Card, str, str]]:
        results = []
        has_escape = any(
            c for c in ctx.playable
            if not c.is_special and not self._is_trap(c, ctx)
        )

        if not has_escape:
            if ctx.is_void:
                for card in specials:
                    results.append((
                        card, "IMMEDIATE_90", f"{card} — žiadna escape"
                    ))
                return results
            if ctx.current_best:
                underplay = [
                    c for c in specials
                    if c.rank_order < ctx.current_best.rank_order
                ]
                for card in underplay:
                    results.append((
                        card, "IMMEDIATE_90",
                        f"{card} podlieza — žiadna escape"
                    ))
                if results:
                    return results

        if ctx.is_void:
            for card in specials:
                results.append((
                    card, "VOID",
                    f"90+ {card} ({self._special_points(card)}b)"
                ))

        return results

    def weight(self, ctx: AIContext) -> float:
        if ctx.is_high_score:
            return 6.0
        return 9.0