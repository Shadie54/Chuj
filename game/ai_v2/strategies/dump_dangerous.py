# game/ai_v2/strategies/dump_dangerous.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpDangerous(Strategy):
    name = "DumpDangerous"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.trick_outcome == TrickOutcome.NEVER:
            return False
        if not ctx.is_void:
            return False

        if self._danger_trap_candidates(ctx):
            return True
        if self._trap_candidates(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []

        danger = self._danger_trap_candidates(ctx)
        valid_danger = [
            c for c in danger
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) == TrickOutcome.NEVER
        ]
        if valid_danger:
            for card in valid_danger:
                results.append((card, "DANGER_TRAP", f"{card} — živý horník"))
            return results

        traps = self._trap_candidates(ctx)
        valid_traps = [
            c for c in traps
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) == TrickOutcome.NEVER
        ]
        for card in valid_traps:
            results.append((card, "TRAP", f"{card}"))

        return results

    def _danger_trap_candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            suit_cards = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            if not suit_cards:
                continue

            remaining_non_special = [
                c for c in self.memory.remaining[suit] if not c.is_special
            ]
            my_non_special = [c for c in suit_cards if c.rank not in ("ace", "king")]

            remaining_sorted = sorted(
                remaining_non_special, key=lambda c: c.rank_order, reverse=True
            )
            available = sorted(my_non_special, key=lambda c: c.rank_order, reverse=True)
            all_covered = True
            for their in remaining_sorted:
                match = next(
                    (c for c in available if c.rank_order < their.rank_order), None
                )
                if match is None:
                    all_covered = False
                    break
                available.remove(match)

            if all_covered:
                continue

            candidates += [c for c in suit_cards if c.rank in ("ace", "king")]

        return candidates

    def _trap_candidates(self, ctx: AIContext) -> list[Card]:
        return [
            c for c in ctx.playable
            if not c.is_special
               and c.suit != "heart"
               and self._is_trap(c, ctx)
        ]

    def weight(self, ctx: AIContext) -> float:
        return 4.0