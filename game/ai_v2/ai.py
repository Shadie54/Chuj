# game/ai_v2/ai.py

import random
from game.player import Player
from game.card import Card
from game.trick import Trick
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEvaluator, GameContext
from game.ai_sweep.engine import SweepEngineV2
from game.ai_sweep.pipeline import SweepDecision
from game.ai_declaration import DeclarationAdvisor
from game.ai_play_none import NonePlayer
from game.ai_play_all import AllPlayer
from game.ai_v2.engine import AIEngine


class AIv2:
    def __init__(self, player: Player, difficulty: str = "hard", logger=None):
        self.player = player
        self.difficulty = difficulty
        self.logger = logger
        self.player_name = player.name

        self.memory = AIMemory(player.index)

        self.declaration_player: int | None = None
        self.declaration_type: str | None = None

        self.sweep_engine_v2 = SweepEngineV2(player, self.memory, logger)
        self.sweep_confidence = None
        self.sweep_attempt = None

        self.evaluator = HandEvaluator(self.memory)
        self.declaration_advisor = DeclarationAdvisor(
            player, self.memory, difficulty, logger
        )

        self.none_player = NonePlayer(player, self.memory, logger)
        self.all_player = AllPlayer(player, self.memory, logger)

        self.engine_v2 = AIEngine(player, self.memory, logger)

        self.last_strategy: str = ""

    def _log_sweep_90_eval(self, sweep_result, trick_number: int):
        """
        Čisto pozorovací log (výskum 90+ pravidla vs. sweep pipeline,
        claude/03_SWEEP_V2_HANDOFF.md §14) — NEOVPLYVŇUJE žiadne
        rozhodnutie, len zaznamená KAŽDÉ vyhodnotenie sweep pipeline,
        keď má hráč (self.player) už 90+ bodov. Pipeline dnes pri
        výpočte escape damage/EV nerozlišuje, že horníkove body by mu
        boli 0 (§13/player.py finalize_round) — cieľom je nazbierať dáta,
        kde presne sa to prejaví, pred akoukoľvek zmenou kódu.
        """
        from config import HIGH_SCORE_THRESHOLD
        if self.player.total_score < HIGH_SCORE_THRESHOLD:
            return
        if self.logger:
            self.logger.log_strategy(
                self.player_name, "SWEEP_90_EVAL",
                f"skóre={self.player.total_score} | štich={trick_number + 1} | "
                f"decision={sweep_result.decision.value} | "
                f"state={sweep_result.state.value} | "
                f"P={sweep_result.sweep_probability:.2f} | "
                f"EV={sweep_result.expected_value:.2f} | "
                f"{' | '.join(sweep_result.reasoning_chain)}"
            )

    def decide_declaration(self) -> str | None:
        return self.declaration_advisor.decide_declaration()

    def decide_illumination(self, first_player_index: int,
                            all_scores: list[int] | None = None) -> tuple[bool, bool]:
        return self.declaration_advisor.decide_illumination(
            first_player_index, all_scores
        )

    def decide_card(self, playable: list[Card],
                    current_trick: Trick,
                    trick_number: int,
                    all_scores: list[int] | None = None) -> Card:
        if self.difficulty == "easy":
            return random.choice(playable)

        my_declaration = (
            self.declaration_type
            if self.declaration_player == self.player.index
            else None
        )

        scores = all_scores if all_scores is not None \
            else [self.player.total_score] * 4

        hand = self.player.hand.cards
        tricks_remaining = 8 - trick_number
        trick_cards = [c for _, c in current_trick.played_cards]

        game_ctx = GameContext.build(
            self.player.index, scores,
            my_declaration=my_declaration
        )
        hand_eval = self.evaluator.evaluate(
            hand, tricks_remaining, trick_cards, current_trick
        )

        if self.declaration_type == "none":
            return self.none_player.decide(
                playable, current_trick, hand_eval,
                declaration_player=self.declaration_player
            )

        if my_declaration == "all":
            return self.all_player.decide(playable, hand_eval)

        sweep_result = self.sweep_engine_v2.evaluate(
            hand_eval, trick_number, current_trick, playable
        )
        if self.logger:
            self.logger.log_sweep_pipeline(
                self.player_name, sweep_result, trick_number + 1
            )
        self._log_sweep_90_eval(sweep_result, trick_number)
        if sweep_result.decision == SweepDecision.YES:
            if sweep_result.recommended_card in playable:
                self.last_strategy = "SWEEP_COMMIT"
                if self.logger:
                    self.logger.log_strategy(
                        self.player_name, "SWEEP_COMMIT",
                        str(sweep_result.recommended_card)
                    )
                return sweep_result.recommended_card

        card = self.engine_v2.decide(
            playable, current_trick, trick_number,
            scores, my_declaration
        )
        self.last_strategy = self.engine_v2.last_strategy
        return card

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
        self.sweep_engine_v2.reset()
        self.engine_v2.reset()

    def __repr__(self) -> str:
        return f"AIv2({self.player.name}, difficulty={self.difficulty})"