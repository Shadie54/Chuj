# game/ai_v2/strategies/dump_dangerous.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpDangerous(Strategy):
    """
    Zbav sa nebezpečnej karty (nie horník, nie červeň).

    Varianty:
    - DANGER_TRAP — A/K v živej horník farbe (som v pasci)
    - TRAP        — akákoľvek trap karta non-heart, non-special
    """

    name = "DumpDangerous"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.trick_outcome == TrickOutcome.NEVER:
            return False
        if not ctx.is_void:
            return False
        if self._danger_trap_candidates(ctx):
            return True
        if self._trap_candidates(ctx):
            return True
        return False

    def propose(self, ctx: AIContext) -> Card | None:
        # DANGER_TRAP má prednosť
        danger = self._danger_trap_candidates(ctx)
        if danger:
            # Len karty kde card_outcome == NEVER (niekto iný berie)
            valid = [
                c for c in danger
                if card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if valid:
                card = max(valid, key=lambda c: c.rank_order)
                self._set_log("DANGER_TRAP", f"{card} — živý horník")
                return card

        # TRAP — všeobecný trap
        traps = self._trap_candidates(ctx)
        if traps:
            valid = [
                c for c in traps
                if card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if valid:
                card = max(valid, key=lambda c: c.rank_order)
                self._set_log("TRAP", f"{card}")
                return card

        return None

    def _danger_trap_candidates(self, ctx: AIContext) -> list[Card]:
        """
        A/K v leaf/acorn kde horník je živý a som v pasci
        (nemôžem pokryť všetky vyššie karty súperov).
        """
        candidates = []
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            suit_cards = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            if not suit_cards:
                continue

            remaining_non_special = [
                c for c in self.memory.remaining[suit]
                if not c.is_special
            ]
            my_non_special = [
                c for c in suit_cards
                if c.rank not in ("ace", "king")
            ]

            # Kontrola či som v pasci — nemôžem pokryť všetkých
            remaining_sorted = sorted(
                remaining_non_special,
                key=lambda c: c.rank_order, reverse=True
            )
            available = sorted(
                my_non_special,
                key=lambda c: c.rank_order, reverse=True
            )
            all_covered = True
            for their in remaining_sorted:
                match = next(
                    (c for c in available
                     if c.rank_order < their.rank_order), None
                )
                if match is None:
                    all_covered = False
                    break
                available.remove(match)

            if all_covered:
                continue

            candidates += [
                c for c in suit_cards
                if c.rank in ("ace", "king")
            ]

        return candidates

    def _trap_candidates(self, ctx: AIContext) -> list[Card]:
        """Akákoľvek trap karta non-heart, non-special."""
        return [
            c for c in ctx.playable
            if not c.is_special
               and c.suit != "heart"
               and self._is_trap(c, ctx)
        ]

    def weight(self, ctx: AIContext) -> float:
        """
        Váha DumpDangerous.
        Nižšia ako DumpSpecial a DumpHeart pri 90+,
        ale stále relevantná.
        """
        return 4.0