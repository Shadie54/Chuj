# game/ai_v2/strategies/setup_void.py

from game.card import Card
from game.ai_v2.context import AIContext
from game.ai_v2.strategies.base import Strategy


class SetupVoid(Strategy):
    name = "SetupVoid"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False
        return bool(self._candidates(ctx))

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        candidates = self._candidates(ctx)
        return [
            (card, "SETUP", f"{card} → void {card.suit}")
            for card in candidates
        ]

    def _candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []
        hand = self.player.hand.cards

        for suit in ("bell", "leaf", "acorn", "heart"):
            suit_in_hand = [c for c in hand if c.suit == suit]
            if len(suit_in_hand) != 1:
                continue

            card = suit_in_hand[0]
            if card not in ctx.playable:
                continue

            if suit in ("leaf", "acorn"):
                if not self.memory.is_special_gone(suit):
                    if self._is_trap(card, ctx):
                        continue

            elif suit == "heart":
                if card.rank in ("ace", "king"):
                    continue
                if not self._is_safe(card, ctx):
                    if card.rank not in ("seven", "eight", "nine"):
                        continue

            candidates.append(card)

        return candidates

    def weight(self, ctx: AIContext) -> float:
        return 3.0