# game/ai_play_none.py
from game.ai_memory import AIMemory
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

    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def decide(self, playable: list[Card],
               trick: Trick,
               hand_eval: HandEval,
               declaration_player: int | None = None) -> Card:
        is_leader = len(trick.played_cards) == 0

        if is_leader:
            return self._lead(playable, declaration_player)

        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]

        if not lead_cards:
            return self._void(playable)

        return self._follow(lead_cards, trick, declaration_player)

    # ------------------------------------------------------------------
    # Leader — zahraj najvyššiu kartu (pustíme niekoho na štich)
    # ------------------------------------------------------------------

    def _lead(self, playable: list[Card],
              declaration_player: int | None) -> Card:
        if declaration_player is not None:
            decl_void = self.memory.void_suits.get(declaration_player, set())
            non_void_playable = [
                c for c in playable
                if c.suit not in decl_void
            ]
            pool = non_void_playable if non_void_playable else playable
        else:
            pool = playable
        card = min(pool, key=lambda c: c.rank_order)
        self._log(Strategy.DECLARATION_NONE, f"lead najnižšia: {card}")
        return card

    # ------------------------------------------------------------------
    # Follower — podliezaj
    # ------------------------------------------------------------------

    def _follow(self, lead_cards: list[Card],
                trick: Trick,
                declaration_player: int | None) -> Card:
        # Posledný a musím brať — hoď najvyššiu
        is_last = len(trick.played_cards) == NUM_PLAYERS - 1
        if is_last and self.player.index != declaration_player:
            current_best = self._get_current_best(trick)
            can_underplay = current_best and any(
                c.rank_order < current_best.rank_order for c in lead_cards
            )
            if not can_underplay:
                card = max(lead_cards, key=lambda c: c.rank_order)
                self._log(Strategy.DECLARATION_NONE, f"posledný musím brať: {card}")
                return card
        # Bol vyhlasovateľ prebytý?
        decl_beaten = False
        if declaration_player is not None:
            for idx, card in trick.played_cards:
                if idx == declaration_player:
                    current_best = self._get_current_best(trick)
                    if current_best and current_best != card:
                        decl_beaten = True
                    break

        if decl_beaten:
            # Niekto prebil — hoď najvyššiu
            card = max(lead_cards, key=lambda c: c.rank_order)
            self._log(Strategy.DECLARATION_NONE, f"prebytý: {card}")
            return card

        # Nikto neprebil — podliezaj
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