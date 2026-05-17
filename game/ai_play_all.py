# game/ai_play_all.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval
from game.ai_strategies_const import Strategy
from config import SUITS


class AllPlayer:
    """
    Logika pre záväzok 'Beriem všetko'.
    Cieľ: zobrať všetkých 8 štichov — vždy som leader.
    Ak niekto prebije, hra končí ako fail.
    """

    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def decide(self, playable: list[Card],
               hand_eval: HandEval) -> Card:
        # 1. Trap karta — 100% zoberiem štich
        trap_playable = [
            c for c in playable
            if c in hand_eval.trap_cards
        ]
        if trap_playable:
            # Preferuj farbu kde mám najviac trapov — vyčerpaj farbu
            best = self._best_trap(trap_playable)
            self._log(Strategy.DECLARATION_ALL, f"trap istý: {best}")
            return best

        # 2. Žiadna trap — kritická situácia
        # Zahraj najvyššiu escape kartu (dáme súperom najmenšiu šancu prebiť)
        escape_playable = [
            c for c in playable
            if c in hand_eval.escape_cards
        ]
        if escape_playable:
            card = max(escape_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DECLARATION_ALL, f"escape risk: {card}")
            return card

        # 3. Fallback — najvyššia karta
        card = max(playable, key=lambda c: c.rank_order)
        self._log(Strategy.DECLARATION_ALL, f"fallback najvyššia: {card}")
        return card

    def _best_trap(self, trap_cards: list[Card]) -> Card:
        """
        Vyber trap kartu z farby kde mám najviac trapov.
        Stratégia: vyčerpaj farbu po farbe.
        """
        suit_counts: dict[str, list[Card]] = {}
        for c in trap_cards:
            suit_counts.setdefault(c.suit, []).append(c)

        # Farba s najviac trapmi — vyčerpaj ju
        best_suit = max(suit_counts, key=lambda s: len(suit_counts[s]))
        candidates = suit_counts[best_suit]
        return max(candidates, key=lambda c: c.rank_order)