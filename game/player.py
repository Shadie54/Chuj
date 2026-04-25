# game/player.py

from game.hand import Hand
from game.card import Card


class Player:
    def __init__(self, name: str, is_human: bool = False, index: int = 0):
        self.name = name
        self.is_human = is_human
        self.index = index
        self.hand = Hand()

        # Skóre
        self.total_score: int = 0           # celkové skóre cez všetky kolá
        self.round_points: int = 0          # body v aktuálnom kole

        # Záväzky
        self.declaration: str | None = None # "all" / "none" / None
        self.declaration_fulfilled: bool = False

        # Vysvietenie
        self.illuminated_leaf: bool = False     # vysvietil zeleného horníka
        self.illuminated_acorn: bool = False    # vysvietil žaluďového horníka

        # Štatistiky kola
        self.tricks_won: int = 0            # počet vyhraných štichov
        self.penalty_cards: list[Card] = [] # trestné karty zozbierané v kole

        # Séria bez trestných bodov
        self.no_penalty_streak: int = 0     # počet kôl bez trestných bodov

        # Chujogram
        self.bullets: int = 0              # počet guličiek v chujograme

    # ------------------------------------------------------------------
    # Správa kariet
    # ------------------------------------------------------------------

    def receive_cards(self, cards: list[Card]):
        """Dostane karty na ruku."""
        self.hand.add_cards(cards)

    def play_card(self, card: Card) -> Card:
        """Zahrá kartu z ruky."""
        self.hand.remove_card(card)
        return card

    # ------------------------------------------------------------------
    # Záväzky
    # ------------------------------------------------------------------

    def declare_all(self):
        """Hráč vyhlási záväzok — zoberiem všetky štichy."""
        self.declaration = "all"

    def declare_none(self):
        """Hráč vyhlási záväzok — nechytím ani jeden trestný bod."""
        self.declaration = "none"

    def clear_declaration(self):
        """Hráč nevyhlási žiadny záväzok."""
        self.declaration = None

    # ------------------------------------------------------------------
    # Vysvietenie
    # ------------------------------------------------------------------

    def illuminate_leaf(self):
        """Hráč vysvietí zeleného horníka."""
        self.illuminated_leaf = True

    def illuminate_acorn(self):
        """Hráč vysvietí žaluďového horníka."""
        self.illuminated_acorn = True

    # ------------------------------------------------------------------
    # štichy a body
    # ------------------------------------------------------------------

    def add_trick(self, cards: list[Card],
                  leaf_illuminated: bool, acorn_illuminated: bool):
        """
        Hráč vyhral štich — pridá karty a body.
        """
        self.tricks_won += 1
        for card in cards:
            points = card.get_points(leaf_illuminated, acorn_illuminated)
            if points > 0:
                self.round_points += points
                self.penalty_cards.append(card)

    # ------------------------------------------------------------------
    # Bodovanie na konci kola
    # ------------------------------------------------------------------

    def finalize_round(self, all_penalty_taken: bool,
                       leaf_illuminated: bool,
                       acorn_illuminated: bool,
                       other_players: list) -> int:
        points = self.round_points

        # Záväzok "all" — len success/fail, nič iné sa nepočíta
        if self.declaration == "all":
            if self.tricks_won == 8:
                from config import DECLARATION_ALL_BONUS
                points = DECLARATION_ALL_BONUS  # -20b
                self.declaration_fulfilled = True
            else:
                from config import DECLARATION_ALL_PENALTY
                points = DECLARATION_ALL_PENALTY  # +20b
                self.declaration_fulfilled = False

        # Záväzok "none" — len success/fail
        elif self.declaration == "none":
            if self.round_points == 0:
                from config import DECLARATION_NONE_BONUS
                points = DECLARATION_NONE_BONUS  # -10b
                self.declaration_fulfilled = True
            else:
                self.declaration_fulfilled = False
                from config import DECLARATION_FAIL_PENALTY
                for other in other_players:
                    other.total_score -= DECLARATION_FAIL_PENALTY

        # Sweep — len ak nie je záväzok
        elif all_penalty_taken:
            from config import SHOOT_MOON_BONUS
            points = SHOOT_MOON_BONUS  # -10b

        # Normálny priebeh — 90b hranica
        else:
            from config import HIGH_SCORE_THRESHOLD
            if self.total_score >= HIGH_SCORE_THRESHOLD:
                for card in self.penalty_cards:
                    if card.is_special:
                        points -= card.get_points(
                            leaf_illuminated, acorn_illuminated
                        )

        self.total_score += points

        # Reset na 90 ak má presne 100b
        from config import WINNING_SCORE, RESET_SCORE
        if self.total_score == WINNING_SCORE:
            self.total_score = RESET_SCORE

        # Séria — podľa skutočných trestných bodov
        if self.round_points == 0:
            self.no_penalty_streak += 1
            from config import NO_PENALTY_STREAK, NO_PENALTY_BONUS
            if self.no_penalty_streak >= NO_PENALTY_STREAK:
                self.total_score += NO_PENALTY_BONUS
                self.no_penalty_streak = 0
        else:
            self.no_penalty_streak = 0

        return points

    def reset_round(self):
        """Resetuje stav hráča pre nové kolo."""
        self.hand = Hand()
        self.round_points = 0
        self.tricks_won = 0
        self.penalty_cards = []
        self.declaration = None
        self.declaration_fulfilled = False
        self.illuminated_leaf = False
        self.illuminated_acorn = False

    def __repr__(self) -> str:
        return f"Player({self.name}, score={self.total_score})"