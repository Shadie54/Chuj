# game/ai_memory.py

from dataclasses import dataclass
from game.card import Card
from config import NUM_PLAYERS, SUITS, RANKS


# ------------------------------------------------------------------
# SuitProfile — hodnotenie jednej farby v ruke
# ------------------------------------------------------------------

@dataclass
class SuitProfile:
    suit: str
    count: int                        # počet kariet v tejto farbe
    is_void: bool                     # nemám túto farbu
    my_cards: list[Card]              # moje karty v tejto farbe
    trap_cards: list[Card]            # karty bez coverage (zoberú štich)
    escape_cards: list[Card]          # karty s coverage (môžem podliezť)
    coverage: list[Card]              # vyššie karty vonku (+ current trick)
    has_special: bool                 # mám horníka tejto farby
    special_reserves: int             # počet kariet okrem horníka (rezervy)


# ------------------------------------------------------------------
# AIMemory
# ------------------------------------------------------------------

class AIMemory:
    def __init__(self, player_index: int):
        self.player_index = player_index

        # Zahraté karty
        self.played_cards: set[Card] = set()

        # Pre každú farbu — ostávajúce karty u súperov
        # (po init_with_hand sem nepatria moje karty)
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

        # Počet štichov, ktoré každý hráč zobral v tomto kole
        self.tricks_taken: dict[int, int] = {
            i: 0 for i in range(NUM_PLAYERS)
        }

        # Discardy — čo kto zahodil keď bol void
        self.discards: dict[int, list[Card]] = {
            i: [] for i in range(NUM_PLAYERS)
        }

    # ------------------------------------------------------------------
    # Inicializácia s rukou
    # ------------------------------------------------------------------

    def init_with_hand(self, my_hand: list[Card]):
        """
        Zavolať po rozdaní kariet.
        Odstráni moje karty z remaining — viem presne čo mám.
        Remaining = karty u súperov (neznáme).
        """
        for card in my_hand:
            self._remove_from_remaining(card)

    # ------------------------------------------------------------------
    # Aktualizácia po štichu
    # ------------------------------------------------------------------

    def record_trick(self, played_cards: list[tuple[int, Card]],
                     winner_index: int):
        """Zaznamená odohraný štich a aktualizuje pamäť."""
        lead_suit = played_cards[0][1].suit

        for player_idx, card in played_cards:
            self.played_cards.add(card)
            self._remove_from_remaining(card)

            # Void detekcia — len pre followera (nie leadera)
            if player_idx != played_cards[0][0] and card.suit != lead_suit:
                self.void_suits[player_idx].add(lead_suit)
                self.discards[player_idx].append(card)
                if lead_suit == "leaf":
                    self.special_possible_holders["leaf"].discard(player_idx)
                elif lead_suit == "acorn":
                    self.special_possible_holders["acorn"].discard(player_idx)

            # Horník zahraný → gone
            if card.is_leaf_over:
                self.special_gone["leaf"] = True
                self.special_possible_holders["leaf"] = set()
            if card.is_acorn_over:
                self.special_gone["acorn"] = True
                self.special_possible_holders["acorn"] = set()

        self.tricks_taken[winner_index] += 1

    def record_illumination(self, player_index: int,
                             leaf: bool, acorn: bool):
        """Zaznamená vysvietenie — vieme presne kto má horníka."""
        if leaf:
            self.illuminated_by["leaf"] = player_index
            self.special_possible_holders["leaf"] = {player_index}
        if acorn:
            self.illuminated_by["acorn"] = player_index
            self.special_possible_holders["acorn"] = {player_index}

    # ------------------------------------------------------------------
    # SuitProfile — hlavná metóda hodnotenia farby
    # ------------------------------------------------------------------

    def build_suit_profile(self, suit: str,
                            my_hand: list[Card],
                            current_trick_cards: list[Card]) -> SuitProfile:
        """
        Vybuduje profil farby pre aktuálnu situáciu.

        Coverage = remaining[suit] + karty tejto farby v aktuálnom štichu.
        Karty v štichu sú dočasne preč ale stále sú coverage —
        kým štich neskončí, sú to reálne karty vonku.
        """
        my_cards = [c for c in my_hand if c.suit == suit]

        if not my_cards:
            return SuitProfile(
                suit=suit,
                count=0,
                is_void=True,
                my_cards=[],
                trap_cards=[],
                escape_cards=[],
                coverage=[],
                has_special=False,
                special_reserves=0
            )

        # Coverage = ostávajúce u súperov + karty v aktuálnom štichu
        trick_suit_cards = [c for c in current_trick_cards if c.suit == suit]
        coverage = self.remaining[suit] + trick_suit_cards

        trap_cards = []
        escape_cards = []

        for card in my_cards:
            higher = [c for c in coverage if c.rank_order > card.rank_order]
            if higher:
                escape_cards.append(card)   # niekto vyšší vonku → môžem podliezť
            else:
                trap_cards.append(card)     # nikto vyšší → zoberiem štich

        has_special = any(c.is_special for c in my_cards)
        special_reserves = len(my_cards) - (1 if has_special else 0)

        return SuitProfile(
            suit=suit,
            count=len(my_cards),
            is_void=False,
            my_cards=my_cards,
            trap_cards=trap_cards,
            escape_cards=escape_cards,
            coverage=coverage,
            has_special=has_special,
            special_reserves=special_reserves
        )

    def build_all_profiles(self, my_hand: list[Card],
                            current_trick_cards: list[Card]
                            ) -> dict[str, SuitProfile]:
        """Vybuduje profily pre všetky farby."""
        return {
            suit: self.build_suit_profile(suit, my_hand, current_trick_cards)
            for suit in SUITS
        }

    # ------------------------------------------------------------------
    # Dotazy — ostávajúce karty
    # ------------------------------------------------------------------

    def get_remaining(self, suit: str) -> list[Card]:
        """Vráti ostávajúce karty danej farby u súperov."""
        return self.remaining[suit].copy()

    def get_remaining_count(self, suit: str) -> int:
        return len(self.remaining[suit])

    def get_highest_remaining(self, suit: str) -> Card | None:
        if not self.remaining[suit]:
            return None
        return max(self.remaining[suit], key=lambda c: c.rank_order)

    def is_highest_remaining(self, card: Card) -> bool:
        highest = self.get_highest_remaining(card.suit)
        return highest is not None and highest == card

    def is_special_gone(self, suit: str) -> bool:
        return self.special_gone.get(suit, False)

    def who_has_special(self, suit: str) -> set[int]:
        return self.special_possible_holders.get(suit, set()).copy()

    # ------------------------------------------------------------------
    # Dotazy — situácia a poradie
    # ------------------------------------------------------------------

    def can_anyone_beat(self, card: Card,
                         players_after_me: list[int],
                         current_trick_cards: list[Card]) -> bool:
        """
        Môže niekto z hráčov po mne prebiť túto kartu?

        Coverage zahŕňa aj karty v aktuálnom štichu.
        Hráč môže prebiť ak:
        1. Nie je void na danú farbu
        2. Existuje vyššia karta v coverage
        """
        trick_suit_cards = [c for c in current_trick_cards
                            if c.suit == card.suit]
        coverage = self.remaining[card.suit] + trick_suit_cards
        higher = [c for c in coverage if c.rank_order > card.rank_order]

        if not higher:
            return False

        for player_idx in players_after_me:
            if card.suit not in self.void_suits[player_idx]:
                return True

        return False

    def will_someone_else_take(self,
                               current_trick_played: list[tuple[int, Card]],
                               players_after_me: list[int]) -> str:
        if not current_trick_played:
            return "maybe"

        lead_suit = current_trick_played[0][1].suit

        best_idx = current_trick_played[0][0]
        best_card = current_trick_played[0][1]
        for idx, card in current_trick_played[1:]:
            if card.suit == lead_suit and card.rank_order > best_card.rank_order:
                best_card = card
                best_idx = idx

        if best_idx == self.player_index:
            return "maybe"

        higher_remaining = [
            c for c in self.remaining[lead_suit]
            if c.rank_order > best_card.rank_order
        ]
        if not higher_remaining:
            return "yes"

        non_void_after = [
            p for p in players_after_me
            if lead_suit not in self.void_suits[p]
        ]
        remaining_count = self.get_remaining_count(lead_suit)
        void_prob = self._estimate_void_probability(remaining_count)
        if non_void_after and void_prob <= 0.5:
            return "yes"

        return "maybe"

    @staticmethod
    def _estimate_void_probability(remaining_count: int) -> float:
        """
        Odhadne pravdepodobnosť, že náhodný hráč je void na danú farbu.

        Čím menej kariet ostáva, tým väčšia šanca, že niekto je void.
        """
        if remaining_count == 0:
            return 1.0
        if remaining_count >= 6:
            return 0.1
        if remaining_count >= 4:
            return 0.25
        if remaining_count >= 2:
            return 0.5
        return 0.8

    def active_players_in_suit(self, suit: str) -> int:
        """Počet hráčov ktorí ešte majú karty danej farby."""
        return sum(
            1 for i in range(NUM_PLAYERS)
            if suit not in self.void_suits[i]
        )

    # ------------------------------------------------------------------
    # Post-win risk
    # ------------------------------------------------------------------

    def worst_possible_discard(self, lead_suit: str,
                                players_after_me: list[int]) -> int:
        """
        Ak zoberiem štich, čo najhoršie mi môže padnúť od hráčov po mne?

        Pre každého hráča po mne:
        - Ak je void na lead_suit → môže hodiť čokoľvek nebezpečné
        - Ak nevieme → škálujeme podľa void_probability

        Vracia maximálne možné body, ktoré môžu padnúť.
        """
        worst_points = 0
        remaining_count = self.get_remaining_count(lead_suit)
        void_prob = self._estimate_void_probability(remaining_count)

        for player_idx in players_after_me:
            is_void = lead_suit in self.void_suits[player_idx]

            if is_void:
                max_discard = self._max_discard_points(lead_suit)
                worst_points = max(worst_points, max_discard)
            else:
                max_discard = self._max_discard_points(lead_suit)
                expected = int(max_discard * void_prob)
                worst_points = max(worst_points, expected)

        return worst_points

    def _max_discard_points(self, exclude_suit: str) -> int:
        """
        Najväčší počet bodov, ktoré môžu padnúť, ako discard
        (karty inej farby, ako lead).
        """
        max_pts = 0
        for suit in SUITS:
            if suit == exclude_suit:
                continue
            for card in self.remaining[suit]:
                if card.is_leaf_over:
                    max_pts = max(max_pts, 8)
                elif card.is_acorn_over:
                    max_pts = max(max_pts, 4)
                elif suit == "heart":
                    max_pts = max(max_pts, 1)
        return max_pts

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _remove_from_remaining(self, card: Card):
        self.remaining[card.suit] = [
            c for c in self.remaining[card.suit]
            if c != card
        ]

    def reset(self):
        self.__init__(self.player_index)

    def __repr__(self) -> str:
        return (f"AIMemory(played={len(self.played_cards)}, "
                f"tricks_taken={self.tricks_taken}, "
                f"specials_gone={self.special_gone})")