# game/ai_play_all_defender.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory


class AllDefender:
    """
    Logika pre hráčov, ktorí NIE SÚ deklarant počas záväzku
    'Beriem všetko' (koncept: claude/14_HORNIK_TIEBREAK_HAND_EVAL_LOG.md
    sekcia "Beriem všetko").

    Cieľ: prebiť deklaranta aspoň v jednom štichu — "ostatní 0b" platí
    bez ohľadu na výsledok (00_GAME_RULES.md), takže zobratie štichu nás
    nič nestojí, a zároveň zmení deklarantovi +20b (zlyhanie) namiesto
    -20b (úspech). Deklarant vedie každý štich, kým vyhráva — ja som
    teda prakticky vždy follower.

    Pravidlo (po dohode, žiadny rozdiel medzi "najvyššia dostačujúca" a
    "najnižšia dostačujúca" na prebitie — kolo sa vyhodnotí ako zlyhané
    hneď pri prvom prebití, round.check_declaration_failed(), takže
    "neskôr v tomto kole" už nenastane):

      1. Ak deklarant v tomto štichu ešte NIE JE prebytý (current_best
         je stále jeho karta) a mám vo vedenej farbe vyššiu kartu →
         zahrám najnižšiu dostačujúcu (prebije rovnako dobre).
      2. Ak už bol v tomto štichu prebytý (niekto iný ako deklarant už
         drží current_best) → už nie je dôvod sa snažiť, hádžem
         najnižšiu — zbytočné míňať vysoké karty na niečo, na čom už
         nezáleží.
      3. Ak prebiť nemôžem (nemám vyššiu, alebo som void) → najnižšia
         hrateľná karta — šetrím vysoké karty na budúce štichy.
      4. Vedenie — teoretický prípad (deklarant vedie prakticky vždy) →
         default najnižšia.
    """

    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def decide(self, playable: list[Card], trick: Trick,
               declaration_player: int) -> Card:
        if len(trick.played_cards) == 0:
            card = min(playable, key=lambda c: c.rank_order)
            self._log("D3-DECLARATION_ALL_DEFEND",
                       f"lead (neočakávané): {card}")
            return card

        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]

        if not lead_cards:
            card = min(playable, key=lambda c: c.rank_order)
            self._log("D3-DECLARATION_ALL_DEFEND", f"void najnižšia: {card}")
            return card

        if not self._declarant_already_beaten(trick, declaration_player):
            current_best = self._get_current_best(trick)
            beating = [
                c for c in lead_cards
                if current_best is None
                   or c.rank_order > current_best.rank_order
            ]
            if beating:
                card = min(beating, key=lambda c: c.rank_order)
                self._log("D3-DECLARATION_ALL_DEFEND", f"chytám: {card}")
                return card

        card = min(lead_cards, key=lambda c: c.rank_order)
        self._log("D3-DECLARATION_ALL_DEFEND", f"najnižšia: {card}")
        return card

    @staticmethod
    def _declarant_already_beaten(trick: Trick,
                                   declaration_player: int) -> bool:
        if not trick.played_cards:
            return False
        winner_idx = trick.get_winner_index()
        return winner_idx != declaration_player

    @staticmethod
    def _get_current_best(trick: Trick) -> Card | None:
        if not trick.played_cards:
            return None
        winner_idx = trick.get_winner_index()
        for idx, card in trick.played_cards:
            if idx == winner_idx:
                return card
        return None
