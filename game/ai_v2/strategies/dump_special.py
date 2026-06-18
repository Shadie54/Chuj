# game/ai_v2/strategies/dump_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpSpecial(Strategy):
    """
    Zbav sa horníka.

    Varianty:
    - VOID        — som void na lead suit, hodím horníka
    - UNDERPLAY   — horník podlieza current_best, zahodím ho zadarmo
    - TARGETED_90 — pri 90+, cielený dump na hráča pod 90b (placeholder)
    - IMMEDIATE_90 — pri 90+, okamžitý dump ak je riziko čakania vysoké (placeholder)
    """

    name = "DumpSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False

        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return False

        # DEBUG
        print(f"[DUMP_SPECIAL_ACTIVE {self.player.name}] "
              f"specials={specials} is_void={ctx.is_void} "
              f"current_best={ctx.current_best}")

        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return False

        # Void → príležitosť na dump (someone_takes != NEVER)
        if ctx.is_void:
            if ctx.trick_outcome == TrickOutcome.NEVER:
                return False
            return True

        # Underplay → horník podlieza current_best → NEVER je správne
        if ctx.current_best:
            underplay_specials = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
            ]
            if underplay_specials:
                return True

        return False

    def propose(self, ctx: AIContext) -> Card | None:
        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return None

        print(f"[DUMP_SPECIAL_DEBUG {self.player.name}] "
              f"specials={specials} current_best={ctx.current_best} "
              f"is_void={ctx.is_void} trick_cards={ctx.trick_cards}")

        if ctx.is_high_score:
            return self._propose_high_score(ctx, specials)

        # Void → najhodnotnejší horník
        if ctx.is_void:
            card = max(specials, key=lambda c: self._special_points(c))
            self._set_log("VOID", f"{card} ({self._special_points(card)}b)")
            return card

        # Underplay → horník ktorý podlieza a dáva NEVER
        if ctx.current_best:
            underplay = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                    c, ctx.decision.trick,
                    self.memory, ctx.decision.players_after
                ) == TrickOutcome.NEVER
            ]
            if underplay:
                card = max(underplay, key=lambda c: self._special_points(c))
                self._set_log("UNDERPLAY", f"{card} podlieza {ctx.current_best}")
                return card

        return None

    def _propose_high_score(self, ctx: AIContext,
                             specials: list[Card]) -> Card | None:
        """
        Pri 90+ — zvažujeme komu hodíme horníka.
        Placeholder: zatiaľ rovnaká logika ako štandard.
        Neskôr: TARGETED (hráč pod 90b) vs IMMEDIATE (riziko čakania).
        """
        # TODO: TARGETED_90 — cielený dump na hráča pod 90b
        # TODO: IMMEDIATE_90 — okamžitý dump ak has_escape == False

        has_escape = any(
            c for c in ctx.playable
            if not c.is_special
               and not self._is_trap(c, ctx)
        )

        if not has_escape:
            # Riziko čakania vysoké → okamžitý dump
            if ctx.is_void:
                card = max(specials, key=lambda c: self._special_points(c))
                self._set_log("IMMEDIATE_90", f"{card} — žiadna escape")
                return card
            if ctx.current_best:
                underplay = [
                    c for c in specials
                    if c.rank_order < ctx.current_best.rank_order
                ]
                if underplay:
                    card = max(underplay, key=lambda c: self._special_points(c))
                    self._set_log("IMMEDIATE_90", f"{card} podlieza — žiadna escape")
                    return card

        # Zatiaľ štandard — neskôr TARGETED
        if ctx.is_void:
            card = max(specials, key=lambda c: self._special_points(c))
            self._set_log("VOID", f"90+ {card} ({self._special_points(card)}b)")
            return card

        return None

    def weight(self, ctx: AIContext) -> float:
        """
        Váha DumpSpecial.
        Vysoká — horník je najväčšie bodové riziko.
        Pri 90+ mierne nižšia (horníci nie sú bodové riziko).
        """
        if ctx.is_high_score:
            return 6.0
        return 9.0