# game/ai_v2/strategies/dump_special.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class DumpSpecial(Strategy):
    name = "DumpSpecial"

    def is_active(self, ctx: AIContext) -> bool:
        if ctx.is_leader:
            return False

        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return False

        if ctx.is_void:
            if ctx.trick_outcome == TrickOutcome.NEVER:
                return False
            return True

        if ctx.current_best:
            underplay_specials = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
            ]
            if underplay_specials:
                return True

        return False

    def propose(self, ctx: AIContext) -> list[tuple[Card, str, str]]:
        results = []
        specials = [c for c in ctx.playable if c.is_special]
        if not specials:
            return results

        if ctx.is_high_score:
            return self._propose_high_score(ctx, specials)

        if ctx.is_void:
            ordered = self._ordered_by_urgency(specials, ctx)
            for card in ordered:
                detail = f"{card} ({self._special_points(card)}b)"
                if len(ordered) > 1:
                    detail += f" [{self._urgency_label(card, ctx)}]"
                results.append((card, "VOID", detail))
            return results

        if ctx.current_best:
            underplay = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.NEVER
            ]
            for card in underplay:
                results.append((
                    card, "UNDERPLAY",
                    f"{card} podlieza {ctx.current_best}"
                ))

        return results

    def _ordered_by_urgency(self, specials: list[Card],
                             ctx: AIContext) -> list[Card]:
        """
        Zoradí držaných horníkov od najurgentnejšieho po najmenej urgentný,
        pre remízu vo VOID vetve (dvaja horníci naraz, rovnaký rank_order
        → StrategySelector._select_dump() by inak vzal prvého v poradí
        ruky — AI_V2_HANDOFF.md §8). Poradie vrstiev (claude/14_HORNIK_
        TIEBREAK_HAND_EVAL_LOG.md, koncept 15, nahrádza koncept 14):

          1. istota — päťstavovo. "Vankúš" = rezervy>0 (iná karta tej
             farby v ruke), t.j. keby sa farba ešte viedla, nemusím
             hneď zahrať horníka, môžem podliezť rezervou:
               a) trap A pokrytie>0 A rezervy==0 — istý sebazáchyt PRI
                  force A žiadny vankúš → najurgentnejšie.
               b) escape A rezervy==0 — neisté, ale tiež žiadny
                  vankúš → pri najbližšom vedení tej farby som nútený
                  zahrať priamo horníka, nech je to trap či nie.
               c) trap A pokrytie>0 A rezervy>0 — istý sebazáchyt PRI
                  force, ale môžem ho o kolo-dve odložiť podliezkou.
               d) escape A rezervy>0 — neisté, a navyše vankúš.
               e) trap A pokrytie==0 — farba je úplne mŕtva, nikto ju už
                  nikdy nepovede → žiadne budúce riziko → najmenej
                  urgentné (koncept 7 — trap-label je irelevantný, keď
                  farbu už nikto nemôže viesť; nezávisí od vankúša).
             (Koncept 14 mal len trojstavovo: trap&pokrytie>0 / escape /
             trap&pokrytie==0 — Hra 4 odhalila, že to nezohľadňuje vankúš:
             escape bez rezervy môže byť v praxi rizikovejšia než trap
             s rezervou, pretože escape bez vankúša = istá budúca
             exekúcia horníka, len s neistým výsledkom.)
          2. rezervy danej farby ako číslo (tiebreak v rámci rovnakého
             tieru — menej rezerv = urgentnejšie); pri rovnakom počte
             rezerv rozhoduje, koľko z nich je samo trap.
          3. bodová hodnota horníka (vyššia = urgentnejšia — nech jej
             body pripadnú niekomu inému, nie nám).

        Zatiaľ len pre tento (nie 90+) VOID prípad — _propose_high_score()
        vedome nechaný bokom, nebol súčasťou testovaných príkladov.
        """
        if len(specials) < 2:
            return specials

        return sorted(specials, key=lambda c: self._urgency_key(c, ctx))

    def _urgency_key(self, card: Card, ctx: AIContext) -> tuple:
        profile = self.memory.build_suit_profile(
            card.suit, self.player.hand.cards, ctx.trick_cards
        )
        is_trap = self._is_trap(card, ctx)
        suit_alive = len(profile.coverage) > 0
        has_buffer = profile.special_reserves > 0

        if is_trap and suit_alive and not has_buffer:
            certainty = 0   # istý sebazáchyt, žiadny vankúš
        elif not is_trap and not has_buffer:
            certainty = 1   # escape, žiadny vankúš — tiež istá exekúcia
        elif is_trap and suit_alive and has_buffer:
            certainty = 2   # istý sebazáchyt, ale je vankúš (možno odložiť)
        elif not is_trap:
            certainty = 3   # escape, a je vankúš — najmenej urgentné zo "živých"
        else:
            certainty = 4   # trap, farba mŕtva — nulové riziko

        trap_reserves = len([
            c for c in profile.trap_cards if not c.is_special
        ])
        return (
            certainty,                               # 1: istota (0..4)
            profile.special_reserves,                 # 2a: menej rezerv skôr
            -trap_reserves,                            # 2b: viac trap rezerv skôr
            -self._special_points(card),               # 3: vyššia hodnota skôr
        )

    def _urgency_label(self, card: Card, ctx: AIContext) -> str:
        """
        Krátky "prečo" tag pre AI log (diagnostika v testeri) — vysvetľuje
        poradie z _ordered_by_urgency() bez nutnosti čítať kód.
        """
        profile = self.memory.build_suit_profile(
            card.suit, self.player.hand.cards, ctx.trick_cards
        )
        is_trap = self._is_trap(card, ctx)
        label = "trap" if is_trap else "escape"
        if is_trap and not profile.coverage:
            label += " mŕtva farba"
        elif profile.special_reserves == 0:
            label += " bez vankúša"
        return f"{label}, pokrytie={len(profile.coverage)}, rezervy={profile.special_reserves}"

    def _propose_high_score(self, ctx: AIContext,
                             specials: list[Card]) -> list[tuple[Card, str, str]]:
        results = []
        has_escape = any(
            c for c in ctx.playable
            if not c.is_special and not self._is_trap(c, ctx)
        )

        if not has_escape:
            if ctx.is_void:
                for card in specials:
                    results.append((
                        card, "IMMEDIATE_90", f"{card} — žiadna escape"
                    ))
                return results
            if ctx.current_best:
                underplay = [
                    c for c in specials
                    if c.rank_order < ctx.current_best.rank_order
                ]
                for card in underplay:
                    results.append((
                        card, "IMMEDIATE_90",
                        f"{card} podlieza — žiadna escape"
                    ))
                if results:
                    return results

        if ctx.is_void:
            for card in specials:
                results.append((
                    card, "VOID",
                    f"90+ {card} ({self._special_points(card)}b)"
                ))
            return results

        if ctx.current_best:
            underplay = [
                c for c in specials
                if c.rank_order < ctx.current_best.rank_order
                   and card_outcome(
                       c, ctx.decision.trick,
                       self.memory, ctx.decision.players_after
                   ) == TrickOutcome.NEVER
            ]
            for card in underplay:
                results.append((
                    card, "UNDERPLAY",
                    f"90+ {card} podlieza {ctx.current_best}"
                ))

        return results

    def weight(self, ctx: AIContext) -> float:
        if ctx.is_high_score:
            return 6.0
        return 9.0