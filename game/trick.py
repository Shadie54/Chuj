# game/trick.py

from game.card import Card
from game.player import Player

class Trick:
    def __init__(self, players: list[Player], leader_index: int):
        """
        players: zoznam všetkých hráčov
        leader_index: index hráča, ktorý začína štich
        V Chuji nie sú tromfy.
        """
        self.players = players
        self.leader_index = leader_index
        self.played_cards: list[tuple[int, Card]] = []  # (player_index, card)

    @property
    def lead_suit(self) -> str | None:
        """Farba prvej zahranej karty v štichu."""
        if self.played_cards:
            return self.played_cards[0][1].suit
        return None

    @property
    def is_complete(self) -> bool:
        """štich je kompletný ak zahrali všetci hráči."""
        return len(self.played_cards) == len(self.players)

    def play_card(self, player_index: int, card: Card):
        """Zaznamená zahratú kartu hráča."""
        self.played_cards.append((player_index, card))

    def get_winner_index(self) -> int:
        """
        Určí víťaza štichu podľa pravidiel:
        - Najvyššia karta v hranej farbe vyhráva
        - Karty inej farby, ako lead_suit nemôžu vyhrať
        - Nie sú tromfy
        """
        best_player_index = self.played_cards[0][0]
        best_card = self.played_cards[0][1]

        for player_index, card in self.played_cards[1:]:
            if self._beats(card, best_card):
                best_card = card
                best_player_index = player_index

        return best_player_index

    def _beats(self, challenger: Card, current_best: Card) -> bool:
        """
        Skontroluje či challenger porazí current_best.
        Len karty rovnakej farby, ako lead_suit môžu vyhrať.
        """
        # Challenger musí byť v lead farbe
        if challenger.suit != self.lead_suit:
            return False

        # Current best nie je v lead farbe — challenger vyhráva
        if current_best.suit != self.lead_suit:
            return True

        # Obaja sú v lead farbe — vyššia rank_order vyhráva
        return challenger.rank_order > current_best.rank_order

    @property
    def total_base_points(self) -> int:
        """Celkové základné body kariet v štichu."""
        return sum(card.base_points for _, card in self.played_cards)

    def total_points(self, leaf_illuminated: bool = False,
                     acorn_illuminated: bool = False) -> int:
        """Celkové body kariet so zohľadnením vysvietenia."""
        return sum(
            card.get_points(leaf_illuminated, acorn_illuminated)
            for _, card in self.played_cards
        )

    def get_all_cards(self) -> list[Card]:
        """Vráti všetky karty v štichu."""
        return [card for _, card in self.played_cards]

    def get_played_card(self, player_index: int) -> Card | None:
        """Vráti kartu ktorú zahral daný hráč."""
        for idx, card in self.played_cards:
            if idx == player_index:
                return card
        return None

    def __repr__(self) -> str:
        cards_str = ", ".join(
            f"{self.players[i].name}: {card}"
            for i, card in self.played_cards
        )
        return f"Trick(lead={self.lead_suit}, cards=[{cards_str}])"