# game/ai_v2/strategies/risk_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class RiskSpecial(Strategy):
    """
    Riskni horníka ako leader — vediem horníkom v nádeji že súper zoberie.

    Varianty:
    - RISK — vediem horníkom, vonku existuje vyššia non-special karta
    """

    name = "RiskSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False

        return bool(self._risk_candidates(ctx))

    def propose(self, ctx: AIContext) -> Card | None:
        candidates = self._risk_candidates(ctx)
        if not candidates:
            return None

        # Vyber horníka s najvyššou bodovou hodnotou
        card = max(candidates, key=lambda c: self._special_points(c))
        self._set_log("RISK", f"{card} — vonku vyššia non-special")
        return card

    def _risk_candidates(self, ctx: AIContext) -> list[Card]:
        candidates = []

        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue

            special = next(
                (c for c in ctx.playable
                 if c.is_special and c.suit == suit), None
            )
            if special is None:
                continue

            # Remaining threshold
            if len(self.memory.remaining[suit]) > 4:
                continue

            # Len A/K ako non-special v tej farbe
            suit_cards = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            if not suit_cards:
                continue
            all_high = all(
                c.rank in ("ace", "king") for c in suit_cards
            )
            if not all_high:
                continue

            # Vonku existuje vyššia non-special
            remaining_higher = [
                c for c in self.memory.remaining[suit]
                if c.rank_order > special.rank_order
                   and not c.is_special
            ]
            if not remaining_higher:
                continue

            # card_outcome musí byť UNKNOWN — niekto môže prebiť
            outcome = card_outcome(
                special, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome != TrickOutcome.UNKNOWN:
                continue

            candidates.append(special)

        return candidates

    def weight(self, ctx: AIContext) -> float:
        """
        Stredná váha — nižšia ako LeadSafe.
        LeadSafe má prednosť ak má kandidáta.
        """
        return 4.0