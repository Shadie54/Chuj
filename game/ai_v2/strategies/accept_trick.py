# game/ai_v2/strategies/accept_trick.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy
from config import HIGH_SCORE_THRESHOLD


class AcceptTrick(Strategy):
    """
    Follower stratégia — dobrovoľné/vynútené vzatie štichu, keď je výsledok
    istý (CERTAIN) alebo keď sa oplatí zobrať skôr (bell early take, free take
    po illuminator hral A/K).
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
            if ctx.current_best and ctx.current_best.is_special:
                # Horník je current_best — bežne radšej podľahni a nechaj
                # body pôvodnému hráčovi horníka (netreba ho preberať na seba).
                # Výnimka: ak som posledný a JA aj majiteľ horníka máme 90+,
                # horník je preňho aj pre mňa neutrálny (0b) → pokojne vezmi
                # a zbav sa vysokej A/K karty bez rizika.
                both_high_score = self._both_high_score(ctx)

                if not both_high_score:
                    non_special = [c for c in ctx.lead_cards if not c.is_special]
                    has_never = any(
                        card_outcome(
                            c, ctx.decision.trick,
                            self.memory, ctx.decision.players_after
                        ) == TrickOutcome.NEVER
                        for c in non_special
                    )
                    if has_never:
                        return False

                if not self._has_alternative(ctx, ignore_penalty=both_high_score):
                    return True
            elif not self._has_alternative(ctx):
                return True

        if self._can_early_take(ctx):
            return True

        if self._can_free_take(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []
        both_high_score = self._both_high_score(ctx)

        if ctx.trick_outcome == TrickOutcome.CERTAIN and not self._has_alternative(ctx, ignore_penalty=both_high_score):
            certain_cards = [
                c for c in ctx.lead_cards
                if not c.is_special
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.CERTAIN
            ]
            if not certain_cards:
                certain_cards = [
                    c for c in ctx.lead_cards
                    if card_outcome(
                        c, ctx.decision.trick,
                        self.memory, ctx.decision.players_after
                    ) == TrickOutcome.CERTAIN
                ]
            if certain_cards:
                if not ctx.trick_has_penalty:
                    results += self._forced_clean(ctx, certain_cards)
                else:
                    # FORCED_POINTS_LOW: existuje nešpeciálna lead karta,
                    # ktorá by štich NEzobrala (podlez bol technicky možný) —
                    # _has_alternative() ju napriek tomu nepovažuje za
                    # alternatívu (napr. ≤2 body, pozri jej docstring), takže
                    # sa sem dostaneme aj v tomto prípade. Tip na to potrebuje
                    # iný text než skutočné "štichu sa nevyhneš".
                    non_special = [c for c in ctx.lead_cards if not c.is_special]
                    has_never = any(
                        card_outcome(
                            c, ctx.decision.trick,
                            self.memory, ctx.decision.players_after
                        ) == TrickOutcome.NEVER
                        for c in non_special
                    )
                    variant = "FORCED_POINTS_LOW" if has_never else "FORCED_POINTS"
                    results += self._forced_points(ctx, certain_cards, variant)
                return results

        free = self._free_take_cards(ctx)
        if free:
            for card in free:
                results.append((card, "FREE_TAKE", f"dump A/K illuminator hral: {card}"))
            return results

        early = self._early_take_cards(ctx)
        if early:
            for card in early:
                # _early_take_cards() má fallback vetvu: ak risk-picknutá
                # karta neprebije current_best, vráti max(underplay) —
                # teda kartu, ktorá štich NEzoberie (zámerné, pozri
                # 02_AI_REFERENCE.md F-EARLY_TAKE). Tá si preto zaslúži
                # "UNDERPLAY" popis ("Podlez to."), nie "EARLY_TAKE"
                # ("Ber štich") — inak tip hovorí opak toho, čo karta
                # reálne robí.
                if ctx.current_best and card.rank_order < ctx.current_best.rank_order:
                    results.append(
                        (card, "UNDERPLAY",
                         f"bell risk_pick neprebíja, podliezam: {card}")
                    )
                else:
                    results.append((card, "EARLY_TAKE", f"bell risk_pick: {card}"))
            return results

        return results

    def _owner_index(self, card, ctx: AIContext) -> int | None:
        """Nájde index hráča, ktorý zahral danú kartu do aktuálneho štichu."""
        return next(
            (idx for idx, c in ctx.decision.trick.played_cards if c == card),
            None
        )

    def _both_high_score(self, ctx: AIContext) -> bool:
        """
        True len ak som posledný, current_best je horník, a JA aj majiteľ
        horníka máme 90+ (horník je preto neutrálny pre oboch — 0b).
        Mimo is_last sa toto zámerne nevyhodnocuje (víťaz štichu ešte nie je
        istý, kým niekto po mne ešte hrá).
        """
        if not ctx.is_last:
            return False
        if not ctx.current_best or not ctx.current_best.is_special:
            return False
        owner_index = self._owner_index(ctx.current_best, ctx)
        owner_high_score = (
                owner_index is not None
                and ctx.all_scores[owner_index] >= HIGH_SCORE_THRESHOLD
        )
        return ctx.is_high_score and owner_high_score

    def _penalty_points_for_me(self, ctx: AIContext) -> int:
        """
        Skutočná bodová hodnota štichu PRE MŇA, ak by som ho zobral.
        Heart body počítajú vždy; horníkove body len ak mi 90+ pravidlo
        nedáva 0 (t.j. nemám 90+).
        """
        total = 0
        for _, c in ctx.decision.trick.played_cards:
            if c.suit == "heart":
                total += c.base_points
            elif c.is_special:
                total += self._special_value_for_me(c, ctx)
        return total

    def _has_alternative(self, ctx: AIContext, ignore_penalty: bool = False) -> bool:
        """
        Zisťuje, či mám legitímnu alternatívu k dobrovoľnému vzatiu štichu.
        - is_last: alternatíva je NEVER karta pri bodovom štichu (>2b, počítané
          z môjho pohľadu — horníkove body sa nerátajú ak mám 90+) — radšej
          nechám body tomu, kto vedie, než ich preberať na seba.
          ignore_penalty vypne túto podmienku (pozri _both_high_score).
        - nie is_last: akákoľvek karta, ktorá nie je CERTAIN, je alternatíva
          (mám možnosť počkať, výsledok závisí od hráčov po mne).
        """
        non_special = [c for c in ctx.lead_cards if not c.is_special]
        for c in non_special:
            outcome = card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if ctx.is_last:
                if not ignore_penalty and outcome == TrickOutcome.NEVER:
                    penalty_points = self._penalty_points_for_me(ctx)
                    if penalty_points > 2:
                        return True
                if outcome == TrickOutcome.UNKNOWN:
                    return True
            else:
                if outcome != TrickOutcome.CERTAIN:
                    return True
        return False

    def _forced_clean(self, ctx: AIContext,
                      certain_cards: list[Card]) -> list[tuple[Card, str, str]]:
        """Čistý štich (bez bodov) — posledný hráč sa zbaví trap karty, inak najvyššia."""
        results = []
        if ctx.is_last:
            traps = [c for c in certain_cards if self._is_trap(c, ctx)]
            if traps:
                max_rank = max(c.rank_order for c in traps)
                for card in [c for c in traps if c.rank_order == max_rank]:
                    results.append((card, "FORCED_CLEAN", f"dump trap: {card}"))
                return results

        max_rank = max(c.rank_order for c in certain_cards)
        for card in [c for c in certain_cards if c.rank_order == max_rank]:
            results.append((card, "FORCED_CLEAN", f"najvyššia lead: {card}"))
        return results

    @staticmethod
    def _forced_points(ctx: AIContext, certain_cards: list[Card],
                       variant: str = "FORCED_POINTS") -> list[tuple[Card, str, str]]:
        """
        Bodový štich — posledný berie max, inak min škoda.
        variant="FORCED_POINTS": skutočne nemám alternatívu (každá karta by
        štich zobrala). variant="FORCED_POINTS_LOW": podlez bol technicky
        možný, len sa pre pár bodov neoplatí (pozri propose()).
        """
        results = []
        if ctx.is_last:
            target = max(c.rank_order for c in certain_cards)
            label = "posledný max"
        else:
            target = min(c.rank_order for c in certain_cards)
            label = "min škoda"
        for card in [c for c in certain_cards if c.rank_order == target]:
            results.append((card, variant, f"{label}: {card}"))
        return results

    def _can_early_take(self, ctx: AIContext) -> bool:
        """Bell, čistý štich, 2./3. pozícia, nízke void riziko — dobrovoľné zbavenie sa bell karty."""
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
        if ctx.current_best:
            can_win = any(
                c.rank_order > ctx.current_best.rank_order
                for c in bell_cards
            )
            if not can_win:
                return False
        return True

    def _early_take_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_early_take(ctx):
            return []

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

        cards = self._risk_pick_matrix(bell_cards, my_count, remaining, all_in_hand, ctx)
        if not cards:
            max_rank = max(c.rank_order for c in bell_cards)
            cards = [c for c in bell_cards if c.rank_order == max_rank]

        if ctx.current_best:
            valid = [c for c in cards if c.rank_order >= ctx.current_best.rank_order]
            if not valid:
                underplay = [
                    c for c in bell_cards
                    if c.rank_order < ctx.current_best.rank_order
                ]
                if underplay:
                    max_rank = max(c.rank_order for c in underplay)
                    return [c for c in underplay if c.rank_order == max_rank]
                return []
            return valid
        return cards

    def _can_free_take(self, ctx: AIContext) -> bool:
        """Illuminator už zahral A/K vo svojej vysvietenej farbe — bezpečné dumpnúť vlastné A/K."""
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

    def _free_take_cards(self, ctx: AIContext) -> list[Card]:
        if not self._can_free_take(ctx):
            return []
        high = [
            c for c in ctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if not high:
            return []
        max_rank = max(c.rank_order for c in high)
        return [c for c in high if c.rank_order == max_rank]

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> list[Card]:
        """Zdieľaná risk-pick matica (max/mid podľa my_count) — použitá pre bell v _early_take_cards."""
        if not suit_cards:
            return []

        # remaining < 5 je nedosiahnuteľné (_can_early_take už vyžaduje >=5)
        # a my_count >= 4 je nedosiahnuteľné pri remaining>=5 (pigeonhole
        # na 8-kartovej farbe) — obe pôvodné "mŕtve" vetvy boli zmazané.
        if my_count <= 2:
            max_rank = max(c.rank_order for c in suit_cards)
            return [c for c in suit_cards if c.rank_order == max_rank]

        # my_count == 3 (jediný ešte dosiahnuteľný prípad) — skutočný
        # stred zoradených kariet, bez gap-heuristiky a bez fallbacku
        # na najnižšiu (rovnaký princíp ako LeadSafe._simple_median()).
        sorted_cards = sorted(suit_cards, key=lambda c: c.rank_order)
        n = len(sorted_cards)
        idx = n // 2 if n % 2 == 1 else n // 2 - 1
        target_rank = sorted_cards[idx].rank_order
        return [c for c in sorted_cards if c.rank_order == target_rank]

    def weight(self, ctx: AIContext) -> float:
        if ctx.trick_outcome == TrickOutcome.CERTAIN:
            return 8.0
        return 5.0