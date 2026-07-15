# game/ai_v2/engine.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEvaluator, GameContext
from game.ai_v2.context import AIContext
from game.ai_v2.selector import StrategySelector

# Stratégie
from game.ai_v2.strategies.dump_special import DumpSpecial
from game.ai_v2.strategies.dump_heart import DumpHeart
from game.ai_v2.strategies.dump_dangerous import DumpDangerous
from game.ai_v2.strategies.dump_high import DumpHigh
from game.ai_v2.strategies.avoid_trick import AvoidTrick
from game.ai_v2.strategies.force_special import ForceSpecial
from game.ai_v2.strategies.setup_void import SetupVoid
from game.ai_v2.strategies.accept_trick import AcceptTrick
from game.ai_v2.strategies.risk_special import RiskSpecial
from game.ai_v2.strategies.wait import Wait
from game.ai_v2.strategies.lead_safe import LeadSafe


class AIEngine:
    """
    Hlavný vstupný bod pre nový AI systém (v2).

    Nahrádza pipeline:
    situácia → mód → CardSelector

    Novým systémom:
    kontext → aktívne stratégie → selector → karta
    """

    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

        self.evaluator = HandEvaluator(memory)

        # Inicializuj všetky stratégie
        strategy_classes = [
            DumpSpecial,
            DumpHeart,
            DumpDangerous,
            DumpHigh,
            AvoidTrick,
            ForceSpecial,
            SetupVoid,
            AcceptTrick,
            RiskSpecial,
            Wait,
            LeadSafe,
        ]
        self.strategies = [
            cls(player, memory) for cls in strategy_classes
        ]

        self.selector = StrategySelector(
            player, memory, self.strategies, logger
        )

    def decide(self,
               playable: list[Card],
               current_trick: Trick,
               trick_number: int,
               all_scores: list[int],
               my_declaration: str | None = None) -> Card:
        """
        Hlavná metóda — vyber kartu pre aktuálny ťah.
        Volá sa z AI.decide_card() ak use_new_system=True.
        """

        hand = self.player.hand.cards
        tricks_remaining = 8 - trick_number
        trick_cards = [c for _, c in current_trick.played_cards]

        # Kontext hry
        game_ctx = GameContext.build(
            self.player.index,
            all_scores,
            my_declaration=my_declaration
        )

        # Hodnotenie ruky
        hand_eval = self.evaluator.evaluate(
            hand, tricks_remaining, trick_cards, current_trick
        )

        # Zostav AIContext
        ctx = AIContext.build(
            self.player,
            self.memory,
            hand_eval,
            game_ctx,
            playable,
            current_trick
        )

        if self.logger:
            self.logger.log_strategy(
                self.player.name,
                "AI_V2",
                f"trick={trick_number + 1} "
                f"playable={playable} "
                f"outcome={ctx.trick_outcome}"
            )

        # Vyber kartu
        return self.selector.select(ctx)

    def reset(self):
        """Reset po skončení kola — ak stratégie majú stav."""
        for strategy in self.strategies:
            if hasattr(strategy, 'reset'):
                strategy.reset()

    @property
    def last_strategy(self) -> str:
        return self.selector.last_variant