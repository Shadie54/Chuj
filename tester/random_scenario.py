# tester/random_scenario.py

import random
import time
from game.card import Card
from tester.scenario import Scenario
from config import NUM_PLAYERS, CARDS_PER_PLAYER, SUITS, RANKS


def random_scenario(seed: int | None = None) -> Scenario:
    if seed is None:
        seed = int(time.time() * 1000) % 1_000_000

    rng = random.Random(seed)

    deck = [Card(suit, rank) for suit in SUITS for rank in RANKS]
    rng.shuffle(deck)

    # Rozdanie 4-4-4-4 + 4-4-4-4 (kompatibilné s game/deck.py)
    hands = {i: [] for i in range(NUM_PLAYERS)}
    card_index = 0
    for batch in [4, 4]:
        for player in range(NUM_PLAYERS):
            for _ in range(batch):
                hands[player].append(deck[card_index])
                card_index += 1

    first_player = rng.randint(0, NUM_PLAYERS - 1)

    return Scenario(
        name=f"random_seed_{seed}",
        description=f"Náhodné rozdanie (seed={seed})",
        hands=hands,
        first_player_index=first_player,
        illuminations={"leaf": None, "acorn": None},
        declarations={i: None for i in range(NUM_PLAYERS)},
        history=[],
        start_after_trick=None,
    )