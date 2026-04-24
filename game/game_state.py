# game/game_state.py

import random
from game.player import Player
from game.round import Round
from game.game_logger import GameLogger
from config import NUM_PLAYERS, WINNING_SCORE


class GameState:
    def __init__(self, player_names: list[str], human_index: int = 0):
        """
        player_names: mená hráčov v poradí
        human_index: index ľudského hráča
        """
        self.players: list[Player] = [
            Player(name, is_human=(i == human_index), index=i)
            for i, name in enumerate(player_names)
        ]
        self.human_index = human_index
        self.round_number: int = 0
        self.current_round: Round | None = None
        self.round_history: list[dict] = []
        self.phase: str = "setup"           # setup → playing → game_over

        # Kto začína prvý štich
        self.first_player_index: int = 0

        # Chujogram — história guličiek
        self.bullet_history: list[list[int]] = []  # [kolo][player_index] = má guličku
        #Logger
        self.logger = GameLogger()
        #hráč, ktorý zobral všetky trestné karty
        self.last_sweep_player: int | None = None
    # ------------------------------------------------------------------
    # Inicializácia hry
    # ------------------------------------------------------------------

    def setup_first_player(self):
        """Náhodne vyberie hráča, ktorý začína prvý štich."""
        self.first_player_index = random.randint(0, NUM_PLAYERS - 1)

    # ------------------------------------------------------------------
    # Správa kôl
    # ------------------------------------------------------------------

    def start_new_round(self):
        """Začne nové kolo."""
        for player in self.players:
            player.reset_round()

        self.current_round = Round(
            self.players,
            self.first_player_index
        )
        self.current_round.deal()
        self.round_number += 1
        self.phase = "playing"

    def finish_round(self):
        self.current_round.score_round()
        self.last_sweep_player = self.current_round._check_sweep()  # ← pridaj
        self._record_round_history()
        self._update_chujogram()
        self._advance_first_player()
        if self._check_game_over():
            self.phase = "game_over"

    def _record_round_history(self):
        """Zaznamená výsledky kola."""
        round_data = {
            "round_number": self.round_number,
            "first_player": self.players[self.first_player_index].name,
            "leaf_illuminated": self.current_round.leaf_illuminated,
            "acorn_illuminated": self.current_round.acorn_illuminated,
            "declaration_player": (
                self.players[self.current_round.declaration_player].name
                if self.current_round.declaration_player is not None
                else None
            ),
            "declaration_type": self.current_round.declaration_type,
            "scores": {
                player.name: player.total_score
                for player in self.players
            },
            "round_points": {
                player.name: player.round_points
                for player in self.players
            }
        }
        self.round_history.append(round_data)

    def _update_chujogram(self):
        """
        Aktualizuje chujogram — pridá guličky hráčom
        s najvyšším celkovým skóre po tomto kole.
        """
        max_score = max(p.total_score for p in self.players)

        # Ak nikto nemá body — nikto nedostane guličku
        if max_score == 0:
            self.bullet_history.append([0] * NUM_PLAYERS)
            return

        round_bullets = []
        for player in self.players:
            if player.total_score == max_score:
                player.bullets += 1
                round_bullets.append(1)
            else:
                round_bullets.append(0)

        self.bullet_history.append(round_bullets)

    def _advance_first_player(self):
        """
        Nastaví ďalšieho leadera.
        Ak bol záväzok — ďalší v poradí od záväzkového hráča.
        Inak — ďalší v poradí.
        """
        self.first_player_index = (
            self.first_player_index + 1
        ) % NUM_PLAYERS

    def _check_game_over(self) -> bool:
        for player in self.players:
            print(f"[GAME_OVER CHECK] {player.name}: {player.total_score}")
        return any(
            player.total_score > WINNING_SCORE
            for player in self.players
        )

    # ------------------------------------------------------------------
    # Pomocné metódy
    # ------------------------------------------------------------------

    @property
    def loser(self) -> Player | None:
        """
        Vráti porazených hráčov (tí čo prekročili 100 bodov).
        Ak viacero — ten s najvyšším skóre.
        """
        losers = [
            p for p in self.players
            if p.total_score > WINNING_SCORE
        ]
        if not losers:
            return None
        return max(losers, key=lambda p: p.total_score)

    @property
    def current_player(self) -> Player | None:
        """Vráti hráča, ktorý je aktuálne na ťahu."""
        if self.current_round is None:
            return None
        idx = self.current_round.get_current_player_index()
        return self.players[idx]

    @property
    def is_human_turn(self) -> bool:
        """Skontroluje či je na ťahu ľudský hráč."""
        if self.current_round is None:
            return False
        phase = self.current_round.phase

        if phase == "preparation":  # ← zmenené
            return True

        return self.current_player == self.players[self.human_index]

    def get_scores(self) -> dict[str, int]:
        """Vráti aktuálne skóre všetkých hráčov."""
        return {player.name: player.total_score for player in self.players}

    def get_last_round_summary(self) -> dict | None:
        """Vráti súhrn posledného kola."""
        if self.round_history:
            return self.round_history[-1]
        return None

    def __repr__(self) -> str:
        scores = ", ".join(f"{p.name}={p.total_score}" for p in self.players)
        return (f"GameState(round={self.round_number}, "
                f"phase={self.phase}, "
                f"scores=[{scores}])")