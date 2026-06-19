# game/ai_v2/strategies/risk_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class RiskSpecial(Strategy):
    name = "RiskSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False
        return bool(self._risk_candidates(ctx))

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        candidates = self._risk_candidates(ctx)
        if not candidates:
            return []
        max_pts = max(self._special_points(c) for c in candidates)
        top = [c for c in candidates if self._special_points(c) == max_pts]
        return [
            (card, "RISK", f"{card} — vonku vyššia non-special")
            for card in top
        ]

    def _risk_candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []

        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue

            special = next(
                (c for c in ctx.playable if c.is_special and c.suit == suit), None
            )
            if special is None:
                continue

            if len(self.memory.remaining[suit]) > 4:
                continue

            suit_cards = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            if not suit_cards:
                continue
            all_high = all(c.rank in ("ace", "king") for c in suit_cards)
            if not all_high:
                continue

            remaining_higher = [
                c for c in self.memory.remaining[suit]
                if c.rank_order > special.rank_order and not c.is_special
            ]
            if not remaining_higher:
                continue

            outcome = card_outcome(
                special, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome != TrickOutcome.UNKNOWN:
                continue

            candidates.append(special)

        return candidates

    def weight(self, ctx: AIContext) -> float:
        return 4.0