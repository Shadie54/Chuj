# game/ai_v2/strategies/force_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class ForceSpecial(Strategy):
    name = "ForceSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False

        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            holders = ctx.decision.special_holders.get(suit, set())
            if not holders:
                continue
            if self.player.index in holders:
                continue
            if self._forcing_cards(suit, ctx):
                return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            holders = ctx.decision.special_holders.get(suit, set())
            if not holders or self.player.index in holders:
                continue

            forcing = self._forcing_cards(suit, ctx)
            if not forcing:
                continue

            cards = self._aggressive_cards(forcing, suit, ctx)
            for card in cards:
                results.append((card, "FORCE", f"vytiahni horníka {suit}: {card}"))

        return results

    def _forcing_cards(self, suit: str, ctx: AIContext) -> list[Card]:
        suit_cards = [
            c for c in ctx.playable
            if c.suit == suit and not c.is_special and c.rank not in ("ace", "king")
        ]
        if not suit_cards:
            return []

        remaining_non_ak = [
            c for c in suit_cards
            if c != min(suit_cards, key=lambda c: c.rank_order)
        ]
        high_cards = [
            c for c in ctx.playable
            if c.suit == suit and not c.is_special and c.rank in ("ace", "king")
        ]
        if not remaining_non_ak and high_cards:
            return []

        return [
            c for c in suit_cards
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) == TrickOutcome.UNKNOWN
        ]

    def _aggressive_cards(self, suit_cards: list[Card],
                          suit: str, ctx: AIContext) -> list[Card]:
        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ])
        remaining = len(self.memory.remaining[suit])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ]

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

        def by_extreme(pick_max: bool) -> list[Card]:
            target = max(c.rank_order for c in suit_cards) if pick_max \
                else min(c.rank_order for c in suit_cards)
            return [c for c in suit_cards if c.rank_order == target]

        if remaining >= 5:
            if my_count <= 2:
                return by_extreme(pick_max=True)
            elif my_count == 3:
                mid = mid_cards()
                return mid if mid else by_extreme(pick_max=False)
            else:
                return by_extreme(pick_max=False)
        else:
            if my_count <= 2:
                mid = mid_cards()
                return mid if mid else by_extreme(pick_max=False)
            else:
                return by_extreme(pick_max=False)

    def weight(self, ctx: AIContext) -> float:
        return 8.0