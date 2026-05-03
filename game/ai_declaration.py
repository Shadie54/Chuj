# game/ai_declaration.py

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_strategies_const import Strategy
from config import SUITS, NUM_PLAYERS


class DeclarationAdvisor:
    def __init__(self, player: Player, memory: AIMemory,
                 difficulty: str, logger=None):
        self.player = player
        self.memory = memory
        self.difficulty = difficulty
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    # ------------------------------------------------------------------
    # Záväzok
    # ------------------------------------------------------------------

    def decide_declaration(self) -> str | None:
        if self.difficulty == "easy":
            return None
        hand = self.player.hand.cards
        if self._can_take_none(hand):
            self._log(Strategy.DECLARATION_NONE, "žiadne trestné karty")
            return "none"
        if self.difficulty == "hard" and self._can_take_all(hand):
            self._log(Strategy.DECLARATION_ALL, "dominancia")
            return "all"
        return None

    @staticmethod
    def _can_take_none(hand: list[Card]) -> bool:
        has_penalty = any(card.is_penalty_card for card in hand)
        has_special = any(card.is_special for card in hand)
        if has_penalty or has_special:
            return False
        return not any(c.rank in ("ace", "king") for c in hand)

    def _can_take_all(self, hand: list[Card]) -> bool:
        for suit in SUITS:
            suit_cards = [c for c in hand if c.suit == suit]
            if not suit_cards:
                continue
            highest_in_hand = max(suit_cards, key=lambda c: c.rank_order)
            unplayed = [c for c in self.memory.get_remaining(suit)
                        if c not in hand]
            if not unplayed:
                continue
            highest_unplayed = max(unplayed, key=lambda c: c.rank_order)
            if highest_in_hand.rank_order < highest_unplayed.rank_order:
                return False
        return True

    # ------------------------------------------------------------------
    # Vysvietenie
    # ------------------------------------------------------------------

    def decide_illumination(self,
                             first_player_index: int) -> tuple[bool, bool]:
        if self.difficulty == "easy":
            return False, False

        hand = self.player.hand.cards
        illuminate_leaf = False
        illuminate_acorn = False

        if self.difficulty in ("medium", "hard"):
            position = (self.player.index - first_player_index) % NUM_PLAYERS
            illuminate_leaf, leaf_debug = self._should_illuminate(
                hand, "leaf", position
            )
            illuminate_acorn, acorn_debug = self._should_illuminate(
                hand, "acorn", position
            )
            if self.logger:
                self.logger.log_illumination_decision(
                    self.player.name, "leaf", *leaf_debug, illuminate_leaf
                )
                self.logger.log_illumination_decision(
                    self.player.name, "acorn", *acorn_debug, illuminate_acorn
                )

        return illuminate_leaf, illuminate_acorn

    def _should_illuminate(self, hand: list[Card], suit: str,
                            position: int) -> tuple[bool, tuple]:
        special = next(
            (c for c in hand if c.is_special and c.suit == suit), None
        )
        if special is None:
            return False, ("none", "none", 0)

        reserves = [c for c in hand if c.suit == suit and not c.is_special]

        reserve_quality = self._reserve_quality(reserves) if reserves else "plonk"
        risk_level = self._hand_risk_level(hand, suit)
        compensation = self._compensation_count(hand, position)

        if len(reserves) == 0:
            return False, (reserve_quality, risk_level, compensation)

        if reserve_quality == "bad":
            return False, (reserve_quality, risk_level, compensation)

        result = self._illumination_decision(
            reserve_quality, risk_level, compensation
        )
        return result, (reserve_quality, risk_level, compensation)

    def _reserve_quality(self, reserves: list[Card]) -> str:
        if len(reserves) >= 3:
            return "strong"
        if len(reserves) == 2:
            high = [c for c in reserves if c.rank in ("ace", "king")]
            low = [c for c in reserves if c.rank in ("nine", "eight", "seven")]
            if len(high) == 2:
                return "bad"
            if len(high) == 1 and not low:
                return "bad"
            if len(high) == 1 and low:
                return "borderline"
            mid = [c for c in reserves if c.rank in ("under", "ten")]
            if len(mid) == 2:
                return "borderline"
            return "good"
        # 1 rezerva
        rank = reserves[0].rank
        if rank in ("ace", "king"):
            return "bad"
        if rank in ("under", "ten"):
            return "borderline"
        return "good"

    def _hand_risk_level(self, hand: list[Card], special_suit: str) -> str:
        worst = "low"
        for suit in SUITS:
            if suit == "bell":
                continue
            suit_cards = [
                c for c in hand
                if c.suit == suit and not c.is_special
            ]
            high_cards = [
                c for c in suit_cards
                if c.rank in ("ace", "king", "queen")
            ]
            if not high_cards:
                continue
            low_cards = [
                c for c in suit_cards
                if c.rank in ("nine", "eight", "seven")
            ]
            mid_cards = [
                c for c in suit_cards
                if c.rank in ("under", "ten")
            ]
            buffers = len(low_cards) + len(mid_cards)
            for _ in high_cards:
                if buffers == 0:
                    return "critical"
                elif buffers == 1 and worst == "low":
                    worst = "medium"
                buffers = max(0, buffers - 1)
        return worst

    def _compensation_count(self, hand: list[Card],
                             position: int) -> int:
        count = 0
        for suit in SUITS:
            suit_count = sum(1 for c in hand if c.suit == suit)
            if suit_count <= 1:
                count += 1
        if position > 0:
            count += 1
        if position == 3:
            count += 1
        return count

    @staticmethod
    def _illumination_decision(reserve_quality: str,
                                risk_level: str,
                                compensation: int) -> bool:
        if reserve_quality in ("strong", "good"):
            if risk_level == "low":
                return True
            if risk_level == "medium":
                return compensation >= 1
            if risk_level == "critical":
                return compensation >= 2
        if reserve_quality == "borderline":
            if risk_level == "low":
                return compensation >= 1
            if risk_level == "medium":
                return compensation >= 2
            if risk_level == "critical":
                return False
        return False