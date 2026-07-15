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
        if self._protected_last_resort(ctx):
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

        escape = [c for c in self._escape_candidates(ctx) if c not in bell]
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

        if not results:
            suit_picks = self._protected_last_resort(ctx)
            if suit_picks:
                # Farba s viac rezervami = primárna (vyššia váha)
                best_suit = max(suit_picks, key=lambda s: self._last_resort_reserves[s])
                for suit, cards in suit_picks.items():
                    variant = "PROTECTED_ESCAPE_PRIMARY" if suit == best_suit else "PROTECTED_ESCAPE_SECONDARY"
                    for card in cards:
                        results.append(
                            (card, variant, f"núdzovo {suit} (rezervy={self._last_resort_reserves[suit]}): {card}"))

        return results

    def _worst_case_dangerous(self, suit: str, ctx: AIContext) -> bool:
        """
        True ak existuje INÁ horníková farba, ktorá ešte nepadla
        a ja horníka tejto inej farby nemám v ruke.
        """
        hand = self.player.hand.cards
        other_suit = "acorn" if suit == "leaf" else "leaf"
        if self.memory.is_special_gone(other_suit):
            return False
        if any(c.is_special and c.suit == other_suit for c in hand):
            return False
        return True

    def _protected_last_resort(self, ctx: AIContext) -> dict[str, list[Card]]:
        """
        Núdzová voľba, ak sú všetky escape/exhaust/bell kandidáti vetované
        cez protected_suits. Vráti kandidátov za KAŽDÚ protected farbu
        (nie len jednu) — výber medzi farbami sa rieši cez váhy v propose().
        """
        suit_picks = {}
        self._last_resort_reserves = {}
        for suit in ctx.decision.protected_suits:
            suit_cards = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            if not suit_cards:
                continue

            my_count = len(suit_cards)
            remaining = len(self.memory.remaining[suit])
            aggressive = not self._worst_case_dangerous(suit, ctx)

            picked = self._risk_pick_matrix(
                suit_cards, my_count, remaining, suit_cards, ctx,
                aggressive=aggressive
            )
            if picked:
                suit_picks[suit] = picked
                self._last_resort_reserves[suit] = my_count

        return suit_picks

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
            if remaining >= 5 and my_count <= 2:
                max_rank = max(c.rank_order for c in non_trap_bell)
                return [c for c in non_trap_bell if c.rank_order == max_rank]
            cards = self._simple_median(all_in_hand)
            cards = [c for c in cards if c in non_trap_bell]
            if cards:
                return cards
            cards = self._simple_median(non_trap_bell)
            if cards:
                return cards

        if trap_bell and my_count <= 2 and remaining >= 5:
            max_rank = max(c.rank_order for c in trap_bell)
            return [c for c in trap_bell if c.rank_order == max_rank]

        return []

    def _escape_candidates(self, ctx: AIContext) -> list[Card]:
        hand = self.player.hand.cards
        candidates = []
        first_trick = ctx.decision.hand_eval.tricks_remaining == 8

        for c in ctx.decision.hand_eval.escape_cards:
            if c.suit == "heart" and first_trick:
                continue
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
                          ctx: AIContext,
                          aggressive: bool = False) -> list[Card]:
        if not suit_cards:
            return []

        def safe_or_lowest() -> list[Card]:
            safe = [c for c in suit_cards if self._is_safe(c, ctx)]
            pool = safe if safe else suit_cards
            min_rank = min(c.rank_order for c in pool)
            return [c for c in pool if c.rank_order == min_rank]

        def median_card() -> list[Card]:
            sorted_cards = sorted(suit_cards, key=lambda c: c.rank_order)
            n = len(sorted_cards)
            if n % 2 == 1:
                idx = n // 2
            else:
                # párny počet: aggressive → horný medián, inak dolný
                idx = n // 2 if aggressive else n // 2 - 1
            target_rank = sorted_cards[idx].rank_order
            return [c for c in sorted_cards if c.rank_order == target_rank]

        def max_cards() -> list[Card]:
            max_rank = max(c.rank_order for c in suit_cards)
            return [c for c in suit_cards if c.rank_order == max_rank]

        if remaining >= 5:
            if my_count <= 2:
                return max_cards()
            elif my_count == 3:
                if aggressive:
                    return max_cards()
                return median_card()
            else:
                if aggressive:
                    return median_card()
                return safe_or_lowest()
        else:
            if my_count <= 2:
                if aggressive:
                    return max_cards()
                return median_card()
            else:
                if aggressive:
                    return median_card()
                return safe_or_lowest()

    @staticmethod
    def _simple_median(cards: list[Card]) -> list[Card]:
        """
        Jednoduchý medián zo všetkých kariet danej farby (bell, heart).
        Žiadne trap/escape rozlišovanie, žiadny worst-case posun.
        """
        if not cards:
            return []
        sorted_cards = sorted(cards, key=lambda c: c.rank_order)
        n = len(sorted_cards)
        idx = n // 2 if n % 2 == 1 else n // 2 - 1
        target_rank = sorted_cards[idx].rank_order
        return [c for c in sorted_cards if c.rank_order == target_rank]

    def weight(self, ctx: AIContext) -> float:
        return 6.0

    def variant_weight(self, variant: str, ctx: AIContext) -> float:
        if variant == "BELL_ESCAPE":
            if ctx.decision.hand_eval.tricks_remaining == 8:
                return 8.0
            return 6.0
        if variant == "HIGH_SCORE":
            return 7.0
        if variant == "PROTECTED_ESCAPE_PRIMARY":
            return 4.0
        if variant == "PROTECTED_ESCAPE_SECONDARY":
            return 3.0
        return self.weight(ctx)