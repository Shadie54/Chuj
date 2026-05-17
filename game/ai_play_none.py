# game/ai_play_none.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_hand_eval import HandEval
from game.ai_strategies_const import Strategy
from config import NUM_PLAYERS


class NonePlayer:
    """
    Logika pre záväzok 'Nechytím nič'.
    Cieľ: neprichnatiť ani jeden štich počas celého kola.
    Body za trestné karty sa nepočítajú — len výsledok záväzku.
    """

    def __init__(self, player: Player, logger=None):
        self.player = player
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def decide(self, playable: list[Card],
               trick: Trick,
               hand_eval: HandEval) -> Card:
        is_leader = len(trick.played_cards) == 0

        if is_leader:
            return self._lead(playable)

        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]

        if not lead_cards:
            return self._void(playable)

        return self._follow(lead_cards, trick)

    # ------------------------------------------------------------------
    # Leader — zahraj najvyššiu kartu (pustíme niekoho na štich)
    # ------------------------------------------------------------------

    def _lead(self, playable: list[Card]) -> Card:
        card = min(playable, key=lambda c: c.rank_order)
        self._log(Strategy.DECLARATION_NONE, f"lead najnižšia: {card}")
        return card

    # ------------------------------------------------------------------
    # Follower — podliezaj
    # ------------------------------------------------------------------

    def _follow(self, lead_cards: list[Card], trick: Trick) -> Card:
        current_best = self._get_current_best(trick)

        if current_best:
            underplay = [
                c for c in lead_cards
                if c.rank_order < current_best.rank_order
            ]
            if underplay:
                card = max(underplay, key=lambda c: c.rank_order)
                self._log(Strategy.DECLARATION_NONE, f"podliezam: {card}")
                return card

        # Nemôžem podliezť — najnižšia možná
        card = min(lead_cards, key=lambda c: c.rank_order)
        self._log(Strategy.DECLARATION_NONE, f"donútený najnižšia: {card}")
        return card

    # ------------------------------------------------------------------
    # Follower void — zahraj najnižšiu kartu
    # ------------------------------------------------------------------

    def _void(self, playable: list[Card]) -> Card:
        card = max(playable, key=lambda c: c.rank_order)
        self._log(Strategy.DECLARATION_NONE, f"void najvyššia: {card}")
        return card

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_best(trick: Trick) -> Card | None:
        if not trick.played_cards:
            return None
        winner_idx = trick.get_winner_index()
        for idx, card in trick.played_cards:
            if idx == winner_idx:
                return card
        return None