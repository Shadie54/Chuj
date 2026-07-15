# game/ai_v2/strategies/risk_special.py

import random
from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class RiskSpecial(Strategy):
    name = "RiskSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return bool(self._risk_candidates(ctx))
        return self._should_risk_trap(ctx)

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        if ctx.is_leader:
            candidates = self._risk_candidates(ctx)
            if not candidates:
                return []
            max_pts = max(self._special_points(c) for c in candidates)
            top = [c for c in candidates if self._special_points(c) == max_pts]
            return [
                (card, "RISK", f"{card} — vonku vyššia non-special")
                for card in top
            ]

        if not self._should_risk_trap(ctx):
            return []
        trap_high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        card = max(trap_high, key=lambda c: c.rank_order)
        chance = self._risk_chance(ctx)
        return [(card, "RISK_TRAP", f"risk trap: {card} (P={chance})")]

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

    def _should_risk_trap(self, ctx: AIContext) -> bool:
        if ctx.is_last:
            return False
        if len(ctx.decision.players_after) != 1:
            return False
        if ctx.is_high_score:
            return False
        if 80 <= ctx.game.my_score <= 89:
            return False

        my_special = next((c for c in ctx.lead_cards if c.is_special), None)
        if my_special is not None:
            return False

        lead_suit = ctx.lead_suit
        if lead_suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(lead_suit):
            return False
        special_in_trick = any(
            c.is_special and c.suit == lead_suit
            for _, c in ctx.decision.trick.played_cards
        )
        if special_in_trick:
            return False
        if self.memory.illuminated_by[lead_suit] is not None:
            return False

        lead_cards = ctx.lead_cards
        trap_high = [
            c for c in lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        escape_low = [
            c for c in lead_cards
            if c.rank not in ("ace", "king") and not c.is_special
        ]
        if not trap_high or len(escape_low) != 1:
            return False

        my_best_trap = max(trap_high, key=lambda c: c.rank_order)
        higher_in_trick = any(
            c.suit == lead_suit and c.rank_order > my_best_trap.rank_order
            for _, c in ctx.decision.trick.played_cards
        )
        if higher_in_trick:
            return False

        return random.random() < self._risk_chance(ctx)

    @staticmethod
    def _risk_chance(self, ctx: AIContext) -> float:
        if len(set(ctx.all_scores)) == 1:
            return 0.5
        rank = ctx.game.score_rank
        if rank == 1:
            return 0.2
        elif rank == 4:
            return 0.7
        return 0.5

    def weight(self, ctx: AIContext) -> float:
        return 4.0

    def variant_weight(self, variant: str, ctx: AIContext) -> float:
        if variant == "RISK_TRAP":
            return 6.0
        return self.weight(ctx)