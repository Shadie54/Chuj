# game/ai_situation.py

import traceback
from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval, GameContext
from game.ai_strategies_const import Situation, Mode
from config import NUM_PLAYERS, SUITS



class SituationDetector:
    def __init__(self, player: Player, memory: AIMemory,
                 difficulty: str = "hard"):
        self.player = player
        self.memory = memory
        self.difficulty = difficulty

    def determine(self, hand_eval: HandEval,
                  playable: list[Card],
                  trick: Trick,
                  ctx: GameContext | None = None) -> str:
        is_leader = len(trick.played_cards) == 0
        if is_leader:
            return self._leader(hand_eval, playable, ctx)
        else:
            return self._follower(playable, trick)

    def to_mode(self, situation: str, trick: Trick) -> str:
        mapping = {
            Situation.LEADER_SAFE: Mode.SAFE,
            Situation.LEADER_FORCED: Mode.OPEN,
            Situation.LEADER_AGGRESSIVE: Mode.TAKE,
            Situation.LEADER_HIGH_SCORE: Mode.SAFE,
            Situation.FOLLOWER_SAFE: Mode.SAFE,
            Situation.FOLLOWER_VOID: Mode.OPEN,
            Situation.FOLLOWER_FORCED: Mode.TAKE,
            Situation.FOLLOWER_WAIT: Mode.OPEN,
            Situation.FOLLOWER_FREE_TAKE: Mode.TAKE,
            Situation.FOLLOWER_CONTROLLED: Mode.TAKE,
        }
        mode = mapping.get(situation)
        if mode is None:
            worst = self.evaluate_post_win_risk(trick)
            return Mode.TAKE if worst <= 4 else Mode.SAFE
        return mode

    def _leader(self, hand_eval: HandEval,
                playable: list[Card],
                ctx: GameContext | None = None) -> str:

        if self.difficulty == "hard":
            for suit in SUITS:
                if self.memory.is_special_gone(suit):
                    continue
                holders = self.memory.who_has_special(suit)
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
                    return Situation.LEADER_AGGRESSIVE

        # 90+ — špeciálna logika
        if ctx and ctx.is_high_score:
            return self._leader_high_score(playable, hand_eval)

        non_heart_escape = [
            c for c in hand_eval.escape_cards
            if c.suit != "heart" and c in playable
        ]
        if non_heart_escape:
            return Situation.LEADER_SAFE

        return Situation.LEADER_FORCED

    def _leader_high_score(self, playable: list[Card],
                           hand_eval: HandEval) -> str:
        """
        90+ logika pre leadera:
        - Veď nízkou červeňou ak mám prebytočné buffery
        - Inak escape non-heart → LEADER_SAFE
        - Inak LEADER_FORCED
        """
        hand = self.player.hand.cards
        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]

        # Prebytočné buffery — môžem zahodiť nízku červeň
        surplus_low = len(low_hearts) - len(high_hearts)
        if surplus_low > 0:
            low_heart_playable = [
                c for c in playable
                if c.suit == "heart"
                   and c.rank in ("seven", "eight", "nine")
            ]
            if low_heart_playable:
                return Situation.LEADER_HIGH_SCORE

        # Escape non-heart — štandardná safe logika bez červeňov
        non_heart_escape = [
            c for c in hand_eval.escape_cards
            if c.suit != "heart" and c in playable
        ]
        if non_heart_escape:
            return Situation.LEADER_SAFE

        return Situation.LEADER_FORCED

    def _follower(self, playable: list[Card],
                  trick: Trick) -> str:
        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]

        if not lead_cards:
            return Situation.FOLLOWER_VOID

        if self._trick_is_free_to_take(playable, trick):
            return Situation.FOLLOWER_FREE_TAKE

        is_last = len(trick.played_cards) == NUM_PLAYERS - 1
        trick_has_penalty = self._trick_has_penalty(trick) or any(
            c.is_special for c in lead_cards
        )

        current_best = self._get_current_best(trick)
        can_underplay = any(
            c.rank_order < current_best.rank_order
            for c in lead_cards
        ) if current_best else False

        if can_underplay:
            return Situation.FOLLOWER_SAFE

        players_after = self._get_players_after_me(trick)
        trick_cards = [c for _, c in trick.played_cards]
        my_lowest = min(lead_cards, key=lambda c: c.rank_order)
        can_be_beaten = self.memory.can_anyone_beat(
            my_lowest, players_after, trick_cards)

        i_will_likely_win = (
                len(lead_cards) == 1
                and not any(
            c.rank_order > lead_cards[0].rank_order
            for c in self.memory.remaining[lead_cards[0].suit]
        )
                and not any(
            c.suit == lead_cards[0].suit
            and c.rank_order > lead_cards[0].rank_order
            for _, c in trick.played_cards
        )
        )

        if not trick_has_penalty:
            if is_last and not can_underplay:
                return Situation.FOLLOWER_CONTROLLED
            else:
                if can_be_beaten and not i_will_likely_win:
                    return Situation.FOLLOWER_WAIT
                else:
                    return Situation.FOLLOWER_FORCED
        else:
            if is_last:
                return Situation.FOLLOWER_FORCED
            else:
                if can_be_beaten and not i_will_likely_win:
                    return Situation.FOLLOWER_WAIT
                else:
                    return Situation.FOLLOWER_FORCED

    def _trick_is_free_to_take(self, playable: list[Card],
                               trick: Trick) -> bool:
        """
        štich je vhodný na bezpečné zbavenie sa A/K.

        Spúšťač: vysvietený horník lead-suitu je u skoršieho hráča ktorý
        v tomto štichu už zahral inú kartu (nie horníka)
        → môj A/K v lead suit je trap, dumpnem ho zadarmo

        Veto: niekto po mne je preukázane void na lead suit A môže mať
        druhého horníka → riziko chytenia 4-16b
        """
        lead_suit = trick.lead_suit
        if lead_suit is None:
            return False

        if lead_suit == "heart":
            return False

        lead_cards = [c for c in playable if c.suit == lead_suit]
        if not lead_cards:
            return False

        has_high = any(c.rank in ("ace", "king") for c in lead_cards)
        if not has_high:
            return False

        if lead_suit not in ("leaf", "acorn"):
            return False

        # Horník tejto farby už padol — FREE_TAKE scenár nedáva zmysel
        if self.memory.is_special_gone(lead_suit):
            return False

        illuminator = self.memory.illuminated_by[lead_suit]
        if illuminator is None or illuminator == self.player.index:
            return False

        played_indices = {idx for idx, _ in trick.played_cards}
        if illuminator not in played_indices:
            return False

        hornik_played = any(
            c.is_special and c.suit == lead_suit
            for _, c in trick.played_cards
        )
        if hornik_played:
            return False

        # Veto: druhý horník môže prísť od void hráča po mne
        other_suit = "acorn" if lead_suit == "leaf" else "leaf"
        if not self.memory.is_special_gone(other_suit):
            players_after = self._get_players_after_me(trick)
            other_holders = self.memory.who_has_special(other_suit)
            for player_idx in players_after:
                is_void_lead = lead_suit in self.memory.void_suits[player_idx]
                could_have_other = player_idx in other_holders
                if is_void_lead and could_have_other:
                    return False

        return True

    def evaluate_post_win_risk(self, trick: Trick) -> int:
        lead_suit = trick.lead_suit
        if not lead_suit:
            return 0
        players_after = self._get_players_after_me(trick)
        return self.memory.worst_possible_discard(lead_suit, players_after)

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

    def _get_players_after_me(self, trick: Trick) -> list[int]:
        played_indices = {idx for idx, _ in trick.played_cards}
        order = self._get_play_order(trick)
        return [
            i for i in order
            if i not in played_indices and i != self.player.index
        ]