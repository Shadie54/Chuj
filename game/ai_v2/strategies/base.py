# game/ai_v2/strategies/base.py

from abc import ABC, abstractmethod
from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_v2.context import AIContext


class Strategy(ABC):
    """
    Základná trieda pre všetky stratégie AI v2.

    Každá stratégia:
    - Skontroluje podmienky aktivácie (is_active)
    - Navrhne kartu alebo None (propose)
    - Určí svoju váhu v danom kontexte (weight)
    - Vráti log string pre debugging (log_variant)
    """

    def __init__(self, player: Player, memory: AIMemory):
        self.player = player
        self.memory = memory
        self._last_variant: str = ""
        self._last_detail: str = ""

    @abstractmethod
    def is_active(self, ctx: AIContext) -> bool:
        """Podmienky aktivácie — kedy je táto stratégia relevantná."""
        ...

    @abstractmethod
    def propose(self, ctx: AIContext) -> Card | None:
        """Navrhni kartu alebo None ak nemá kandidáta."""
        ...

    @abstractmethod
    def weight(self, ctx: AIContext) -> float:
        """Váha stratégie v danom kontexte — pre súťaž medzi stratégiami."""
        ...

    @property
    def name(self) -> str:
        """Názov stratégie pre logy — override v podtriede."""
        return self.__class__.__name__

    def log_entry(self) -> str:
        """
        Vráti log string vo formáte: stratégia | variant | detail
        Volaj po propose() — _last_variant a _last_detail sú nastavené tam.
        """
        return f"{self.name} | {self._last_variant} | {self._last_detail}"

    def _set_log(self, variant: str, detail: str = ""):
        """Pomocná metóda — nastav log variant a detail."""
        self._last_variant = variant
        self._last_detail = detail

    # ------------------------------------------------------------------
    # Zdieľané pomocné metódy pre všetky stratégie
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_best(ctx: AIContext) -> Card | None:
        """Aktuálny víťaz štichu."""
        return ctx.current_best

    def _is_trap(self, card: Card, ctx: AIContext) -> bool:
        """
        Karta je trap — nikto vyšší vonku (remaining + trick + vlastná ruka).
        """
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
        """
        Karta je safe — všetci vonku sú vyšší → garantovane nezoberiem štich.
        """
        profile = ctx.decision.hand_eval.profiles.get(card.suit)
        if profile:
            return card in profile.safe_cards
        return False

    def _special_points(self, card: Card) -> int:
        """Body za horníka (s vysvietením)."""
        if card.is_leaf_over:
            illuminated = self.memory.illuminated_by["leaf"] is not None
            return 16 if illuminated else 8
        if card.is_acorn_over:
            illuminated = self.memory.illuminated_by["acorn"] is not None
            return 8 if illuminated else 4
        return 0