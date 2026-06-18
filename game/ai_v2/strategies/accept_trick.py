# game/ai_v2/strategies/accept_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class AcceptTrick(Strategy):
    """
    Vedome ber štich — minimalizuj škodu alebo využi príležitosť.

    Varianty:
    - FORCED_CLEAN  — CERTAIN + čistý štich → dump max trap
    - FORCED_POINTS — CERTAIN + bodový štich → minimalizuj škodu
    - EARLY_TAKE    — bell čistý štich, 2./3. pozícia → risk_pick matica
    - FREE_TAKE     — illuminator hral → dump A/K
    """

    name = "AcceptTrick"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.is_void:
            return False
        if not ctx.lead_cards:
            return False
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            return True
        if self._can_early_take(ctx):
            return True
        if self._can_free_take(ctx):
            return True
        return False

    def propose(self, ctx: AIContext) -> Card | None:
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            certain_cards = [
                c for c in ctx.lead_cards
                if not c.is_special
                   and card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.CERTAIN
            ]
            # Ak nemáme non-special CERTAIN kartu,
            # skús aj špeciálne karty
            if not certain_cards:
                certain_cards = [
                    c for c in ctx.lead_cards
                    if card_outcome(
                        c, ctx.decision.trick,
                        self.memory, ctx.decision.players_after
                    ) == TrickOutcome.CERTAIN
                ]
            if not certain_cards:
                return None

            if not ctx.trick_has_penalty:
                return self._forced_clean(ctx, certain_cards)
            else:
                return self._forced_points(ctx, certain_cards)

        # FREE_TAKE
        if self._can_free_take(ctx):
            card = self._free_take(ctx)
            if card:
                return card

        # EARLY_TAKE
        if self._can_early_take(ctx):
            card = self._early_take(ctx)
            if card:
                return card

        return None

    def _forced_clean(self, ctx: AIContext,
                      certain_cards: list[Card]) -> Card:
        if ctx.is_last:
            traps = [c for c in certain_cards if self._is_trap(c, ctx)]
            if traps:
                card = max(traps, key=lambda c: c.rank_order)
                self._set_log("FORCED_CLEAN", f"dump trap: {card}")
                return card

        card = max(certain_cards, key=lambda c: c.rank_order)
        self._set_log("FORCED_CLEAN", f"najvyššia lead: {card}")
        return card

    def _forced_points(self, ctx: AIContext,
                       certain_cards: list[Card]) -> Card:
        if ctx.is_last:
            card = max(certain_cards, key=lambda c: c.rank_order)
            self._set_log("FORCED_POINTS", f"posledný max: {card}")
        else:
            card = min(certain_cards, key=lambda c: c.rank_order)
            self._set_log("FORCED_POINTS", f"min škoda: {card}")
        return card

    def _can_early_take(self, ctx: AIContext) -> bool:
        if ctx.is_last:
            return False
        if ctx.lead_suit != "bell":
            return False
        if ctx.trick_has_penalty:
            return False
        bell_cards = [c for c in ctx.lead_cards if not c.is_special]
        if len(bell_cards) < 2:
            return False
        if "bell" in self.memory.suits_led:
            return False
        if len(self.memory.remaining["bell"]) < 5:
            return False
        # Veto — mám kartu ktorá môže vyhrať štich?
        if ctx.current_best:
            can_win = any(
                c.rank_order > ctx.current_best.rank_order
                for c in bell_cards
            )
            if not can_win:
                return False
        return True

    def _early_take(self, ctx: AIContext) -> Card | None:
        """Bell risk_pick matica + ak neprebije → max underplay."""
        bell_cards = [c for c in ctx.lead_cards if not c.is_special]
        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ])
        remaining = len(self.memory.remaining["bell"])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ]

        card = self._risk_pick_matrix(
            bell_cards, my_count, remaining, all_in_hand, ctx
        )
        if card is None:
            card = max(bell_cards, key=lambda c: c.rank_order)

        # Ak neprebije current_best → max underplay
        if ctx.current_best and card.rank_order < ctx.current_best.rank_order:
            underplay = [
                c for c in bell_cards
                if c.rank_order < ctx.current_best.rank_order
            ]
            if underplay:
                card = max(underplay, key=lambda c: c.rank_order)

        self._set_log("EARLY_TAKE", f"bell risk_pick: {card}")
        return card

    def _can_free_take(self, ctx: AIContext) -> bool:
        """Illuminator hral, nezahral horníka, mám A/K."""
        if ctx.lead_suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(ctx.lead_suit):
            return False

        illuminator = self.memory.illuminated_by[ctx.lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return False

        played_indices = {idx for idx, _ in ctx.decision.trick.played_cards}
        if illuminator not in played_indices:
            return False

        special_in_trick = any(c.is_special for c in ctx.trick_cards)
        if special_in_trick:
            return False

        # Veto — void hráč po mne môže mať druhého horníka
        other_suit = "acorn" if ctx.lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            other_holders = ctx.decision.special_holders.get(other_suit, set())
            for player_idx in ctx.decision.players_after:
                is_void_lead = ctx.lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return False

        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        return bool(high)

    def _free_take(self, ctx: AIContext) -> Card | None:
        """Dump A/K cez FREE_TAKE príležitosť."""
        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if not high:
            return None
        card = max(high, key=lambda c: c.rank_order)
        self._set_log("FREE_TAKE", f"dump A/K illuminator hral: {card}")
        return card

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> Card | None:
        """Rozhodovacia matica: remaining vs my_count."""
        if not suit_cards:
            return None

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
        """
        CERTAIN → vysoká váha (musíme brať).
        EARLY/FREE → stredná váha (dobrovoľné).
        """
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            return 8.0
        return 5.0