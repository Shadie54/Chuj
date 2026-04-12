# game/deck.py

import random
from game.card import Card
from config import SUITS, RANKS, NUM_PLAYERS


class Deck:
    def __init__(self):
        self.cards: list[Card] = []
        self._build()

    def _build(self):
        """Vytvorí kompletný balíček 32 kariet."""
        self.cards = [Card(suit, rank) for suit in SUITS for rank in RANKS]

    def shuffle(self):
        """Zamieša balíček."""
        random.shuffle(self.cards)

    def deal(self, num_players: int = NUM_PLAYERS) -> list[list[Card]]:
        """
        Rozdá karty hráčom v sekvencii 4-4-4-4 + 4-4-4-4.
        Každý hráč dostane 8 kariet.
        """
        self.shuffle()

        hands = [[] for _ in range(num_players)]

        card_index = 0
        for batch in [4, 4]:  # 2 kolá rozdávania
            for player in range(num_players):  # každému hráčovi
                for _ in range(batch):  # 4 karty
                    hands[player].append(self.cards[card_index])
                    card_index += 1

        return hands

    def reset(self):
        """Resetuje balíček do pôvodného stavu."""
        self._build()

    def __repr__(self) -> str:
        return f"Deck({len(self.cards)} cards)"