# game/ai_hand_eval.py

from dataclasses import dataclass
from game.card import Card
from game.trick import Trick
from game.ai_memory import AIMemory
from config import NUM_PLAYERS, HIGH_SCORE_THRESHOLD

# ------------------------------------------------------------------
# HandEval — snapshot ruky pred každým ťahom
# ------------------------------------------------------------------

@dataclass
class HandEval:
    profiles: dict                # dict[str, SuitProfile]
    void_suits: list[str]
    trap_cards: list[Card]
    escape_cards: list[Card]
    tricks_remaining: int
    i_will_be_leader: bool

@dataclass
class GameContext:
    my_score: int
    all_scores: list[int]
    is_high_score: bool      # my_score >= 90
    score_rank: int          # 1 = vediem, 4 = posledný
    gap_to_leader: int       # o koľko zaostávam za lídrom (0 ak som líder)
    gap_to_last: int         # o koľko som pred posledným (0 ak som posledný)
    my_declaration: str | None = None  # ← nové

    @staticmethod
    def build(my_index: int, all_scores: list[int],
              my_declaration: str | None = None) -> "GameContext":
        my_score = all_scores[my_index]
        rank = sorted(all_scores, reverse=True).index(my_score) + 1
        return GameContext(
            my_score=my_score,
            all_scores=all_scores,
            is_high_score=my_score >= HIGH_SCORE_THRESHOLD,
            score_rank=rank,
            gap_to_leader=max(all_scores) - my_score,
            gap_to_last=my_score - min(all_scores),
            my_declaration=my_declaration,
        )

# ------------------------------------------------------------------
# HandEvaluator
# ------------------------------------------------------------------

class HandEvaluator:
    def __init__(self, memory: AIMemory):
        self.memory = memory

    def evaluate(self, hand: list[Card],
                 tricks_remaining: int,
                 trick_cards: list[Card],
                 trick: Trick) -> HandEval:
        """
        Snapshot stavu ruky cez SuitProfile.
        Každá farba sa hodnotí samostatne s coverage = remaining + trick karty.
        """
        profiles = self.memory.build_all_profiles(hand, trick_cards)

        void_suits = [s for s, p in profiles.items() if p.is_void]

        trap_cards = [
            c for p in profiles.values()
            for c in p.trap_cards
        ]
        escape_cards = [
            c for p in profiles.values()
            for c in p.escape_cards
        ]

        i_will_be_leader = len(trick.played_cards) == NUM_PLAYERS - 1

        return HandEval(
            profiles=profiles,
            void_suits=void_suits,
            trap_cards=trap_cards,
            escape_cards=escape_cards,
            tricks_remaining=tricks_remaining,
            i_will_be_leader=i_will_be_leader
        )