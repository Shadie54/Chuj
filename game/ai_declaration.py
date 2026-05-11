# game/ai_declaration.py

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_strategies_const import Strategy
from config import SUITS, NUM_PLAYERS, HIGH_SCORE_THRESHOLD


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
        # TODO: "all" logika nie je hotová
        # if self.difficulty == "hard" and self._can_take_all(hand):
        #     return "all"
        if self._can_take_none(self.player.hand.cards):
            self._log(Strategy.DECLARATION_NONE, "žiadne trestné karty")
            return "none"
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

    def decide_illumination(self, first_player_index: int,
                            all_scores: list[int] | None = None) -> tuple[bool, bool]:
        if self.difficulty == "easy":
            return False, False

        hand = self.player.hand.cards
        illuminate_leaf = False
        illuminate_acorn = False

        is_leader = False
        if all_scores is not None:
            my_score = self.player.total_score
            max_score = max(all_scores)
            is_leader = my_score == max_score and max_score > 0

        if self.difficulty in ("medium", "hard"):
            position = (self.player.index - first_player_index) % NUM_PLAYERS
            illuminate_leaf, leaf_debug = self._should_illuminate(
                hand, "leaf", position, is_leader
            )
            illuminate_acorn, acorn_debug = self._should_illuminate(
                hand, "acorn", position, is_leader
            )
            if self.logger:
                rq, rl, reason, comp, cbd, _ = leaf_debug
                self.logger.log_illumination_decision(
                    self.player.name, "leaf", rq, rl, comp, cbd, reason, illuminate_leaf
                )
                rq, rl, reason, comp, cbd, _ = acorn_debug
                self.logger.log_illumination_decision(
                    self.player.name, "acorn", rq, rl, comp, cbd, reason, illuminate_acorn
                )

        return illuminate_leaf, illuminate_acorn

    def _should_illuminate(self, hand, suit, position, is_leader=False):
        special = next((c for c in hand if c.is_special and c.suit == suit), None)
        if special is None:
            return False, ("none", "n/a", "n/a", 0, {}, "no_special")

        reserves = [c for c in hand if c.suit == suit and not c.is_special]
        reserve_quality = self._reserve_quality(reserves) if reserves else "plonk"
        risk_level = self._hand_risk_level(hand, suit)
        compensation, comp_breakdown = self._compensation_count(hand, position)

        if self.player.total_score >= HIGH_SCORE_THRESHOLD:
            veto = self._is_safe_to_illuminate_at_high_score(hand)
            if veto:
                return False, (reserve_quality, risk_level, veto, compensation, comp_breakdown, veto)

        if len(reserves) == 0:
            return False, (reserve_quality, risk_level, "no_reserves", compensation, comp_breakdown, "no_reserves")

        if reserve_quality == "bad":
            return False, (reserve_quality, risk_level, "bad_reserves", compensation, comp_breakdown, "bad_reserves")

        if is_leader and reserve_quality == "borderline":
            return False, (reserve_quality, risk_level, "leader_borderline", compensation, comp_breakdown,
                           "leader_borderline")

        result = self._illumination_decision(reserve_quality, risk_level, compensation)
        reason = "decision_yes" if result else "decision_no"
        return result, (reserve_quality, risk_level, reason, compensation, comp_breakdown, reason)

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
        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]
        uncovered_hearts = max(0, len(high_hearts) - len(low_hearts))
        expected_penalty = uncovered_hearts * 4

        for suit in ("leaf", "acorn"):
            suit_cards = [c for c in hand if c.suit == suit and not c.is_special]
            high = [c for c in suit_cards if c.rank in ("ace", "king")]
            low = [c for c in suit_cards if c.rank in ("seven", "eight", "nine")]
            mid = [c for c in suit_cards if c.rank in ("under", "ten")]
            buffers = len(low) + len(mid)
            uncovered = max(0, len(high) - buffers)
            expected_penalty += uncovered * 2

        if expected_penalty == 0:
            return "low"
        elif expected_penalty <= 4:
            return "medium"
        else:
            return "critical"

    def _compensation_count(self, hand: list[Card], position: int) -> tuple[int, dict]:
        breakdown = {}
        void_suits = []
        for suit in SUITS:
            suit_cards = [c for c in hand if c.suit == suit]
            if len(suit_cards) == 0:
                void_suits.append(suit)
            elif len(suit_cards) == 1:
                # 1 karta — len ak je nízka (nie A/K/Q)
                if suit_cards[0].rank not in ("ace", "king", "over"):
                    void_suits.append(suit)
        if void_suits:
            breakdown["void"] = void_suits
        if position == 3:
            breakdown["position"] = True
        count = len(void_suits) + (1 if position == 3 else 0)
        return count, breakdown

    def _is_safe_to_illuminate_at_high_score(self, hand: list[Card]) -> str | None:
        """Vráti None ak je bezpečné, inak dôvod veta."""
        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]
        if len(low_hearts) < len(high_hearts):
            return "high_score_unprotected_hearts"

        for suit in ("bell",):
            suit_cards = [c for c in hand if c.suit == suit and not c.is_special]
            high = [c for c in suit_cards if c.rank in ("ace", "king")]
            low = [c for c in suit_cards if c.rank in ("seven", "eight", "nine")]
            if high and not low:
                return "high_score_naked_high"

        return None

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