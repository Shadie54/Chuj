# gui/card_throw_animation.py

import pygame
from config import TRICK_START_POSITIONS


class CardThrowAnimation:
    """
    Veľmi rýchla animácia — karta letí z ruky hráča (odkiaľ bola
    zahraná) na svoje miesto na stole (TRICK_START_POSITIONS).

    Na rozdiel od TrickAnimation (ktorá zbiera už kompletný štich
    k víťazovi na konci) toto rieši samotné odhodenie JEDNEJ karty
    v momente, keď ju hráč/AI zahrá — aby to nepôsobilo sekavo
    (karta sa dnes objaví na stole okamžite, bez prechodu).
    """

    def __init__(self, screen: pygame.Surface, card_renderer):
        self.screen = screen
        self.card_renderer = card_renderer
        self.in_flight: dict[int, dict] = {}  # player_index -> card dict
        self.card_speed: float = 100.0        # veľmi rýchla, kratšia dráha než TrickAnimation

    def start(self, player_index: int, card, start_pos: tuple[int, int]):
        """Spustí let karty z start_pos (stred karty v ruke) do jej miesta na stole."""
        target_x, target_y = TRICK_START_POSITIONS[player_index]
        sx, sy = start_pos
        self.in_flight[player_index] = {
            "card": card,
            "x": float(sx),
            "y": float(sy),
            "target_x": float(target_x),
            "target_y": float(target_y),
            "settled": False,
        }

    def update(self):
        """Aktualizuje pozície letiacich kariet."""
        if not self.in_flight:
            return

        arrived = []
        for player_index, c in self.in_flight.items():
            dx = c["target_x"] - c["x"]
            dy = c["target_y"] - c["y"]
            dist = (dx ** 2 + dy ** 2) ** 0.5

            if dist <= self.card_speed:
                # Posledný krok — dorovnaj PRESNE na cieľ (rovnaká pozícia,
                # akú potom kreslí draw_trick), aby nebol viditeľný skok.
                # Nechá sa doletená karta ešte 1 snímok takto vykresliť cez
                # animáciu (settled), až potom zmizne a prevezme ju draw_trick.
                if c["settled"]:
                    arrived.append(player_index)
                else:
                    c["x"] = c["target_x"]
                    c["y"] = c["target_y"]
                    c["settled"] = True
            else:
                c["x"] += dx / dist * self.card_speed
                c["y"] += dy / dist * self.card_speed

        for player_index in arrived:
            del self.in_flight[player_index]

    def draw(self):
        """Nakreslí karty v lete."""
        for c in self.in_flight.values():
            img = self.card_renderer._get_card_image(c["card"])
            rect = img.get_rect(center=(int(c["x"]), int(c["y"])))
            self.screen.blit(img, rect)

    def is_in_flight(self, player_index: int) -> bool:
        return player_index in self.in_flight

    def __repr__(self) -> str:
        return f"CardThrowAnimation(in_flight={len(self.in_flight)})"
