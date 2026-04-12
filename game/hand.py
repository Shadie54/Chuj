# game/hand.py

from game.card import Card

class Hand:
    def __init__(self):
        self.cards: list[Card] = []

    def add_card(self, card: Card):
        """Pridá kartu do ruky."""
        self.cards.append(card)

    def add_cards(self, cards: list[Card]):
        """Pridá viacero kariet do ruky."""
        self.cards.extend(cards)

    def remove_card(self, card: Card):
        """Odstráni kartu z ruky (po zahraní)."""
        self.cards.remove(card)

    def has_suit(self, suit: str) -> bool:
        """Skontroluje či hráč má kartu danej farby."""
        return any(card.suit == suit for card in self.cards)

    def get_cards_of_suit(self, suit: str) -> list[Card]:
        """Vráti všetky karty danej farby."""
        return [card for card in self.cards if card.suit == suit]

    def get_playable_cards(self, lead_suit: str | None,
                           trick_number: int = 0) -> list[Card]:
        """
        Vráti karty ktoré môže hráč zahrať.
        - Ak je leader: môže zahrať čokoľvek
          (okrem srdcí v 1. štychu)
        - Ak má farbu: môže zahrať akúkoľvek kartu tej farby
          (aj nižšiu — podliezanie)
        - Ak nemá farbu: môže zahrať čokoľvek
        """
        # Prvý štych — žiadna červeň
        if trick_number == 0:
            non_heart = [c for c in self.cards if c.suit != "heart"]
            available = non_heart if non_heart else self.cards
        else:
            available = self.cards.copy()

        # Leader — môže zahrať čokoľvek z available
        if lead_suit is None:
            return available

        # Follower — musí priznať farbu ak má
        # ALE môže zahrať akúkoľvek kartu tej farby (podliezanie)
        same_suit = [c for c in available if c.suit == lead_suit]
        if same_suit:
            return same_suit  # ← všetky karty farby, nie len vyššie

        # Nemá farbu — môže zahrať čokoľvek
        return available

    def has_penalty_cards(self) -> bool:
        """Skontroluje či hráč má nejaké trestné karty."""
        return any(card.is_penalty_card for card in self.cards)

    def has_special_card(self) -> bool:
        """Skontroluje či hráč má špeciálnu kartu (horník)."""
        return any(card.is_special for card in self.cards)

    def has_leaf_over(self) -> bool:
        """Skontroluje či hráč má zeleného horníka."""
        return any(card.is_leaf_over for card in self.cards)

    def has_acorn_over(self) -> bool:
        """Skontroluje či hráč má žaluďového horníka."""
        return any(card.is_acorn_over for card in self.cards)

    def sort_hand(self):
        """Zoradí karty zostupne podľa farby a hodnoty."""
        from config import SUITS as SUIT_ORDER
        self.cards.sort(
            key=lambda c: (
                SUIT_ORDER.index(c.suit),
                -c.rank_order
            )
        )

    @property
    def total_base_points(self) -> int:
        """Celkové základné body kariet v ruke."""
        return sum(card.base_points for card in self.cards)

    def total_points(self, leaf_illuminated: bool = False,
                     acorn_illuminated: bool = False) -> int:
        """Celkové body kariet so zohľadnením vysvietenia."""
        return sum(
            card.get_points(leaf_illuminated, acorn_illuminated)
            for card in self.cards
        )

    @property
    def is_empty(self) -> bool:
        """Skontroluje či je ruka prázdna."""
        return len(self.cards) == 0

    def __len__(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"Hand({[str(c) for c in self.cards]})"