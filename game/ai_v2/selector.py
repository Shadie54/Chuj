# game/ai_v2/selector.py

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_v2.context import AIContext, TrickOutcome
from game.ai_v2.strategies.base import Strategy


class StrategySelector:
    """
    Zbiera aktívne stratégie, vyberá najlepšiu kartu.

    Mechanika:
    1. Zozbieraj všetky aktívne stratégie
    2. Dump stratégie (void / TAKE_CERTAIN) → pevná priorita
    3. Ostatné → najvyššia váha
    4. Globálny fallback ak žiadna stratégia nemá kandidáta
    """

    # Pevná priorita dump stratégií
    DUMP_PRIORITY = [
        "DumpSpecial",
        "DumpHeart",
        "DumpDangerous",
        "DumpHigh",
    ]

    def __init__(self, player: Player, memory: AIMemory,
                 strategies: list[Strategy], logger=None):
        self.player = player
        self.memory = memory
        self.strategies = strategies
        self.logger = logger

    def select(self, ctx: AIContext) -> Card:
        active = [s for s in self.strategies if s.is_active(ctx)]

        if self.logger:
            self._log_active(active)

        # Dump stratégie — vždy s pevnou prioritou
        card = self._select_dump(active, ctx)
        if card:
            return card

        # Ostatné stratégie — súťaž cez váhy
        card = self._select_by_weight(active, ctx)
        if card:
            return card

        return self._fallback(ctx)

    def _select_dump(self, active: list[Strategy],
                     ctx: AIContext) -> Card | None:
        """
        Dump stratégie v pevnom poradí priority.
        Prvá aktívna dump stratégia s kandidátom vyhrá.
        """
        for name in self.DUMP_PRIORITY:
            strategy = next(
                (s for s in active if s.name == name), None
            )
            if strategy is None:
                continue
            card = strategy.propose(ctx)
            if card is not None:
                if self.logger:
                    self.logger.log_strategy(
                        self.player.name,
                        strategy.log_entry(),
                        f"dump_priority → {card}"
                    )
                self._log_selected(strategy, card, "dump_priority")
                return card

        return None

    def _select_by_weight(self, active: list[Strategy],
                          ctx: AIContext) -> Card | None:
        """
        Ostatné stratégie súťažia cez váhy.
        Karta môže dostať podporu od viacerých stratégií.
        """
        # Vylúč dump stratégie — tie riešime osobitne
        non_dump = [
            s for s in active
            if s.name not in self.DUMP_PRIORITY
        ]

        if not non_dump:
            return None

        # Každá stratégia navrhne kartu + váhu
        card_scores: dict[Card, float] = {}
        card_sources: dict[Card, list[str]] = {}

        for strategy in non_dump:
            card = strategy.propose(ctx)
            if card is None:
                continue
            w = strategy.weight(ctx)
            # ← zaloguj variant ihneď po propose()
            if self.logger:
                self.logger.log_strategy(
                    self.player.name,
                    strategy.log_entry(),
                    f"navrhuje: {card} (váha={w})"
                )
            if card not in card_scores:
                card_scores[card] = 0.0
                card_sources[card] = []
            card_scores[card] += w
            card_sources[card].append(f"{strategy.name}({w})")

        if not card_scores:
            return None

        best_card = max(card_scores, key=lambda c: card_scores[c])

        if self.logger:
            self._log_scores(card_scores, card_sources, best_card)

        return best_card

    def _fallback(self, ctx: AIContext) -> Card:
        """Globálny fallback — žiadna stratégia nemala kandidáta."""
        non_special = [c for c in ctx.playable if not c.is_special]
        pool = non_special if non_special else ctx.playable
        card = min(pool, key=lambda c: c.rank_order)

        if self.logger:
            self.logger.log_strategy(
                self.player.name,
                "GLOBAL_FALLBACK",
                f"žiadna stratégia nemala kandidáta: {card}"
            )
        return card

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_active(self, active: list[Strategy]):
        if not self.logger:
            return
        names = [s.name for s in active]
        self.logger.log_strategy(
            self.player.name,
            "ACTIVE_STRATEGIES",
            f"{names}"
        )

    def _log_selected(self, strategy: Strategy,
                      card: Card, method: str):
        if not self.logger:
            return
        self.logger.log_strategy(
            self.player.name,
            strategy.log_entry(),
            f"[{method}] → {card}"
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
            self.player.name,
            "WEIGHT_SELECTION",
            f"{scores_str} → {best_card}"
        )