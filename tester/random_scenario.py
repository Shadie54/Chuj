# tester/random_scenario.py

import random
import time
from pathlib import Path
from config import NUM_PLAYERS, SUITS, RANKS
from game.card import Card
from tester.scenario import Scenario

LAST_SEED_FILE = Path.home() / "Documents" / "Chuj" / "last_seed.txt"

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
        illuminations={},  # ← prázdny dict = AI rozhodnú sami
        declarations={i: None for i in range(NUM_PLAYERS)},
        history=[],
        start_after_trick=None,
    )
def save_last_seed(seed: int):
    LAST_SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEED_FILE.write_text(str(seed))

def load_last_seed() -> int | None:
    try:
        return int(LAST_SEED_FILE.read_text().strip())
    except Exception:
        return None