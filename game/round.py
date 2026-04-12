# game/round.py

from game.card import Card
from game.deck import Deck
from game.player import Player
from game.trick import Trick
from config import NUM_PLAYERS, TRICKS_PER_ROUND


class Round:
    def __init__(self, players: list[Player], first_player_index: int):
        """
        players: zoznam všetkých hráčov
        first_player_index: index hráča, ktorý začína prvý štych
        """
        self.players = players
        self.first_player_index = first_player_index
        self.deck = Deck()
        self.tricks: list[Trick] = []
        self.current_trick: Trick | None = None
        self.current_leader_index: int = first_player_index
        self.trick_number: int = 0

        # Vysvietenie — globálny stav kola
        self.leaf_illuminated: bool = False
        self.acorn_illuminated: bool = False

        # Záväzky
        self.declaration_player: int | None = None  # kto vyhlásil záväzok
        self.declaration_type: str | None = None    # "all" / "none"

        # Fázy kola
        self.phase: str = "dealing"
        # Fázy: dealing → preparation → tricks → scoring

    # ------------------------------------------------------------------
    # FÁZA 1: Rozdávanie
    # ------------------------------------------------------------------

    def deal(self):
        """Rozdá karty hráčom."""
        hands = self.deck.deal(NUM_PLAYERS)
        for i, player in enumerate(self.players):
            player.receive_cards(hands[i])
        self.phase = "preparation"  # ← zmenené z "game_declaration"

    # ------------------------------------------------------------------
    # FÁZA 2: Príprava
    # ------------------------------------------------------------------

    def process_declaration(self, player_index: int,
                            declaration: str | None) -> bool:
        """
        Spracuje záväzok hráča.
        declaration: "all" / "none" / None (žiadny záväzok)
        Vracia True ak môžeme pokračovať na ďalšieho hráča.
        """
        player = self.players[player_index]

        if declaration == "all":
            player.declare_all()
            self.declaration_player = player_index
            self.declaration_type = "all"
            # Hráč so záväzkom začína prvý štych
            self.current_leader_index = player_index
            self.first_player_index = player_index
        elif declaration == "none":
            player.declare_none()
            self.declaration_player = player_index
            self.declaration_type = "none"
            # Hráč so záväzkom začína prvý štych
            self.current_leader_index = player_index
            self.first_player_index = player_index
        else:
            player.clear_declaration()

        return True

    def process_revealing(self, player_index: int,
                          illuminate_leaf: bool,
                          illuminate_acorn: bool):
        """
        Spracuje vysvietenie horníkov hráča.
        """
        player = self.players[player_index]

        if illuminate_leaf and player.hand.has_leaf_over():
            player.illuminate_leaf()
            self.leaf_illuminated = True

        if illuminate_acorn and player.hand.has_acorn_over():
            player.illuminate_acorn()
            self.acorn_illuminated = True

    def finish_preparation(self):
        """Ukončí prípravu a začne štychy."""
        self.phase = "tricks"
        self.start_trick()

    # ------------------------------------------------------------------
    # FÁZA 3: Štychy
    # ------------------------------------------------------------------

    def start_trick(self):
        """Začne nový štych."""
        self.current_trick = Trick(
            self.players,
            self.current_leader_index
        )

    def play_card(self, player_index: int, card: Card) -> bool:
        player = self.players[player_index]
        playable = player.hand.get_playable_cards(
            self.current_trick.lead_suit,
            self.trick_number  # ← pridané
        )
        if card not in playable:
            return False
        player.play_card(card)
        self.current_trick.play_card(player_index, card)
        return True

    def finish_trick(self) -> int:
        """
        Uzavrie štych, určí víťaza, pripočíta body.
        Vracia index víťaza štychu.
        """
        winner_index = self.current_trick.get_winner_index()
        cards = self.current_trick.get_all_cards()

        # Víťaz dostane karty a body
        self.players[winner_index].add_trick(
            cards,
            self.leaf_illuminated,
            self.acorn_illuminated
        )

        self.tricks.append(self.current_trick)
        self.current_trick = None
        self.current_leader_index = winner_index
        self.trick_number += 1

        if self.trick_number >= TRICKS_PER_ROUND:
            self.phase = "scoring"

        return winner_index

    # ------------------------------------------------------------------
    # FÁZA 4: Bodovanie
    # ------------------------------------------------------------------

    def score_round(self):
        """
        Uzavrie kolo a aktualizuje skóre všetkých hráčov.
        """
        sweep_player = self._check_sweep()

        for i, player in enumerate(self.players):
            other_players = [p for p in self.players if p != player]
            all_penalty = (sweep_player == i)
            player.finalize_round(
                all_penalty_taken=all_penalty,
                leaf_illuminated=self.leaf_illuminated,
                acorn_illuminated=self.acorn_illuminated,
                other_players=other_players
            )

        self.phase = "done"

    def _check_sweep(self) -> int | None:
        """
        Skontroluje či jeden hráč zobral všetky trestné karty.
        Vracia index hráča alebo None.
        """
        # Celkový počet trestných kariet
        total_penalty = sum(
            len(p.penalty_cards) for p in self.players
        )

        if total_penalty == 0:
            return None

        # Skontroluj či má jeden hráč všetky
        for i, player in enumerate(self.players):
            if len(player.penalty_cards) == total_penalty:
                return i

        return None

    # ------------------------------------------------------------------
    # Pomocné metódy
    # ------------------------------------------------------------------

    def get_current_player_index(self) -> int:
        """Vráti index hráča, ktorý je aktuálne na ťahu."""
        if self.current_trick is None:
            return self.current_leader_index
        played_count = len(self.current_trick.played_cards)
        # Poradie proti smeru hodinových ručičiek
        return (self.current_leader_index + played_count) % NUM_PLAYERS

    @staticmethod
    def get_next_player_index(current_index: int) -> int:
        """Vráti index ďalšieho hráča (proti smeru hodinových ručičiek)."""
        return (current_index + 1) % NUM_PLAYERS

    def __repr__(self) -> str:
        return (f"Round(phase={self.phase}, "
                f"trick={self.trick_number}/{TRICKS_PER_ROUND}, "
                f"leaf={self.leaf_illuminated}, "
                f"acorn={self.acorn_illuminated})")