# game/game_logger.py

import os
from datetime import datetime
from pathlib import Path
from game.card import Card


class GameLogger:
    def __init__(self, log_dir: str = None):
        if log_dir is None:
            documents = Path.home() / "Documents" / "Chuj" / "logs"
            self.log_dir = str(documents)
        else:
            self.log_dir = log_dir

        self.entries: list[str] = []
        self.round_number = 0

        os.makedirs(self.log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def new_round(self, round_number: int, first_player: str,
                  hands: dict[str, list[Card]]):
        """Zaznamená začiatok kola."""
        self.round_number = round_number
        self.entries.append(f"\n{'='*60}")
        self.entries.append(f"KOLO {round_number}")
        self.entries.append(f"{'='*60}")
        self.entries.append(f"Začína: {first_player}")
        self.entries.append("")
        for name, cards in hands.items():
            self.entries.append(f"Ruka [{name}]: {self._cards_str(cards)}")
        self.entries.append("")

    def log_declaration(self, player: str, declaration: str | None):
        """Zaznamená záväzok hráča."""
        if declaration == "all":
            self.entries.append(f"  Záväzok [{player}]: VŠETKY ŠTYCHY (-20b)")
        elif declaration == "none":
            self.entries.append(f"  Záväzok [{player}]: ŽIADNY TRESTNÝ BOD (-10b)")
        else:
            self.entries.append(f"  Záväzok [{player}]: žiadny")

    def log_illumination(self, player: str,
                         leaf: bool, acorn: bool):
        """Zaznamená vysvietenie horníkov."""
        if leaf:
            self.entries.append(
                f"  Vysvietenie [{player}]: zelený horník (16b)"
            )
        if acorn:
            self.entries.append(
                f"  Vysvietenie [{player}]: žaluďový horník (8b)"
            )

    def log_trick(self, trick_number: int,
                  played: list[tuple[str, Card]],
                  winner: str, trick_points: int):
        """Zaznamená štych."""
        cards_str = "  |  ".join(
            f"{name}: {self._card_str(card)}"
            for name, card in played
        )
        self.entries.append(
            f"  Štych {trick_number:2d}: {cards_str}"
            f"  → {winner} (+{trick_points})"
        )

    def log_shoot_moon(self, player: str):
        """Zaznamená shoot the moon."""
        self.entries.append(
            f"  *** SHOOT THE MOON [{player}]: všetky trestné karty! (-10b)"
        )

    def log_declaration_result(self, player: str,
                                declaration: str,
                                fulfilled: bool):
        """Zaznamená výsledok záväzku."""
        if fulfilled:
            bonus = -20 if declaration == "all" else -10
            self.entries.append(
                f"  ✓ Záväzok splnený [{player}]: {bonus}b"
            )
        else:
            self.entries.append(
                f"  ✗ Záväzok nesplnený [{player}]: ostatní -10b"
            )

    def log_round_result(self, results: dict[str, dict]):
        self.entries.append("")
        self.entries.append("VÝSLEDOK KOLA:")
        for name, data in results.items():
            bullet = " 🔴" if data.get("bullet") else ""
            sweep = " *** SWEEP -10b!" if data.get("sweep") else ""
            self.entries.append(
                f"  {name}: +{data['round_points']}b → "
                f"celkom: {data['total_score']}b{bullet}{sweep}"
            )

    def log_no_penalty_streak(self, player: str, streak: int):
        """Zaznamená sériu bez trestných bodov."""
        self.entries.append(
            f"  *** SÉRIA [{player}]: {streak} kôl bez trestných bodov! (-10b)"
        )

    # ------------------------------------------------------------------
    # Uloženie
    # ------------------------------------------------------------------

    def save_round(self):
        """Uloží priebežný log po každom kole."""
        filename = os.path.join(self.log_dir, "current_game.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(self.entries))

    def save(self):
        """Uloží finálny log."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.log_dir, f"game_{timestamp}.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(self.entries))
        return filename

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    @staticmethod
    def _card_str(card: Card) -> str:
        suit_symbols = {
            "heart": "♥", "bell": "●",
            "leaf": "♣", "acorn": "♠"
        }
        rank_symbols = {
            "seven": "7", "eight": "8", "nine": "9",
            "ten": "10", "under": "J", "over": "Q",
            "king": "K", "ace": "A"
        }
        suit = suit_symbols.get(card.suit, card.suit)
        rank = rank_symbols.get(card.rank, card.rank)
        return f"{rank}{suit}"

    def _cards_str(self, cards: list[Card]) -> str:
        return " ".join(self._card_str(c) for c in cards)

    def log_strategy(self, player: str, strategy: str, details: str = ""):
        """Zaznamená použitú stratégiu AI."""
        if details:
            self.entries.append(f"  [AI {player}] {strategy}: {details}")
        else:
            self.entries.append(f"  [AI {player}] {strategy}")

    def __repr__(self) -> str:
        return f"GameLogger(rounds={self.round_number})"