from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class StrategySelector:
    DUMP_PRIORITY = [
        ("DumpSpecial", None),
        ("DumpDangerous", "DANGER_TRAP"),
        ("DumpHeart", None),
        ("DumpDangerous", "TRAP"),
        ("DumpHigh", None),
    ]
    DUMP_PRIORITY_HIGH_SCORE = [
        ("DumpHeart", None),
        ("DumpSpecial", None),
        ("DumpDangerous", "TRAP"),
        ("DumpHigh", None),
        ("DumpDangerous", "DANGER_TRAP"),  # posledná záchrana, nič lepšie nenašli
    ]

    def __init__(self, player: Player, memory: AIMemory,
                 strategies: list[Strategy], logger=None):
        self.player = player
        self.memory = memory
        self.strategies = strategies
        self.logger = logger
        self.last_variant: str = ""

    def select(self, ctx: AIContext) -> Card:
        if len(ctx.playable) == 1:
            card = ctx.playable[0]
            self.last_variant = "FORCED_SINGLE_CARD"
            if self.logger:
                self.logger.log_strategy(
                    self.player.name, "FORCED_SINGLE_CARD", f"jediná legálna karta: {card}"
                )
            return card

        active = [s for s in self.strategies if s.is_active(ctx)]

        if self.logger:
            self._log_active(active)

        card = self._select_dump(active, ctx)
        if card:
            return card

        card = self._select_by_weight(active, ctx)
        if card:
            return card

        return self._fallback(ctx)

    def _select_dump(self, active: list[Strategy],
                     ctx: AIContext) -> Card | None:
        priority = self.DUMP_PRIORITY_HIGH_SCORE if ctx.is_high_score else self.DUMP_PRIORITY
        proposals_cache: dict[str, list[tuple[Card, str, str]]] = {}

        for strategy_name, variant_filter in priority:
            strategy = next((s for s in active if s.name == strategy_name), None)
            if strategy is None:
                continue

            if strategy_name not in proposals_cache:
                proposals_cache[strategy_name] = strategy.propose(ctx)
            proposals = proposals_cache[strategy_name]

            if variant_filter is not None:
                proposals = [p for p in proposals if p[1] == variant_filter]

            if not proposals:
                continue

            if self.logger:
                for card, variant, detail in proposals:
                    self.logger.log_strategy(
                        self.player.name,
                        f"{strategy.name} | {variant}",
                        f"{detail}"
                    )

            # Z kandidátov tohto tieru vyber najvyšší rank (najhodnotnejší dump)
            best_card, best_variant, _ = max(proposals, key=lambda p: p[0].rank_order)
            self.last_variant = best_variant

            if self.logger:
                self.logger.log_strategy(
                    self.player.name, "DUMP_SELECTED", f"{best_card}"
                )
            return best_card

        return None

    def _select_by_weight(self, active: list[Strategy],
                          ctx: AIContext) -> Card | None:
        non_dump = [s for s in active if s.name not in self.DUMP_PRIORITY]
        if not non_dump:
            return None

        card_scores: dict[Card, float] = {}
        card_sources: dict[Card, list[str]] = {}

        for strategy in non_dump:
            proposals = strategy.propose(ctx)
            if not proposals:
                if self.logger:
                    self.logger.log_strategy(
                        self.player.name, strategy.name, "žiadna karta"
                    )
                continue
            for card, variant, detail in proposals:
                w = strategy.variant_weight(variant, ctx)
                if self.logger:
                    self.logger.log_strategy(
                        self.player.name,
                        f"{strategy.name} | {variant}",
                        f"{detail} (váha={w})"
                    )
                card_scores[card] = card_scores.get(card, 0.0) + w
                card_sources.setdefault(card, []).append(
                    f"{strategy.name}.{variant}({w})"
                )

        if not card_scores:
            return None

        best_card = max(card_scores, key=lambda c: card_scores[c])
        # Nájdi variant s najvyššou váhou pre víťaznú kartu (posledný zdroj ak viac)
        sources = card_sources.get(best_card, [])
        if sources:
            # source formát: "StrategyName.VARIANT(weight)"
            last_source = sources[-1]
            variant_part = last_source.split(".", 1)[-1].split("(")[0]
            self.last_variant = variant_part
        else:
            self.last_variant = ""

        if self.logger:
            self._log_scores(card_scores, card_sources, best_card)

        return best_card

    def _fallback(self, ctx: AIContext) -> Card:
        non_special = [c for c in ctx.playable if not c.is_special]
        pool = non_special if non_special else ctx.playable
        card = min(pool, key=lambda c: c.rank_order)

        # Úzko vymedzený prípad: leader a VŠETKY hrateľné karty (vrátane
        # prípadných horníkov) sú zvonka netknuteľné — nič u súperov ani v
        # aktuálnom štichu ich neprebije. Zámerne NEPOUŽÍVA
        # DumpDangerous-štýl _is_trap (tá naviac kontroluje aj vlastné iné
        # karty tej istej farby — zmysluplné pre reagovanie, kde ide o to,
        # ktorá JEDNA z mojich kariet je natrvalo "zaseknutá", ale zavádzajúce
        # pri vedení, kde vyberám len jednu kartu naraz a vlastné ostatné
        # karty danej farby sú irelevantné). Príklad, prečo je to dôležité:
        # ak držím CELÝ zvyšok jednej farby (napr. 10♣,8♣,7♣ a nič iné z
        # acorn už nikde neexistuje), z pohľadu súperov je KAŽDÁ z nich
        # rovnako netknuteľná — pôvodná (DumpDangerous) definícia by
        # nesprávne označila len 10♣ ako "trap" (8♣/7♣ by "zlyhali" na
        # vlastnom vyššom 10♣), a `all(...)` by nikdy nebolo True.
        # Karta sa nemení oproti GLOBAL_FALLBACK vyššie — mení sa len label,
        # aby sa tieto (väčšinou už správne) prípady dali oddeliť od
        # skutočne vylepšiteľných nálezov. Zámerne mimo zoznamu stratégií v
        # selector.strategies — nesúťaží cez _select_by_weight, takže
        # nemôže ovplyvniť žiadnu inú situáciu.
        is_pure_trap_lead = (
            ctx.is_leader
            and bool(ctx.playable)
            and all(self._is_unbeatable_by_opponent(c, ctx) for c in ctx.playable)
        )

        if is_pure_trap_lead:
            self.last_variant = "FORCED_LEAD_TRAP"
            if self.logger:
                self.logger.log_strategy(
                    self.player.name, "FORCED_LEAD_TRAP",
                    f"leader, všetky hrateľné karty (vrátane prípadných "
                    f"horníkov) sú trap: {card}"
                )
            return card

        self.last_variant = "GLOBAL_FALLBACK"
        if self.logger:
            self.logger.log_strategy(
                self.player.name, "GLOBAL_FALLBACK",
                f"žiadna stratégia nemala kandidáta: {card}"
            )
        return card

    def _is_unbeatable_by_opponent(self, card: Card, ctx: AIContext) -> bool:
        """
        Na rozdiel od Strategy._is_trap (base.py) NEKONTROLUJE vlastné iné
        karty tej istej farby (higher_own) — pre vedenie je relevantné len
        to, či kartu môže prebiť súper (remaining) alebo už rozohraný štich,
        nie moje ostatné karty. Príklad: ak držím CELÝ zvyšok jednej farby
        (napr. 10♣,8♣,7♣ a nič iné z acorn už nikde neexistuje), z pohľadu
        súperov je KAŽDÁ z nich rovnako netknuteľná — pôvodná definícia by
        nesprávne označila len 10♣ ako "trap" (8♣/7♣ by "zlyhali" na
        vlastnom vyššom 10♣).
        """
        higher_remaining = [
            c for c in self.memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        higher_in_trick = [
            c for c in ctx.trick_cards
            if c.suit == card.suit and c.rank_order > card.rank_order
        ]
        return not higher_remaining and not higher_in_trick

    def _log_active(self, active: list[Strategy]):
        if not self.logger:
            return
        names = [s.name for s in active]
        self.logger.log_strategy(
            self.player.name, "ACTIVE_STRATEGIES", f"{names}"
        )

    def _log_scores(self, card_scores: dict[Card, float],
                    card_sources: dict[Card, list[str]],
                    best_card: Card):
        if not self.logger:
            return
        scores_str = ", ".join(
            f"{c}={card_scores[c]:.1f}({'+'.join(card_sources[c])})"
            for c in sorted(card_scores, key=lambda c: card_scores[c], reverse=True)
        )
        self.logger.log_strategy(
            self.player.name, "WEIGHT_SELECTION", f"{scores_str} → {best_card}"
        )