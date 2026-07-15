# game/ai_v2/strategies/accept_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class AcceptTrick(Strategy):
    name = "AcceptTrick"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.is_void:
            return False
        if not ctx.lead_cards:
            return False

        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            if ctx.current_best and ctx.current_best.is_special:
                non_special = [c for c in ctx.lead_cards if not c.is_special]
                has_never = any(
                    card_outcome(
                        c, ctx.decision.trick,
                        self.memory, ctx.decision.players_after
                    ) == TrickOutcome.NEVER
                    for c in non_special
                )
                if not has_never and not self._has_alternative(ctx):
                    return True
            elif not self._has_alternative(ctx):
                return True

        if self._can_early_take(ctx):
            return True

        if self._can_free_take(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []

        if ctx.trick_outcome == TrickOutcome.CERTAIN and not self._has_alternative(ctx):
            certain_cards = [
                c for c in ctx.lead_cards
                if not c.is_special
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.CERTAIN
            ]
            if not certain_cards:
                certain_cards = [
                    c for c in ctx.lead_cards
                    if card_outcome(
                        c, ctx.decision.trick,
                        self.memory, ctx.decision.players_after
                    ) == TrickOutcome.CERTAIN
                ]
            if certain_cards:
                if not ctx.trick_has_penalty:
                    results += self._forced_clean(ctx, certain_cards)
                else:
                    results += self._forced_points(ctx, certain_cards)
                return results

        free = self._free_take_cards(ctx)
        if free:
            for card in free:
                results.append((card, "FREE_TAKE", f"dump A/K illuminator hral: {card}"))
            return results

        early = self._early_take_cards(ctx)
        if early:
            for card in early:
                results.append((card, "EARLY_TAKE", f"bell risk_pick: {card}"))
            return results

        return results

    def _has_alternative(self, ctx: AIContext) -> bool:
        non_special = [c for c in ctx.lead_cards if not c.is_special]
        for c in non_special:
            outcome = card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if ctx.is_last:
                if ctx.decision.trick.total_base_points > 2 and outcome == TrickOutcome.NEVER:
                    return True
                if outcome == TrickOutcome.UNKNOWN:
                    return True
            else:
                if outcome != TrickOutcome.CERTAIN:
                    return True
        return False

    def _forced_clean(self, ctx: AIContext,
                      certain_cards: list[Card]) -> list[tuple[Card, str, str]]:
        results = []
        if ctx.is_last:
            traps = [c for c in certain_cards if self._is_trap(c, ctx)]
            if traps:
                max_rank = max(c.rank_order for c in traps)
                for card in [c for c in traps if c.rank_order == max_rank]:
                    results.append((card, "FORCED_CLEAN", f"dump trap: {card}"))
                return results

        max_rank = max(c.rank_order for c in certain_cards)
        for card in [c for c in certain_cards if c.rank_order == max_rank]:
            results.append((card, "FORCED_CLEAN", f"najvyššia lead: {card}"))
        return results

    @staticmethod
    def _forced_points(ctx: AIContext,
                       certain_cards: list[Card]) -> list[tuple[Card, str, str]]:
        results = []
        if ctx.is_last:
            target = max(c.rank_order for c in certain_cards)
            label = "posledný max"
        else:
            target = min(c.rank_order for c in certain_cards)
            label = "min škoda"
        for card in [c for c in certain_cards if c.rank_order == target]:
            results.append((card, "FORCED_POINTS", f"{label}: {card}"))
        return results

    def _can_early_take(self, ctx: AIContext) -> bool:
        if ctx.is_last:
            return False
        if ctx.lead_suit != "bell":
            return False
        if ctx.trick_has_penalty:
            return False
        bell_cards = [c for c in ctx.lead_cards if not c.is_special]
        if len(bell_cards) < 2:
            return False
        if "bell" in self.memory.suits_led:
            return False
        if len(self.memory.remaining["bell"]) < 5:
            return False
        if ctx.current_best:
            can_win = any(
                c.rank_order > ctx.current_best.rank_order
                for c in bell_cards
            )
            if not can_win:
                return False
        return True

    def _early_take_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_early_take(ctx):
            return []

        bell_cards = [c for c in ctx.lead_cards if not c.is_special]
        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ])
        remaining = len(self.memory.remaining["bell"])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ]

        cards = self._risk_pick_matrix(bell_cards, my_count, remaining, all_in_hand, ctx)
        if not cards:
            max_rank = max(c.rank_order for c in bell_cards)
            cards = [c for c in bell_cards if c.rank_order == max_rank]

        if ctx.current_best:
            valid = [c for c in cards if c.rank_order >= ctx.current_best.rank_order]
            if not valid:
                underplay = [
                    c for c in bell_cards
                    if c.rank_order < ctx.current_best.rank_order
                ]
                if underplay:
                    max_rank = max(c.rank_order for c in underplay)
                    return [c for c in underplay if c.rank_order == max_rank]
                return []
            return valid
        return cards

    def _can_free_take(self, ctx: AIContext) -> bool:
        if ctx.lead_suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(ctx.lead_suit):
            return False

        illuminator = self.memory.illuminated_by[ctx.lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return False

        played_indices = {idx for idx, _ in ctx.decision.trick.played_cards}
        if illuminator not in played_indices:
            return False

        special_in_trick = any(c.is_special for c in ctx.trick_cards)
        if special_in_trick:
            return False

        other_suit = "acorn" if ctx.lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            other_holders = ctx.decision.special_holders.get(other_suit, set())
            for player_idx in ctx.decision.players_after:
                is_void_lead = ctx.lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return False

        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        return bool(high)

    def _free_take_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_free_take(ctx):
            return []
        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if not high:
            return []
        max_rank = max(c.rank_order for c in high)
        return [c for c in high if c.rank_order == max_rank]

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> list[Card]:
        if not suit_cards:
            return []

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
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            return 8.0
        return 5.0