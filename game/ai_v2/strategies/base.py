# game/ai_v2/strategies/base.py

from abc import ABC, abstractmethod
from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_v2.context import AIContext


class Strategy(ABC):
    def __init__(self, player: Player, memory: AIMemory):
        self.player = player
        self.memory = memory

    @abstractmethod
    def is_active(self, ctx: AIContext) -> bool:
        ...

    @abstractmethod
    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        """
        Vráti zoznam kandidátov: (card, variant, detail).
        Prázdny zoznam ak žiadny kandidát.
        """
        ...

    @abstractmethod
    def weight(self, ctx: AIContext) -> float:
        ...

    def variant_weight(self, variant: str, ctx: AIContext) -> float:
        """
        Váha pre konkrétny variant. Default — rovnaká pre všetky varianty
        danej stratégie (volá weight()). Stratégie s rozdielnymi váhami
        per variant túto metódu override-ujú.
        """
        return self.weight(ctx)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    # ------------------------------------------------------------------
    # Zdieľané pomocné metódy pre všetky stratégie
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_best(ctx: AIContext) -> Card | None:
        return ctx.current_best

    def _is_trap(self, card: Card, ctx: AIContext) -> bool:
        higher_remaining = [
            c for c in self.memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        higher_in_trick = [
            c for c in ctx.trick_cards
            if c.suit == card.suit and c.rank_order > card.rank_order
        ]
        higher_own = [
            c for c in self.player.hand.cards
            if c.suit == card.suit
               and c.rank_order > card.rank_order
               and c != card
        ]
        return not higher_remaining and not higher_in_trick and not higher_own

    @staticmethod
    def _is_safe(card: Card, ctx: AIContext) -> bool:
        profile = ctx.decision.hand_eval.profiles.get(card.suit)
        if profile:
            return card in profile.safe_cards
        return False

    def _special_points(self, card: Card) -> int:
        if card.is_leaf_over:
            illuminated = self.memory.illuminated_by["leaf"] is not None
            return 16 if illuminated else 8
        if card.is_acorn_over:
            illuminated = self.memory.illuminated_by["acorn"] is not None
            return 8 if illuminated else 4
        return 0