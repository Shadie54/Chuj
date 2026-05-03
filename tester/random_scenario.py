# tester/random_scenario.py

import random
import time
from game.card import Card
from tester.scenario import Scenario
from config import NUM_PLAYERS, CARDS_PER_PLAYER, SUITS, RANKS


def random_scenario(seed: int | None = None) -> Scenario:
    """
    Vygeneruje náhodný scenár — rozdá 32 kariet medzi 4 hráčov.

    Žiadna história, žiadne iluminácie, žiadne záväzky.
    First player je tiež random.

    Ak seed=None, použije sa časový seed (každé volanie iné).
    """
    if seed is None:
        seed = int(time.time() * 1000) % 1_000_000

    rng = random.Random(seed)

    # Vytvor balík 32 kariet
    deck = [Card(suit, rank) for suit in SUITS for rank in RANKS]
    rng.shuffle(deck)

    # Rozdaj po 8 kariet každému hráčovi
    hands = {}
    for i in range(NUM_PLAYERS):
        start = i * CARDS_PER_PLAYER
        end = start + CARDS_PER_PLAYER
        hands[i] = deck[start:end]

    # Random first player
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