# game/ai_v2/strategies/force_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class ForceSpecial(Strategy):
    """
    Donúť súpera zahrať horníka — vedenie forcing kartou (7-J).

    Varianty:
    - FORCE — forcing karta podľa aggressive matice
    """

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
            # Ja nemám horníka
            if self.player.index in holders:
                continue
            if self._forcing_cards(suit, ctx):
                return True

        return False

    def propose(self, ctx: AIContext) -> Card | None:
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            holders = ctx.decision.special_holders.get(suit, set())
            if not holders or self.player.index in holders:
                continue

            forcing = self._forcing_cards(suit, ctx)
            if not forcing:
                continue

            card = self._aggressive_card(forcing, suit, ctx)
            self._set_log("FORCE", f"vytiahni horníka {suit}: {card}")
            return card

        return None

    def _forcing_cards(self, suit: str, ctx: AIContext) -> list[Card]:
        """
        Karty 7-J v danej farbe — nie A/K, nie special.
        Veto: po zahraní by ostali len A/K.
        Card_outcome musí byť UNKNOWN — forcing má zmysel len ak niekto môže prebiť.
        """
        suit_cards = [
            c for c in ctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank not in ("ace", "king")
        ]
        if not suit_cards:
            return []

        # Veto — po zahraní ostanú len A/K
        remaining_non_ak = [
            c for c in suit_cards
            if c != min(suit_cards, key=lambda c: c.rank_order)
        ]
        high_cards = [
            c for c in ctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank in ("ace", "king")
        ]
        if not remaining_non_ak and high_cards:
            return []

        # card_outcome musí byť UNKNOWN
        return [
            c for c in suit_cards
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) == TrickOutcome.UNKNOWN
        ]

    def _aggressive_card(self, suit_cards: list[Card],
                         suit: str, ctx: AIContext) -> Card:
        """
        Výber forcing karty podľa aggressive matice.
        remaining vs my_count → optimálna karta pre forcing.
        """
        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ])
        remaining = len(self.memory.remaining[suit])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ]

        def mid_card() -> Card | None:
            if not all_in_hand:
                return None
            highest = max(all_in_hand, key=lambda c: c.rank_order)
            candidates = [
                c for c in suit_cards
                if highest.rank_order - c.rank_order >= 2
            ]
            if not candidates:
                return None
            return max(candidates, key=lambda c: c.rank_order)

        if remaining >= 5:
            if my_count <= 2:
                return max(suit_cards, key=lambda c: c.rank_order)
            elif my_count == 3:
                mid = mid_card()
                return mid if mid else min(suit_cards, key=lambda c: c.rank_order)
            else:
                return min(suit_cards, key=lambda c: c.rank_order)
        else:
            if my_count <= 2:
                mid = mid_card()
                return mid if mid else min(suit_cards, key=lambda c: c.rank_order)
            else:
                return min(suit_cards, key=lambda c: c.rank_order)

    def weight(self, ctx: AIContext) -> float:
        """Vysoká váha vždy — forcing je dôležitý bez ohľadu na vysvietenie."""
        return 8.0