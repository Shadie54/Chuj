# game/ai_v2/strategies/wait.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class Wait(Strategy):
    """
    Zahrám nízku escape kartu a čakám — niekto po mne môže prebiť.

    Varianty:
    - WAIT — najnižšia escape karta
    """

    name = "Wait"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_void:
            return False
        if ctx.is_last:
            return False
        if not ctx.lead_cards:
            return False

        # Aktivuj len ak mám escape kartu ktorá dáva NEVER/UNKNOWN
        escape = self._escape_candidates(ctx)
        return bool(escape)

    def propose(self, ctx: AIContext) -> Card | None:
        escape = self._escape_candidates(ctx)
        if not escape:
            return None

        card = min(escape, key=lambda c: c.rank_order)
        self._set_log("WAIT", f"escape: {card}")
        return card

    def _escape_candidates(self, ctx: AIContext) -> list[Card]:
        """Escape karty kde card_outcome != CERTAIN."""
        candidates = []
        for c in ctx.lead_cards:
            if c.is_special:
                continue
            if self._is_safe(c, ctx):
                continue
            if self._is_trap(c, ctx):
                continue
            outcome = card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome != TrickOutcome.CERTAIN:
                candidates.append(c)
        return candidates

    def weight(self, ctx: AIContext) -> float:
        return 5.0