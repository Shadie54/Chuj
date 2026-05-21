# game/ai_situation.py

import random
from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval, GameContext, DecisionContext
from game.ai_strategies_const import Situation, Mode
from config import NUM_PLAYERS, SUITS



class SituationDetector:
    def __init__(self, player: Player, memory: AIMemory,
                 difficulty: str = "hard"):
        self.player = player
        self.memory = memory
        self.difficulty = difficulty

    def determine(self, dctx: DecisionContext) -> str:
        if dctx.is_leader:
            return self._leader(dctx)
        else:
            return self._follower(dctx)

    @staticmethod
    def to_mode(situation: str) -> str:
        mapping = {
            Situation.LEADER_SAFE: Mode.SAFE,
            Situation.LEADER_FORCED: Mode.OPEN,
            Situation.LEADER_AGGRESSIVE: Mode.TAKE,
            Situation.LEADER_HIGH_SCORE: Mode.SAFE,
            Situation.LEADER_RISK: Mode.OPEN,
            Situation.FOLLOWER_SAFE: Mode.SAFE,
            Situation.FOLLOWER_VOID: Mode.OPEN,
            Situation.FOLLOWER_FORCED_CLEAN: Mode.TAKE,
            Situation.FOLLOWER_FORCED_POINTS: Mode.TAKE,
            Situation.FOLLOWER_FREE_TAKE: Mode.TAKE,
            Situation.FOLLOWER_WAIT: Mode.OPEN,
            Situation.FOLLOWER_RISK: Mode.RISK,
        }
        return mapping.get(situation, Mode.OPEN)

    def _leader(self, dctx: DecisionContext) -> str:
        playable = dctx.playable
        hand_eval = dctx.hand_eval
        game_ctx = dctx.game_ctx

        if self.difficulty == "hard":
            for suit in ("leaf", "acorn"):  # ← namiesto SUITS
                if self.memory.is_special_gone(suit):
                    continue
                holders = dctx.special_holders[suit]
                if not holders:
                    continue
                if self.player.index in holders:
                    continue
                suit_cards = [
                    c for c in playable
                    if c.suit == suit
                       and not c.is_special
                       and c.rank not in ("ace", "king")
                ]
                if suit_cards:
                    # Veto — ak je to posledná escape a ostanú len trap karty
                    remaining_non_special = [
                        c for c in playable
                        if c.suit == suit
                           and not c.is_special
                           and c.rank not in ("ace", "king")
                           and c != min(suit_cards, key=lambda c: c.rank_order)
                    ]
                    high_cards = [
                        c for c in playable
                        if c.suit == suit
                           and not c.is_special
                           and c.rank in ("ace", "king")
                    ]
                    if not remaining_non_special and high_cards:
                        continue  # preskočíme — zahodíme jedinú escape
                    return Situation.LEADER_AGGRESSIVE

        if game_ctx.is_high_score:
            return self._leader_high_score(dctx)

        escape_candidates = [
            c for c in hand_eval.escape_cards
            if c in playable
               and not c.is_special
        ]
        if escape_candidates:
            return Situation.LEADER_SAFE

        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            special = next(
                (c for c in playable if c.is_special and c.suit == suit), None
            )
            if special is None:
                continue
            suit_cards = [c for c in playable if c.suit == suit and not c.is_special]
            if not suit_cards:
                continue
            all_high = all(c.rank in ("ace", "king") for c in suit_cards)
            if not all_high:
                continue
            remaining_higher = [
                c for c in self.memory.remaining[suit]
                if c.rank_order > special.rank_order and not c.is_special
            ]
            if remaining_higher:
                return Situation.LEADER_RISK

        return Situation.LEADER_FORCED

    def _leader_high_score(self, dctx: DecisionContext) -> str:
        playable = dctx.playable
        hand_eval = dctx.hand_eval
        hand = self.player.hand.cards

        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]

        surplus_low = len(low_hearts) - len(high_hearts)
        if surplus_low > 0:
            low_heart_playable = [
                c for c in playable
                if c.suit == "heart"
                   and c.rank in ("seven", "eight", "nine")
            ]
            if low_heart_playable:
                return Situation.LEADER_HIGH_SCORE

        non_heart_escape = [
            c for c in hand_eval.escape_cards
            if c.suit != "heart" and c in playable
        ]
        if non_heart_escape:
            return Situation.LEADER_SAFE

        return Situation.LEADER_FORCED

    def _follower(self, dctx: DecisionContext) -> str:
        playable = dctx.playable
        lead_cards = dctx.lead_cards

        if not lead_cards:
            return Situation.FOLLOWER_VOID

        if self._trick_is_free_to_take(dctx):
            return Situation.FOLLOWER_FREE_TAKE

        current_best = self._get_current_best(dctx.trick)
        can_underplay = any(
            c.rank_order < current_best.rank_order
            for c in lead_cards
        ) if current_best else False

        # FOLLOWER_RISK — tretí v poradí, trap A/K + jedna escape, živý nevysvietený horník
        if not dctx.is_last and len(dctx.players_after) == 1:
            if not dctx.game_ctx.is_high_score:
                if not (80 <= dctx.game_ctx.my_score <= 89):
                    risk = self._should_risk_trap(dctx)
                    if risk:
                        return Situation.FOLLOWER_RISK

        # Posledný + trap bell A/K + čistý štich → FOLLOWER_FORCED_CLEAN
        if dctx.is_last and not dctx.trick_has_penalty:
            high_bell = [
                c for c in lead_cards
                if c.suit == "bell"
                   and c.rank in ("ace", "king")
                   and not c.is_special
            ]
            if high_bell:
                return Situation.FOLLOWER_FORCED_CLEAN

        if can_underplay:
            return Situation.FOLLOWER_SAFE

        i_will_likely_win = (
                len(lead_cards) == 1
                and not any(
            c.rank_order > lead_cards[0].rank_order
            for c in self.memory.remaining[lead_cards[0].suit]
        )
                and not any(
            c.suit == lead_cards[0].suit
            and c.rank_order > lead_cards[0].rank_order
            for _, c in dctx.trick.played_cards
        )
        )

        if not dctx.trick_has_penalty:
            if dctx.is_last and not can_underplay:
                return Situation.FOLLOWER_FORCED_CLEAN
            else:
                if dctx.can_be_beaten and not i_will_likely_win:
                    return Situation.FOLLOWER_WAIT
                else:
                    return Situation.FOLLOWER_FORCED_CLEAN
        else:
            if dctx.is_last:
                return Situation.FOLLOWER_FORCED_POINTS
            else:
                if dctx.can_be_beaten and not i_will_likely_win:
                    return Situation.FOLLOWER_WAIT
                else:
                    return Situation.FOLLOWER_FORCED_POINTS

    def _trick_is_free_to_take(self, dctx: DecisionContext) -> bool:
        trick = dctx.trick
        lead_suit = dctx.lead_suit
        playable = dctx.playable

        if lead_suit is None:
            return False
        if lead_suit == "heart":
            return False

        lead_cards = dctx.lead_cards
        if not lead_cards:
            return False

        has_high = any(c.rank in ("ace", "king") for c in lead_cards)
        if not has_high:
            return False

        if lead_suit not in ("leaf", "acorn"):
            return False

        if self.memory.is_special_gone(lead_suit):
            return False

        illuminator = self.memory.illuminated_by[lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return False

        played_indices = {idx for idx, _ in trick.played_cards}
        if illuminator not in played_indices:
            return False

        any_special_in_trick = any(
            c.is_special for _, c in trick.played_cards
        )
        if any_special_in_trick:
            return False

        other_suit = "acorn" if lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            other_holders = dctx.special_holders[other_suit]
            for player_idx in dctx.players_after:
                is_void_lead = lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return False

        return True

    @staticmethod
    def _trick_has_penalty(trick: Trick) -> bool:
        return trick.total_base_points > 0 or any(
            c.is_special for _, c in trick.played_cards
        )

    @staticmethod
    def _get_current_best(trick: Trick) -> Card | None:
        if not trick.played_cards:
            return None
        winner_idx = trick.get_winner_index()
        for idx, card in trick.played_cards:
            if idx == winner_idx:
                return card
        return None

    @staticmethod
    def _get_play_order(trick: Trick) -> list[int]:
        return [(trick.leader_index + i) % NUM_PLAYERS
                for i in range(NUM_PLAYERS)]

    def _should_risk_trap(self, dctx: DecisionContext) -> bool:

        # Veto — ak mám horníka sám, nie je čo riskovať
        my_special = next(
            (c for c in dctx.lead_cards if c.is_special), None
        )
        if my_special is not None:
            return False

        lead_suit = dctx.lead_suit
        if lead_suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(lead_suit):
            return False
        # Veto — horník už v štichu
        special_in_trick = any(
            c.is_special and c.suit == lead_suit
            for _, c in dctx.trick.played_cards
        )
        if special_in_trick:
            return False
        if self.memory.illuminated_by[lead_suit] is not None:
            return False

        lead_cards = dctx.lead_cards
        trap_high = [
            c for c in lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        escape_low = [
            c for c in lead_cards
            if c.rank not in ("ace", "king") and not c.is_special
        ]
        if not trap_high or len(escape_low) != 1:
            return False

        # Randomness podľa skóre
        rank = dctx.game_ctx.score_rank
        if rank == 1:
            risk_chance = 1.0
        elif rank == 4:
            risk_chance = 1.0
        else:
            risk_chance = 1.0

        return random.random() < risk_chance