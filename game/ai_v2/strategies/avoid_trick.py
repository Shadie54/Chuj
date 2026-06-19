# game/ai_v2/strategies/avoid_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class AvoidTrick(Strategy):
    name = "AvoidTrick"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.is_void:
            return False
        if not ctx.lead_cards:
            return False

        non_certain = [
            c for c in ctx.lead_cards
            if not c.is_special
               and card_outcome(
                   c, ctx.decision.trick,
                   self.memory, ctx.decision.players_after
               ) != TrickOutcome.CERTAIN
        ]
        if not non_certain:
            return False

        if ctx.current_best:
            can_underplay = any(
                c.rank_order < ctx.current_best.rank_order
                for c in non_certain
            )
            if can_underplay:
                return True

        has_safe = any(self._is_safe(c, ctx) for c in non_certain)
        if has_safe:
            return True

        if self._can_risk_pick(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []

        dump_ak = self._dump_ak_free(ctx)
        for card in dump_ak:
            results.append((card, "DUMP_AK_FREE", f"{card}"))

        risk = self._risk_pick_cards(ctx)
        valid_risk = [
            c for c in risk
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) != TrickOutcome.CERTAIN
        ]
        for card in valid_risk:
            results.append((card, "RISK_PICK", f"{card}"))

        if ctx.current_best:
            underplay = [
                c for c in ctx.lead_cards
                if c.rank_order < ctx.current_best.rank_order
                   and not c.is_special
            ]
            if underplay:
                max_rank = max(c.rank_order for c in underplay)
                for card in [c for c in underplay if c.rank_order == max_rank]:
                    results.append((card, "UNDERPLAY", f"{card}"))

        if not results:
            safe = [
                c for c in ctx.lead_cards
                if self._is_safe(c, ctx)
                   and card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if safe:
                min_rank = min(c.rank_order for c in safe)
                for card in [c for c in safe if c.rank_order == min_rank]:
                    results.append((card, "UNDERPLAY", f"safe: {card}"))

        return results

    def _dump_ak_free(self, ctx: AIContext) -> list[Card]:
        if ctx.lead_suit not in ("leaf", "acorn"):
            return []
        if self.memory.is_special_gone(ctx.lead_suit):
            return []

        illuminator = self.memory.illuminated_by[ctx.lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return []

        played_indices = {idx for idx, _ in ctx.decision.trick.played_cards}
        if illuminator not in played_indices:
            return []

        special_in_trick = any(c.is_special for c in ctx.trick_cards)
        if special_in_trick:
            return []

        other_suit = "acorn" if ctx.lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            other_holders = ctx.decision.special_holders.get(other_suit, set())
            for player_idx in ctx.decision.players_after:
                is_void_lead = ctx.lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return []

        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if not high:
            return []
        max_rank = max(c.rank_order for c in high)
        return [c for c in high if c.rank_order == max_rank]

    def _can_risk_pick(self, ctx: AIContext) -> bool:
        suit = ctx.lead_suit
        if suit is None:
            return False
        if suit in self.memory.suits_led:
            return False

        if ctx.current_best:
            my_highest = max(
                (c for c in ctx.lead_cards if not c.is_special),
                key=lambda c: c.rank_order,
                default=None
            )
            if my_highest and my_highest.rank_order < ctx.current_best.rank_order:
                return False

        remaining = len(self.memory.remaining[suit])
        return remaining >= 5

    def _risk_pick_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_risk_pick(ctx):
            return []

        suit = ctx.lead_suit
        suit_cards = [c for c in ctx.lead_cards if not c.is_special]

        if suit in ("leaf", "acorn"):
            suit_cards = [c for c in suit_cards if c.rank not in ("ace", "king")]

        if not suit_cards:
            return []

        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ])
        remaining = len(self.memory.remaining[suit])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ]

        return self._risk_pick_matrix(suit_cards, my_count, remaining, all_in_hand, ctx)

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> list[Card]:
        def safe_or_lowest() -> list[Card]:
            safe = [c for c in suit_cards if self._is_safe(c, ctx)]
            pool = safe if safe else suit_cards
            min_rank = min(c.rank_order for c in pool)
            return [c for c in pool if c.rank_order == min_rank]

        def mid_cards() -> list[Card]:
            if not all_in_hand:
                return []
            highest = max(all_in_hand, key=lambda c: c.rank_order)
            candidates = [
                c for c in suit_cards
                if highest.rank_order - c.rank_order >= 2
            ]
            if not candidates:
                return []
            max_rank = max(c.rank_order for c in candidates)
            return [c for c in candidates if c.rank_order == max_rank]

        if remaining >= 5:
            if my_count <= 2:
                max_rank = max(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == max_rank]
            elif my_count == 3:
                mid = mid_cards()
                if mid:
                    return mid
                min_rank = min(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == min_rank]
            else:
                return safe_or_lowest()
        else:
            if my_count <= 2:
                mid = mid_cards()
                if mid:
                    return mid
                min_rank = min(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == min_rank]
            else:
                return safe_or_lowest()

    def weight(self, ctx: AIContext) -> float:
        return 5.0