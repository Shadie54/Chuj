# game/ai_memory.py

from game.card import Card
from config import NUM_PLAYERS, SUITS, RANKS


class AIMemory:
    def __init__(self, player_index: int):
        self.player_index = player_index

        # Zahraté karty
        self.played_cards: set[Card] = set()

        # Pre každú farbu — ostávajúce karty
        self.remaining: dict[str, list[Card]] = {
            suit: [Card(suit, rank) for rank in RANKS]
            for suit in SUITS
        }

        # Void suits — kto nemá akú farbu
        self.void_suits: dict[int, set[str]] = {
            i: set() for i in range(NUM_PLAYERS)
        }

        # Horníci — kto môže mať horníka
        self.special_possible_holders: dict[str, set[int]] = {
            "leaf": set(range(NUM_PLAYERS)),
            "acorn": set(range(NUM_PLAYERS))
        }
        self.special_gone: dict[str, bool] = {
            "leaf": False,
            "acorn": False
        }

        # Vysvietení horníci — vieme presne kto ich má
        self.illuminated_by: dict[str, int | None] = {
            "leaf": None,
            "acorn": None
        }

    # ------------------------------------------------------------------
    # Aktualizácia po štychu
    # ------------------------------------------------------------------

    def record_trick(self, played_cards: list[tuple[int, Card]],
                     winner_index: int):
        """Zaznamená odohraný štych a aktualizuje pamäť."""
        lead_suit = played_cards[0][1].suit

        for player_idx, card in played_cards:
            # Zaznamená zahratú kartu
            self.played_cards.add(card)
            self._remove_from_remaining(card)

            # Ak hráč nezahral lead farbu → je void
            if player_idx != played_cards[0][0] and card.suit != lead_suit:
                self.void_suits[player_idx].add(lead_suit)
                # Void = nemôže mať horníka tej farby
                if lead_suit == "leaf":
                    self.special_possible_holders["leaf"].discard(player_idx)
                elif lead_suit == "acorn":
                    self.special_possible_holders["acorn"].discard(player_idx)

            # Ak bol zahraný horník → gone
            if card.is_leaf_over:
                self.special_gone["leaf"] = True
                self.special_possible_holders["leaf"] = set()
            if card.is_acorn_over:
                self.special_gone["acorn"] = True
                self.special_possible_holders["acorn"] = set()

    def record_illumination(self, player_index: int,
                             leaf: bool, acorn: bool):
        """Zaznamená vysvietenie — vieme presne kto má horníka."""
        if leaf:
            self.illuminated_by["leaf"] = player_index
            self.special_possible_holders["leaf"] = {player_index}
        if acorn:
            self.illuminated_by["acorn"] = player_index
            self.special_possible_holders["acorn"] = {player_index}

    def record_declaration(self, player_index: int,
                            declaration: str | None):
        """Zaznamená záväzok."""
        pass  # zatiaľ len placeholder

    # ------------------------------------------------------------------
    # Dotazy na pamäť
    # ------------------------------------------------------------------

    def get_remaining(self, suit: str) -> list[Card]:
        """Vráti ostávajúce karty danej farby."""
        return self.remaining[suit].copy()

    def get_remaining_count(self, suit: str) -> int:
        """Vráti počet ostávajúcich kariet danej farby."""
        return len(self.remaining[suit])

    def get_highest_remaining(self, suit: str) -> Card | None:
        if not self.remaining[suit]:
            return None
        return max(self.remaining[suit], key=lambda c: c.rank_order)

    def is_highest_remaining(self, card: Card) -> bool:
        """Skontroluje či je karta najvyššia ostávajúca v svojej farbe."""
        highest = self.get_highest_remaining(card.suit)
        return highest == card

    def is_special_gone(self, suit: str) -> bool:
        """Skontroluje či horník danej farby už bol zahraný."""
        return self.special_gone.get(suit, False)

    def who_has_special(self, suit: str) -> set[int]:
        """Vráti možných držiteľov horníka."""
        return self.special_possible_holders.get(suit, set()).copy()

    def is_safe_to_lead(self, card: Card,
                         my_hand: list[Card]) -> bool:
        """
        Je bezpečné zahrať túto kartu ako leader?
        Bezpečné = pravdepodobne nezoberiem štych.
        """
        # Horník → nikdy nie je bezpečné ako lead
        if card.is_special:
            return False

        # Červeň → nie je bezpečné
        if card.suit == "heart":
            return False

        # Najvyššia ostávajúca → zoberieme štych
        if self.is_highest_remaining(card):
            return False

        # Mám horníka tej farby a som najvyšší? → nebezpečné
        my_special = any(
            c.is_special and c.suit == card.suit
            for c in my_hand
        )
        if my_special:
            higher = [
                c for c in self.remaining[card.suit]
                if c.rank_order > card.rank_order
                and c not in my_hand
            ]
            if not higher:
                return False  # môj horník by zostal najvyšší

        return True

    def can_underplay(self, card: Card, current_best: Card) -> bool:
        """
        Môžem podliezť current_best kartou card?
        """
        if card.suit != current_best.suit:
            return True  # iná farba = nemôžem zobrať
        return card.rank_order < current_best.rank_order

    def get_dangerous_cards(self, my_hand: list[Card]) -> list[Card]:
        """
        Vráti nebezpečné karty v mojej ruke — zoradené od najnebezpečnejšej.
        Nebezpečné = ťažko sa ich zbavím.
        """
        dangerous = []

        for card in my_hand:
            score = 0

            # Horník = najnebezpečnejší
            if card.is_special:
                score += 100

            # Červeň = nebezpečná
            if card.suit == "heart":
                score += card.rank_order * 5

            # Najvyššia ostávajúca farby kde nie je void = nebezpečná
            if self.is_highest_remaining(card):
                remaining = self.get_remaining_count(card.suit)
                score += remaining * 3

            if score > 0:
                dangerous.append((card, score))

        dangerous.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in dangerous]

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _remove_from_remaining(self, card: Card):
        """Odstráni kartu z ostávajúcich."""
        self.remaining[card.suit] = [
            c for c in self.remaining[card.suit]
            if c != card
        ]

    def reset(self):
        """Resetuje pamäť pre nové kolo."""
        self.__init__(self.player_index)

    def __repr__(self) -> str:
        return (f"AIMemory(played={len(self.played_cards)}, "
                f"specials_gone={self.special_gone})")