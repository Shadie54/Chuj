# game/ai_v2/strategies/avoid_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class AvoidTrick(Strategy):
    """
    Vyhni sa štichu — podliezaj, zbavuj sa kariet kým niekto iný berie.

    Varianty:
    - UNDERPLAY           — podliezam current_best, max(underplay)
    - DUMP_SPECIAL        — horník podlieza current_best, zahodím ho
    - DUMP_AK_FREE        — illuminator hral, bezpečne zahodím A/K
    - RISK_PICK           — vyššia karta podľa matice (farba nešla + nízke void riziko)
    """

    name = "AvoidTrick"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            return False
        if ctx.is_void:
            return False
        if not ctx.lead_cards:
            return False

        # Viem podliezť alebo mám safe kartu
        if ctx.current_best:
            can_underplay = any(
                c.rank_order < ctx.current_best.rank_order
                for c in ctx.lead_cards
            )
            if can_underplay:
                return True

        has_safe = any(self._is_safe(c, ctx) for c in ctx.lead_cards)
        if has_safe:
            return True

        # Risk pick — farba nešla + nízke void riziko
        if self._can_risk_pick(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> Card | None:
        # DUMP_AK_FREE
        dump_ak = self._dump_ak_free(ctx)
        if dump_ak:
            self._set_log("DUMP_AK_FREE", f"{dump_ak}")
            return dump_ak

        # RISK_PICK — farba nešla + nízke void riziko
        risk = self._risk_pick_card(ctx)
        if risk:
            # Vylúč ak card_outcome == CERTAIN
            outcome = card_outcome(
                risk, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome != TrickOutcome.CERTAIN:
                self._set_log("RISK_PICK", f"{risk}")
                return risk

        # UNDERPLAY — len karty kde card_outcome != CERTAIN
        if ctx.current_best:
            underplay = [
                c for c in ctx.lead_cards
                if c.rank_order < ctx.current_best.rank_order
                   and not c.is_special
            ]
            if underplay:
                card = max(underplay, key=lambda c: c.rank_order)
                self._set_log("UNDERPLAY", f"{card}")
                return card

        # Safe karta — card_outcome == NEVER garantovane
        safe = [
            c for c in ctx.lead_cards
            if self._is_safe(c, ctx)
               and card_outcome(c, ctx.decision.trick,
                                self.memory, ctx.decision.players_after
                                ) == TrickOutcome.NEVER
        ]
        if safe:
            card = min(safe, key=lambda c: c.rank_order)
            self._set_log("UNDERPLAY", f"safe: {card}")
            return card

        return None

    def _dump_ak_free(self, ctx: AIContext) -> Card | None:
        """
        Illuminator už hral a nezahral horníka → bezpečne zahodím A/K.
        """
        if ctx.lead_suit not in ("leaf", "acorn"):
            return None
        if self.memory.is_special_gone(ctx.lead_suit):
            return None

        illuminator = self.memory.illuminated_by[ctx.lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return None

        played_indices = {idx for idx, _ in ctx.decision.trick.played_cards}
        if illuminator not in played_indices:
            return None

        special_in_trick = any(
            c.is_special for c in ctx.trick_cards
        )
        if special_in_trick:
            return None

        # Skontroluj void riziko druhého horníka
        other_suit = "acorn" if ctx.lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            other_holders = ctx.decision.special_holders.get(other_suit, set())
            for player_idx in ctx.decision.players_after:
                is_void_lead = ctx.lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return None

        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if not high:
            return None
        return max(high, key=lambda c: c.rank_order)

    def _can_risk_pick(self, ctx: AIContext) -> bool:
        """Farba nešla + dostatok kariet v obehu → nízke void riziko."""
        suit = ctx.lead_suit
        if suit is None:
            return False
        if suit in self.memory.suits_led:
            return False
        # Veto — v štichu je už vyššia karta → nie je risk, je to underplay
        if ctx.current_best:
            my_highest = max(
                (c for c in ctx.lead_cards if not c.is_special),
                key=lambda c: c.rank_order,
                default=None
            )
            if my_highest and my_highest.rank_order < ctx.current_best.rank_order:
                return False
        # Veto — živý horník v tejto farbe a nemám ho ja
        if suit in ("leaf", "acorn"):
            if not self.memory.is_special_gone(suit):
                i_have_special = any(
                    c.is_special and c.suit == suit
                    for c in self.player.hand.cards
                )
                if not i_have_special:
                    return False
        remaining = len(self.memory.remaining[suit])
        return remaining >= 5

    def _risk_pick_card(self, ctx: AIContext) -> Card | None:
        """
        Výber karty podľa risk matice (remaining vs my_count).
        Aplikovateľné pre bell, leaf, acorn ak farba nešla.
        """
        if not self._can_risk_pick(ctx):
            return None

        suit = ctx.lead_suit
        suit_cards = [
            c for c in ctx.lead_cards
            if not c.is_special
        ]
        if not suit_cards:
            return None

        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ])
        remaining = len(self.memory.remaining[suit])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ]

        return self._risk_pick_matrix(
            suit_cards, my_count, remaining, all_in_hand, ctx
        )

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> Card | None:
        """
        Rozhodovacia matica: remaining vs my_count → výber karty.
        Čím viac kariet mám, tým vyššie void riziko u súperov → nižšia karta.
        """
        def safe_or_lowest() -> Card:
            safe = [c for c in suit_cards if self._is_safe(c, ctx)]
            pool = safe if safe else suit_cards
            return min(pool, key=lambda c: c.rank_order)

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
                return safe_or_lowest()
        else:
            if my_count <= 2:
                mid = mid_card()
                return mid if mid else min(suit_cards, key=lambda c: c.rank_order)
            else:
                return safe_or_lowest()

    def weight(self, ctx: AIContext) -> float:
        return 5.0