# game/card.py

from config import CARD_POINTS, ILLUMINATED_POINTS, RANKS, LEAF_OVER, ACORN_OVER

RANK_DISPLAY = {
    "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "under": "J", "over": "Q", "king": "K", "ace": "A"
}

SUIT_DISPLAY = {
    "heart": "♥", "bell": "●", "leaf": "♠", "acorn": "♣"
}

class Card:
    def __init__(self, suit: str, rank: str):
        self.suit = suit    # "heart", "bell", "leaf", "acorn"
        self.rank = rank    # "ace", "king", "over", "under", "ten", "nine", "eight", "seven"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    def __repr__(self) -> str:
        return f"{RANK_DISPLAY[self.rank]}{SUIT_DISPLAY[self.suit]}"

    def __str__(self) -> str:
        return f"{RANK_DISPLAY[self.rank]}{SUIT_DISPLAY[self.suit]}"

    @property
    def base_points(self) -> int:
        """Základná bodová hodnota karty (bez vysvietenia)."""
        return CARD_POINTS[self.suit].get(self.rank, 0)

    def get_points(self, leaf_illuminated: bool = False,
                   acorn_illuminated: bool = False) -> int:
        """
        Bodová hodnota karty so zohľadnením vysvietenia.
        """
        # Zelený horník
        if self.suit == "leaf" and self.rank == "over":
            if leaf_illuminated:
                return ILLUMINATED_POINTS["leaf"]["over"]   # 16b
            return CARD_POINTS["leaf"]["over"]              # 8b

        # Žaluďový horník
        if self.suit == "acorn" and self.rank == "over":
            if acorn_illuminated:
                return ILLUMINATED_POINTS["acorn"]["over"]  # 8b
            return CARD_POINTS["acorn"]["over"]             # 4b

        # Srdcová karta
        if self.suit == "heart":
            if leaf_illuminated and acorn_illuminated:
                return 2    # dvojnásobná hodnota ak sú obaja horníci vysvietení
            return 1

        return 0

    @property
    def rank_order(self) -> int:
        """Poradie karty pre porovnávanie v štichu (vyššie = silnejšia)."""
        return len(RANKS) - 1 - RANKS.index(self.rank)

    @property
    def is_penalty_card(self) -> bool:
        """Skontroluje či karta nesie trestné body (bez vysvietenia)."""
        return self.base_points > 0

    @property
    def is_leaf_over(self) -> bool:
        """Skontroluje či je karta zelený horník."""
        return self.suit == LEAF_OVER[0] and self.rank == LEAF_OVER[1]

    @property
    def is_acorn_over(self) -> bool:
        """Skontroluje či je karta žaluďový horník."""
        return self.suit == ACORN_OVER[0] and self.rank == ACORN_OVER[1]

    @property
    def is_special(self) -> bool:
        """Skontroluje či je karta špeciálna (horník)."""
        return self.is_leaf_over or self.is_acorn_over

    @property
    def image_name(self) -> str:
        """Názov PNG súboru pre túto kartu."""
        return f"{self.suit}-{self.rank}.png"