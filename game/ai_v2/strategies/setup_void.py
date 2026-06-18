# game/ai_v2/strategies/setup_void.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class SetupVoid(Strategy):
    """
    Priprav void do budúcna — zahrám jedinú kartu farby.

    Varianty:
    - SETUP — zahrám jedinú kartu farby → vytvorím void

    Podmienky per farba:
    - leaf/acorn: nie je trap ak je živý horník
    - bell:       zahrnieme (bell escape je iná logika)
    - heart:      len ak je nízka alebo safe karta
    """

    name = "SetupVoid"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False

        return bool(self._candidates(ctx))

    def propose(self, ctx: AIContext) -> Card | None:
        candidates = self._candidates(ctx)
        if not candidates:
            return None

        # Vyber prvého kandidáta — len jedna karta per farba
        card = candidates[0]
        self._set_log("SETUP", f"{card} → void {card.suit}")
        return card

    def _candidates(self, ctx: AIContext) -> list[Card]:
        """
        Nájdi karty kde mám presne 1 v danej farbe
        a spĺňajú podmienky per farba.
        """
        candidates = []
        hand = self.player.hand.cards

        for suit in ("bell", "leaf", "acorn", "heart"):
            suit_in_hand = [c for c in hand if c.suit == suit]
            if len(suit_in_hand) != 1:
                continue

            card = suit_in_hand[0]

            # Karta musí byť hrateľná
            if card not in ctx.playable:
                continue

            if suit in ("leaf", "acorn"):
                # Veto — trap karta ak je živý horník
                if not self.memory.is_special_gone(suit):
                    if self._is_trap(card, ctx):
                        continue

            elif suit == "heart":
                # Len nízka alebo safe karta
                if card.rank in ("ace", "king"):
                    continue
                # Ak nie je safe, musí byť nízka (7,8,9)
                if not self._is_safe(card, ctx):
                    if card.rank not in ("seven", "eight", "nine"):
                        continue

            # Bell — žiadne extra podmienky
            candidates.append(card)

        return candidates

    def weight(self, ctx: AIContext) -> float:
        """
        Stredná váha — dlhodobá stratégia.
        Nižšia ako dump stratégie a forcing.
        """
        return 3.0