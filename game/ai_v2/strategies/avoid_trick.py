# game/ai_v2/strategies/avoid_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class AvoidTrick(Strategy):
    name = "AvoidTrick"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False
        if ctx.is_void:
            return False
        if not ctx.lead_cards:
            return False

        dump_ak, _ = self._dump_ak_free(ctx)
        if dump_ak:
            return True

        non_certain = [
            c for c in ctx.lead_cards
            if not c.is_special
               and card_outcome(
                   c, ctx.decision.trick,
                   self.memory, ctx.decision.players_after
               ) != TrickOutcome.CERTAIN
        ]
        if not non_certain:
            return False

        if ctx.current_best:
            can_underplay = any(
                c.rank_order < ctx.current_best.rank_order
                for c in non_certain
            )
            if can_underplay:
                return True

        has_safe = any(self._is_safe(c, ctx) for c in non_certain)
        if has_safe:
            return True

        if self._can_risk_pick(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []

        dump_ak, dump_ak_variant = self._dump_ak_free(ctx)
        for card in dump_ak:
            results.append((card, dump_ak_variant, f"{card}"))

        risk = self._risk_pick_cards(ctx)
        valid_risk = [
            c for c in risk
            if card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            ) == TrickOutcome.UNKNOWN
        ]
        for card in valid_risk:
            results.append((card, "RISK_PICK", f"{card}"))

        if ctx.current_best:
            underplay = [
                c for c in ctx.lead_cards
                if c.rank_order < ctx.current_best.rank_order
                   and not c.is_special
            ]
            if underplay:
                max_rank = max(c.rank_order for c in underplay)
                for card in [c for c in underplay if c.rank_order == max_rank]:
                    results.append((card, "UNDERPLAY", f"{card}"))

        if not results:
            safe = [
                c for c in ctx.lead_cards
                if self._is_safe(c, ctx)
                   and card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if safe:
                min_rank = min(c.rank_order for c in safe)
                for card in [c for c in safe if c.rank_order == min_rank]:
                    results.append((card, "UNDERPLAY", f"safe: {card}"))

        return results

    def _dump_ak_free(self, ctx: AIContext) -> tuple[list[Card], str]:
        """
        Vráti (karty, variant_label) pre bezpečný dump A/K vo farbe
        s aktívnym horníkom. Dva nezávislé prípady:
        - DUMP_AK_FREE_OPPONENT: cudzí vysvietený horník už zahral v tomto
          štichu, žiadny súper po mne nemôže mať ten druhý horník
        - DUMP_AK_FREE_OWN: ja mám vlastného živého horníka v ruke →
          objektívne v bezpečí (nikto po mne ho nemôže mať), bez ohľadu
          na vysvietenie. Pri málo rezervách (<=3) je lepšie uvoľniť sa
          z vysokej karty teraz namiesto podliezania.
        """
        suit = ctx.lead_suit
        if suit not in ("leaf", "acorn"):
            return [], ""
        if self.memory.is_special_gone(suit):
            return [], ""

        illuminator = self.memory.illuminated_by[suit]

        # Prípad A — súperov vysvietený horník, illuminator už zahral
        if illuminator is not None and illuminator != self.player.index:
            played_indices = {idx for idx, _ in ctx.decision.trick.played_cards}
            if illuminator in played_indices:
                special_in_trick = any(c.is_special for c in ctx.trick_cards)
                if not special_in_trick:
                    other_suit = "acorn" if suit == "leaf" else "leaf"
                    blocked = False
                    if not self.memory.is_special_gone(other_suit):
                        other_holders = ctx.decision.special_holders.get(other_suit, set())
                        for player_idx in ctx.decision.players_after:
                            is_void_lead = suit in self.memory.void_suits[player_idx]
                            could_have_other = player_idx in other_holders
                            if is_void_lead and could_have_other:
                                blocked = True
                                break
                    if not blocked:
                        high = [
                            c for c in ctx.lead_cards
                            if c.rank in ("ace", "king") and not c.is_special
                        ]
                        if high:
                            max_rank = max(c.rank_order for c in high)
                            return [c for c in high if c.rank_order == max_rank], \
                                   "DUMP_AK_FREE_OPPONENT"

        # Prípad B — mám vlastného živého horníka, som objektívne v bezpečí
        hand = self.player.hand.cards
        has_my_special = any(c.is_special and c.suit == suit for c in hand)
        if has_my_special:
            all_reserves_in_hand = [
                c for c in hand if c.suit == suit and not c.is_special
            ]
            if len(all_reserves_in_hand) <= 3:
                high = [
                    c for c in ctx.lead_cards
                    if c.rank in ("ace", "king") and not c.is_special
                ]
                if high:
                    max_rank = max(c.rank_order for c in high)
                    return [c for c in high if c.rank_order == max_rank], \
                        "DUMP_AK_FREE_OWN"

        return [], ""

    def _can_risk_pick(self, ctx: AIContext) -> bool:
        if ctx.is_last:
            return False
        suit = ctx.lead_suit
        if suit is None:
            return False
        if suit in self.memory.suits_led:
            return False
        if ctx.current_best:
            my_highest = max(
                (c for c in ctx.lead_cards if not c.is_special),
                key=lambda c: c.rank_order,
                default=None
            )
            if my_highest and my_highest.rank_order < ctx.current_best.rank_order:
                return False
        remaining = len(self.memory.remaining[suit])
        return remaining >= 5

    def _risk_pick_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_risk_pick(ctx):
            return []

        suit = ctx.lead_suit
        suit_cards = [c for c in ctx.lead_cards if not c.is_special]

        if suit in ("leaf", "acorn"):
            suit_cards = [c for c in suit_cards if c.rank not in ("ace", "king")]

        if not suit_cards:
            return []

        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ])
        if my_count <= 1:
            return []

        remaining = len(self.memory.remaining[suit])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == suit and not c.is_special
        ]

        return self._risk_pick_matrix(suit_cards, my_count, remaining, all_in_hand, ctx)

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> list[Card]:
        def safe_or_lowest() -> list[Card]:
            safe = [c for c in suit_cards if self._is_safe(c, ctx)]
            pool = safe if safe else suit_cards
            min_rank = min(c.rank_order for c in pool)
            return [c for c in pool if c.rank_order == min_rank]

        def mid_cards() -> list[Card]:
            if not all_in_hand:
                return []
            highest = max(all_in_hand, key=lambda c: c.rank_order)
            candidates = [
                c for c in suit_cards
                if highest.rank_order - c.rank_order >= 2
            ]
            if not candidates:
                return []
            max_rank = max(c.rank_order for c in candidates)
            return [c for c in candidates if c.rank_order == max_rank]

        if remaining >= 5:
            if my_count <= 2:
                max_rank = max(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == max_rank]
            elif my_count == 3:
                mid = mid_cards()
                if mid:
                    return mid
                min_rank = min(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == min_rank]
            else:
                return safe_or_lowest()
        else:
            if my_count <= 2:
                mid = mid_cards()
                if mid:
                    return mid
                min_rank = min(c.rank_order for c in suit_cards)
                return [c for c in suit_cards if c.rank_order == min_rank]
            else:
                return safe_or_lowest()

    def weight(self, ctx: AIContext) -> float:
        return 5.0

    def variant_weight(self, variant: str, ctx: AIContext) -> float:
        if variant in ("DUMP_AK_FREE_OPPONENT", "DUMP_AK_FREE_OWN"):
            return 6.0
        return self.weight(ctx)