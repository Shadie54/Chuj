# game/deck.py

import random
import time
from game.card import Card
from config import SUITS, RANKS, NUM_PLAYERS


class Deck:
    def __init__(self):
        self.cards: list[Card] = []
        self._build()

    def _build(self):
        """Vytvorí kompletný balíček 32 kariet."""
        self.cards = [Card(suit, rank) for suit in SUITS for rank in RANKS]

    def shuffle(self, seed: int | None = None) -> int:
        """
        Zamieša balíček. Vráti použitý seed pre reprodukciu.
        Ak seed=None, vygeneruje sa náhodný.
        """
        if seed is None:
            seed = int(time.time() * 1000) % 1_000_000
        rng = random.Random(seed)
        rng.shuffle(self.cards)
        return seed

    def deal(self, num_players: int = NUM_PLAYERS,
             seed: int | None = None) -> tuple[list[list[Card]], int]:
        """
        Rozdá karty hráčom v sekvencii 4-4-4-4 + 4-4-4-4.
        Vráti (hands, použitý_seed).
        """
        used_seed = self.shuffle(seed)

        hands = [[] for _ in range(num_players)]
        card_index = 0
        for batch in [4, 4]:
            for player in range(num_players):
                for _ in range(batch):
                    hands[player].append(self.cards[card_index])
                    card_index += 1

        return hands, used_seed

    def reset(self):
        """Resetuje balíček do pôvodného stavu."""
        self._build()

    def __repr__(self) -> str:
        return f"Deck({len(self.cards)} cards)"