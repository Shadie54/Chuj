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

    def __init__(self, player: Player, memory: AIMemory,
                 strategies: list[Strategy], logger=None):
        self.player = player
        self.memory = memory
        self.strategies = strategies
        self.logger = logger

    def select(self, ctx: AIContext) -> Card:
        if len(ctx.playable) == 1:
            card = ctx.playable[0]
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
        """
        Dump stratégie v pevnom poradí priority (tier list).
        Každý tier je (strategy_name, variant_filter) — variant_filter=None
        znamená ktorýkoľvek variant danej stratégie.
        Berie VŠETKY kandidátov z prvého tieru ktorý má kandidáta,
        vyberie najlepšieho podľa interného poradia (max rank_order ak viacero).
        """
        proposals_cache: dict[str, list[tuple[Card, str, str]]] = {}

        for strategy_name, variant_filter in self.DUMP_PRIORITY:
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
            best_card, _, _ = max(proposals, key=lambda p: p[0].rank_order)

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

        if self.logger:
            self._log_scores(card_scores, card_sources, best_card)

        return best_card

    def _fallback(self, ctx: AIContext) -> Card:
        non_special = [c for c in ctx.playable if not c.is_special]
        pool = non_special if non_special else ctx.playable
        card = min(pool, key=lambda c: c.rank_order)
        if self.logger:
            self.logger.log_strategy(
                self.player.name, "GLOBAL_FALLBACK",
                f"žiadna stratégia nemala kandidáta: {card}"
            )
        return card

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