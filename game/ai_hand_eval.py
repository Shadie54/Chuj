# game/ai_hand_eval.py

from dataclasses import dataclass, field
from game.card import Card
from game.trick import Trick
from game.player import Player
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
@dataclass
class DecisionContext:
    # --- Vstupné objekty ---
    hand_eval: HandEval
    game_ctx: GameContext
    playable: list[Card]
    trick: Trick

    # --- Vypočítané raz ---
    is_leader: bool
    is_last: bool
    lead_suit: str | None
    lead_cards: list[Card]
    players_after: list[int]
    someone_takes: str
    can_be_beaten: bool
    trick_has_penalty: bool
    protected_suits: set[str]
    exhaustable_suits: set[str]
    special_holders: dict[str, set[int]]

    @staticmethod
    def build(player: Player,
              memory: AIMemory,
              hand_eval: HandEval,
              game_ctx: GameContext,
              playable: list[Card],
              trick: Trick) -> "DecisionContext":

        is_leader = len(trick.played_cards) == 0
        is_last = len(trick.played_cards) == NUM_PLAYERS - 1
        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit] if lead_suit else []

        play_order = [(trick.leader_index + i) % NUM_PLAYERS
                      for i in range(NUM_PLAYERS)]
        played_indices = {idx for idx, _ in trick.played_cards}
        players_after = [
            i for i in play_order
            if i not in played_indices and i != player.index
        ]

        trick_cards = [c for _, c in trick.played_cards]

        # Vypočítaj winner_index pre is_last
        winner_index = None
        if is_last and trick.played_cards:
            winner_index = trick.get_winner_index()

        someone_takes = memory.will_someone_else_take(
            trick.played_cards, players_after,
            is_last=is_last,
            winner_index=winner_index
        )

        can_be_beaten = False
        if lead_cards:
            my_lowest = min(lead_cards, key=lambda c: c.rank_order)
            can_be_beaten = memory.can_anyone_beat(
                my_lowest, players_after, trick_cards
            )

        trick_has_penalty = (
            trick.total_base_points > 0 or
            any(c.is_special for _, c in trick.played_cards)
        )

        # Protected suits
        protected_suits = set()
        for suit in ("leaf", "acorn"):
            if memory.illuminated_by[suit] != player.index:
                continue
            if memory.is_special_gone(suit):
                continue
            reserves = [
                c for c in player.hand.cards
                if c.suit == suit and not c.is_special
            ]
            if len(reserves) <= 3:
                protected_suits.add(suit)

        # Exhaustable suits
        exhaustable_suits = set()
        for suit in ("leaf", "acorn"):
            if memory.illuminated_by[suit] != player.index:
                continue
            reserves = [
                c for c in player.hand.cards
                if c.suit == suit and not c.is_special
            ]
            if len(reserves) < 4:
                continue
            high_reserves = [c for c in reserves if c.rank in ("ace", "king")]
            if len(high_reserves) == 0:
                exhaustable_suits.add(suit)

        # Special holders
        special_holders = {
            suit: memory.who_has_special(suit)
            for suit in ("leaf", "acorn")
        }

        return DecisionContext(
            hand_eval=hand_eval,
            game_ctx=game_ctx,
            playable=playable,
            trick=trick,
            is_leader=is_leader,
            is_last=is_last,
            lead_suit=lead_suit,
            lead_cards=lead_cards,
            players_after=players_after,
            someone_takes=someone_takes,
            can_be_beaten=can_be_beaten,
            trick_has_penalty=trick_has_penalty,
            protected_suits=protected_suits,
            exhaustable_suits=exhaustable_suits,
            special_holders=special_holders,
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