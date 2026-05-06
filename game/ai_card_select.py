# game/ai_card_select.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval
from game.ai_strategies_const import Strategy, Situation, Mode
from config import NUM_PLAYERS, SUITS


class CardSelector:
    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def select(self, mode: str, situation: str,
               hand_eval: HandEval,
               playable: list[Card],
               trick: Trick) -> Card:
        is_leader = len(trick.played_cards) == 0
        if mode == Mode.SAFE:
            return self._play_safe(playable, trick, is_leader, hand_eval)
        elif mode == Mode.TAKE:
            return self._play_take(playable, trick, situation)
        elif mode == Mode.OPEN:
            return self._play_open(playable, trick, situation, hand_eval)
        return min(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # SAFE
    # ------------------------------------------------------------------

    def _play_safe(self, playable: list[Card],
                   trick: Trick, is_leader: bool,
                   hand_eval: HandEval) -> Card:
        if is_leader:
            protected = self._protected_suits()

            escape_playable = [
                c for c in hand_eval.escape_cards
                if c in playable
                   and not c.is_special
                   and c.suit not in protected
            ]

            if escape_playable:
                card = min(escape_playable, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"escape: {card}")
                return card

            exhaust_cards = [
                c for c in playable
                if not c.is_special
                   and (c.suit not in protected
                        or self._can_exhaust_suit(c.suit))
            ]
            if exhaust_cards:
                card = min(exhaust_cards, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"exhaust fallback: {card}")
                return card

            non_special = [
                c for c in playable
                if not c.is_special or self._special_is_safe_lead(c)
            ]
            pool = non_special if non_special else playable
            card = min(pool, key=lambda c: c.rank_order)
            self._log(Strategy.SAFE_LEAD, f"last resort: {card}")
            return card

        else:
            lead_suit = trick.lead_suit
            current_best = self._get_current_best(trick)
            lead_cards = [c for c in playable if c.suit == lead_suit]
            underplay = [
                c for c in lead_cards
                if current_best and c.rank_order < current_best.rank_order
            ]
            if underplay:
                # Horník má vždy prioritu — zbavíme sa bomby
                specials_under = [c for c in underplay if c.is_special]
                if specials_under:
                    card = specials_under[0]
                    self._log(Strategy.DUMP_SPECIAL, f"underplay horník: {card}")
                    return card
                card = max(underplay, key=lambda c: c.rank_order)
                self._log(Strategy.UNDERPLAY, f"podliezam: {card}")
                return card
            return min(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # TAKE
    # ------------------------------------------------------------------

    def _play_take(self, playable: list[Card],
                   trick: Trick, situation: str) -> Card:
        if situation == Situation.LEADER_AGGRESSIVE:
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
                    card = min(suit_cards, key=lambda c: c.rank_order)
                    self._log(Strategy.FORCE_SPECIAL,
                              f"vytiahni horníka {suit}: {card}")
                    return card

        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]
        non_special_lead = [c for c in lead_cards if not c.is_special]

        if non_special_lead:
            card = max(non_special_lead, key=lambda c: c.rank_order)
            self._log(Strategy.FORCED_TAKE, f"najvyššia lead: {card}")
            return card

        if lead_cards:
            return max(lead_cards, key=lambda c: c.rank_order)

        return max(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # OPEN
    # ------------------------------------------------------------------

    def _play_open(self, playable: list[Card],
                   trick: Trick, situation: str,
                   hand_eval: HandEval) -> Card:
        if situation == Situation.FOLLOWER_VOID:
            return self._void_discard(playable, trick)
        if situation in (Situation.LEADER_FORCED,
                          Situation.FOLLOWER_WAIT):
            return self._open_play(playable, hand_eval, trick)
        return min(playable, key=lambda c: c.rank_order)

    def _void_discard(self, playable: list[Card],
                      trick: Trick) -> Card:
        """
        Void discard — nemám lead suit, hádžem nebezpečnú kartu.

        Priorita:
        1. Horník (najviac bodov)
        2. Trap A/K vo farbe živého horníka
        3. Hearts (najvyššia)
        4. Iné trap karty (najvyššia)
        5. Nízka karta (najnižšia)
        """
        players_after = self._get_players_after_me(trick)
        takes = self.memory.will_someone_else_take(
            trick.played_cards, players_after
        )

        # 1. Horník — vyber toho s najviac bodmi
        specials = [c for c in playable if c.is_special]
        if specials:
            def special_points(c: Card) -> int:
                suit = "leaf" if c.is_leaf_over else "acorn"
                illuminated = (
                        self.memory.illuminated_by[suit] is not None
                )
                if c.is_leaf_over:
                    return 16 if illuminated else 8
                else:
                    return 8 if illuminated else 4

            card = max(specials, key=special_points)
            self._log(Strategy.DUMP_SPECIAL, f"{takes}: {card}")
            return card

        # 2. Trap A/K vo farbe živého horníka
        danger_trap = []
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue  # horník padol, farba nie je nebezpečná
            danger_trap += [
                c for c in playable
                if c.suit == suit
                   and not c.is_special
                   and c.rank in ("ace", "king")
                   and self._is_trap(c)
            ]
        if danger_trap:
            card = max(danger_trap, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_DANGEROUS, f"trap A/K živý horník: {card}")
            return card

        # 3. Hearts (najvyššia)
        hearts = [c for c in playable if c.suit == "heart"]
        if hearts:
            card = max(hearts, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"{takes}: {card}")
            return card

        # 4. Iné trap karty (najvyššia)
        trap_playable = [
            c for c in playable
            if not c.is_special
               and c.suit != "heart"
               and self._is_trap(c)
        ]
        if trap_playable:
            card = max(trap_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_DANGEROUS, f"trap: {card}")
            return card

        # 5. Fallback — najvyššia bell, inak najvyššia non-special non-heart
        bell_cards = [c for c in playable if c.suit == "bell"]
        if bell_cards:
            card = max(bell_cards, key=lambda c: c.rank_order)
            self._log(Strategy.WAIT, f"fallback bell: {card}")
            return card

        non_special_non_heart = [
            c for c in playable
            if not c.is_special and c.suit != "heart"
        ]
        pool = non_special_non_heart if non_special_non_heart else playable
        card = max(pool, key=lambda c: c.rank_order)
        self._log(Strategy.WAIT, f"fallback high: {card}")
        return card

    def _open_play(self, playable: list[Card],
                   hand_eval: HandEval, trick: Trick) -> Card:
        is_leader = len(trick.played_cards) == 0
        protected = self._protected_suits() if is_leader else set()

        if is_leader:
            single_suit = [
                suit for suit in SUITS
                if sum(1 for c in self.player.hand.cards
                       if c.suit == suit) == 1
                   and suit != "heart"
                   and suit not in protected
            ]
            for suit in single_suit:
                suit_cards = [
                    c for c in playable
                    if c.suit == suit
                       and not c.is_special
                       and not self._is_trap(c)
                ]
                if suit_cards:
                    card = suit_cards[0]
                    self._log(Strategy.DUMP_SETUP, f"void: {card}")
                    return card

        escape_playable = [
            c for c in hand_eval.escape_cards
            if c in playable
               and not c.is_special
               and c.suit not in protected
        ]
        if escape_playable:
            card = min(escape_playable, key=lambda c: c.rank_order)
            self._log(Strategy.WAIT, f"escape: {card}")
            return card

        if is_leader:
            exhaust_cards = [
                c for c in playable
                if not c.is_special
                   and self._can_exhaust_suit(c.suit)
            ]
            if exhaust_cards:
                card = min(exhaust_cards, key=lambda c: c.rank_order)
                self._log(Strategy.WAIT, f"exhaust: {card}")
                return card

        if not is_leader:
            if not is_leader:
                lead_cards = [c for c in playable if c.suit == trick.lead_suit]
                non_special_lead = [c for c in lead_cards if not c.is_special]
                pool = non_special_lead if non_special_lead else lead_cards
                if pool:
                    if not self._trick_has_penalty(trick):
                        # Bezbodový štich — zhoď strednú kartu
                        traps = [c for c in pool if self._is_trap(c)]
                        if traps:
                            card = min(traps, key=lambda c: c.rank_order)
                            self._log(Strategy.WAIT, f"dump trap: {card}")
                            return card
                        card = max(pool, key=lambda c: c.rank_order)
                        self._log(Strategy.WAIT, f"dump high: {card}")
                        return card
                    else:
                        card = min(pool, key=lambda c: c.rank_order)
                        self._log(Strategy.WAIT, f"wait: {card}")
                        return card

        non_special = [
            c for c in playable
            if not c.is_special or self._special_is_safe_lead(c)
        ]
        pool = non_special if non_special else playable
        return min(pool, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _is_trap(self, card: Card) -> bool:
        higher_opponents = [
            c for c in self.memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        higher_own = [
            c for c in self.player.hand.cards
            if c.suit == card.suit
               and c.rank_order > card.rank_order
               and c != card
        ]
        return not higher_opponents and not higher_own

    def _special_is_safe_lead(self, card: Card) -> bool:
        remaining = self.memory.get_remaining(card.suit)
        if not remaining:
            return False
        return all(c.rank_order > card.rank_order for c in remaining)

    def _i_illuminated(self, suit: str) -> bool:
        if suit not in ("leaf", "acorn"):
            return False
        return self.memory.illuminated_by[suit] == self.player.index

    def _protected_suits(self) -> set[str]:
        protected = set()
        for suit in ("leaf", "acorn"):
            if not self._i_illuminated(suit):
                continue
            hand = self.player.hand.cards
            reserves = [
                c for c in hand
                if c.suit == suit and not c.is_special
            ]
            if len(reserves) <= 3:
                protected.add(suit)
        return protected

    def _can_exhaust_suit(self, suit: str) -> bool:
        if not self._i_illuminated(suit):
            return False
        hand = self.player.hand.cards
        reserves = [
            c for c in hand
            if c.suit == suit and not c.is_special
        ]
        if len(reserves) < 4:
            return False
        high_reserves = [
            c for c in reserves
            if c.rank in ("ace", "king")
        ]
        return len(high_reserves) == 0

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

    @staticmethod
    def _trick_has_penalty(trick: Trick) -> bool:
        return trick.total_base_points > 0 or any(
            c.is_special for _, c in trick.played_cards
        )