# game/ai_v2/strategies/lead_safe.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class LeadSafe(Strategy):
    name = "LeadSafe"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False

        if ctx.is_high_score and self._surplus_low_hearts(ctx):
            return True
        if self._bell_escape_cards(ctx):
            return True
        if self._escape_candidates(ctx):
            return True
        if self._exhaust_candidates(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []

        if ctx.is_high_score:
            cards = self._surplus_low_hearts(ctx)
            for card in cards:
                results.append((card, "HIGH_SCORE", f"prebytočná nízka červeň: {card}"))

        bell = self._bell_escape_cards(ctx)
        for card in bell:
            results.append((card, "BELL_ESCAPE", f"{card}"))

        escape = self._escape_candidates(ctx)
        if escape:
            suits_present = set(c.suit for c in escape)
            for suit in suits_present:
                suit_escape = [c for c in escape if c.suit == suit]
                min_rank = min(c.rank_order for c in suit_escape)
                for card in [c for c in suit_escape if c.rank_order == min_rank]:
                    results.append((card, "ESCAPE", f"{suit}: {card}"))

        exhaust = self._exhaust_candidates(ctx)
        if exhaust:
            min_rank = min(c.rank_order for c in exhaust)
            for card in [c for c in exhaust if c.rank_order == min_rank]:
                results.append((card, "EXHAUST", f"{card}"))

        return results

    def _surplus_low_hearts(self, ctx: AIContext) -> list[Card]:
        hand = self.player.hand.cards
        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]

        surplus = len(low_hearts) - len(high_hearts)
        if surplus <= 0:
            return []

        playable_low = [
            c for c in ctx.playable
            if c.suit == "heart" and c.rank in ("seven", "eight", "nine")
        ]
        if not playable_low:
            return []
        max_rank = max(c.rank_order for c in playable_low)
        return [c for c in playable_low if c.rank_order == max_rank]

    def _bell_escape_cards(self, ctx: AIContext) -> list[Card]:
        if "bell" in self.memory.suits_led:
            return []

        all_bell = [
            c for c in ctx.playable
            if c.suit == "bell" and not c.is_special
        ]
        if not all_bell:
            return []

        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ])
        remaining = len(self.memory.remaining["bell"])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ]

        trap_bell = [c for c in all_bell if self._is_trap(c, ctx)]
        non_trap_bell = [c for c in all_bell if not self._is_trap(c, ctx)]

        if trap_bell and non_trap_bell:
            if remaining >= 5 and my_count <= 2:
                max_rank = max(c.rank_order for c in trap_bell)
                return [c for c in trap_bell if c.rank_order == max_rank]

        if my_count == 1:
            return all_bell

        if non_trap_bell:
            cards = self._risk_pick_matrix(non_trap_bell, my_count, remaining, all_in_hand, ctx)
            if cards:
                return cards

        if trap_bell and my_count <= 2 and remaining >= 5:
            max_rank = max(c.rank_order for c in trap_bell)
            return [c for c in trap_bell if c.rank_order == max_rank]

        return []

    def _escape_candidates(self, ctx: AIContext) -> list[Card]:
        hand = self.player.hand.cards
        candidates = []

        for c in ctx.decision.hand_eval.escape_cards:
            if c not in ctx.playable:
                continue
            if c.is_special:
                continue
            if c.suit in ctx.decision.protected_suits:
                continue
            if self._is_last_escape_dangerous(c, ctx):
                continue
            if c.rank in ("ace", "king") and c.suit in ("leaf", "acorn"):
                if not self.memory.is_special_gone(c.suit):
                    if not any(x.is_special and x.suit == c.suit for x in hand):
                        continue
            if c.suit in ("leaf", "acorn"):
                if any(x.is_special and x.suit == c.suit for x in hand):
                    if not self.memory.is_special_gone(c.suit):
                        non_special_playable = [
                            x for x in ctx.playable
                            if x.suit == c.suit and not x.is_special and x != c
                        ]
                        if not non_special_playable:
                            continue
            candidates.append(c)

        return candidates

    def _is_last_escape_dangerous(self, card: Card, ctx: AIContext) -> bool:
        suit = card.suit
        if suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(suit):
            return False
        holders = ctx.decision.special_holders.get(suit, set())
        if not holders:
            return False
        hand = self.player.hand.cards
        if any(c.is_special and c.suit == suit for c in hand):
            return False

        remaining_escapes = [
            c for c in ctx.playable
            if c.suit == suit and not c.is_special
               and c.rank not in ("ace", "king") and c != card
        ]
        high_cards = [
            c for c in ctx.playable
            if c.suit == suit and not c.is_special
               and c.rank in ("ace", "king") and self._is_trap(c, ctx)
        ]

        # Veto má zmysel len ak okrem horníka existuje ešte aspoň jedna
        # iná karta vonku — inak je horník neodvrátiteľný a trap je irelevantný
        other_cards_outside = [
            c for c in self.memory.remaining[suit]
            if not c.is_special
        ]
        if not other_cards_outside:
            return False

        return not remaining_escapes and bool(high_cards)

    def _exhaust_candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []
        for suit in ("leaf", "acorn"):
            if self.memory.illuminated_by[suit] != self.player.index:
                continue
            reserves = [
                c for c in self.player.hand.cards
                if c.suit == suit and not c.is_special
            ]
            if len(reserves) < 4:
                continue
            if any(c.rank in ("ace", "king") for c in reserves):
                continue
            suit_playable = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            candidates += suit_playable
        return candidates

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
        return 6.0

    def variant_weight(self, variant: str, ctx: AIContext) -> float:
        if variant == "BELL_ESCAPE":
            # Vyššia priorita v prvom štichu
            if ctx.decision.hand_eval.tricks_remaining == 8:
                return 8.0
            return 6.0
        if variant == "HIGH_SCORE":
            return 7.0
        return self.weight(ctx)  # ESCAPE, EXHAUST → default 6.0