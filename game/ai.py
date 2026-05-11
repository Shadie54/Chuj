# game/ai.py

import random
from game.player import Player
from game.card import Card
from game.trick import Trick
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEvaluator, GameContext
from game.ai_situation import SituationDetector
from game.ai_card_select import CardSelector
from game.ai_sweep import SweepPipeline, SweepDecision
from game.ai_declaration import DeclarationAdvisor



class AI:
    def __init__(self, player: Player, difficulty: str = "hard",
                 logger=None):

        self.player = player
        self.difficulty = difficulty
        self.logger = logger
        self.player_name = player.name

        self.memory = AIMemory(player.index)

        # Záväzok
        self.declaration_player: int | None = None
        self.declaration_type: str | None = None

        # Sweep
        self.sweep_pipeline = SweepPipeline(player, self.memory, logger)

        # Moduly
        self.evaluator = HandEvaluator(self.memory)
        self.situator = SituationDetector(player, self.memory, difficulty)
        self.selector = CardSelector(player, self.memory, logger)
        self.declaration_advisor = DeclarationAdvisor(
            player, self.memory, difficulty, logger
        )
        # Sweep
        self.sweep_confidence = None
        self.sweep_attempt = None

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player_name, strategy, details)

    # ------------------------------------------------------------------
    # Záväzok a vysvietenie
    # ------------------------------------------------------------------

    def decide_declaration(self) -> str | None:
        return self.declaration_advisor.decide_declaration()

    def decide_illumination(self, first_player_index: int,
                            all_scores: list[int] | None = None) -> tuple[bool, bool]:
        return self.declaration_advisor.decide_illumination(
            first_player_index, all_scores
        )

    # ------------------------------------------------------------------
    # Hlavný vstupný bod
    # ------------------------------------------------------------------

    def decide_card(self, playable: list[Card],
                    current_trick: Trick,
                    trick_number: int,
                    all_scores: list[int] | None = None) -> Card:
        if self.difficulty == "easy":
            return random.choice(playable)

        hand = self.player.hand.cards
        tricks_remaining = 8 - trick_number
        trick_cards = [c for _, c in current_trick.played_cards]

        # skóre?
        ctx = GameContext.build(
            self.player.index,
            all_scores if all_scores is not None
            else [self.player.total_score] * 4
        )

        # --- KROK 1: HAND_EVAL ---
        hand_eval = self.evaluator.evaluate(
            hand, tricks_remaining, trick_cards, current_trick
        )

        # --- SWEEP PIPELINE ---
        sweep_result = self.sweep_pipeline.evaluate(
            hand_eval, trick_number,
        )
        if self.logger:
            self.logger.log_sweep_pipeline(
                self.player_name, sweep_result, trick_number + 1
            )

        if sweep_result.decision == SweepDecision.YES:
            if sweep_result.recommended_card in playable:
                self._log("SWEEP_COMMIT", str(sweep_result.recommended_card))
                return sweep_result.recommended_card
            else:
                # BUG guard: sweep pipeline vrátila kartu mimo playable
                self._log(
                    "SWEEP_BUG",
                    f"recommended {sweep_result.recommended_card} "
                    f"not in playable {playable} — fallback to default"
                )

        # WATCHING → default logika pokračuje

        if sweep_result.decision == SweepDecision.YES:
            if sweep_result.recommended_card in playable:
                self._log("SWEEP_COMMIT", str(sweep_result.recommended_card))
                return sweep_result.recommended_card

        # WATCHING → default logika pokračuje

        # --- KROK 2: SITUATION ---
        situation = self.situator.determine(hand_eval, playable, current_trick, ctx)

        # --- KROK 3: MODE ---
        mode = self.situator.to_mode(situation, current_trick)

        # --- KROK 4: CARD ---
        card = self.selector.select(
            mode, situation, hand_eval, playable, current_trick, ctx
        )

        self._log(f"{situation}/{mode}", str(card))
        return card

    # ------------------------------------------------------------------
    # Verejné rozhranie — pamäť
    # ------------------------------------------------------------------

    def record_trick(self, played_cards: list[tuple[int, Card]],
                     winner_index: int, _trick_number: int):
        self.memory.record_trick(played_cards, winner_index)

    def record_illumination(self, player_index: int,
                             leaf: bool, acorn: bool):
        self.memory.record_illumination(player_index, leaf, acorn)

    def record_declaration(self, player_index: int,
                            declaration: str | None):
        if declaration:
            self.declaration_player = player_index
            self.declaration_type = declaration

    def reset_memory(self):
        self.memory.reset()
        self.declaration_player = None
        self.declaration_type = None
        self.sweep_attempt = False
        self.sweep_confidence = None
        self.sweep_pipeline.reset()


    def __repr__(self) -> str:
        return f"AI({self.player.name}, difficulty={self.difficulty})"