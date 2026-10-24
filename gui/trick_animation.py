# gui/trick_animation.py

import pygame
from gui import layout


class TrickAnimation:
    def __init__(self, canvas, card_renderer):
        self.canvas = canvas      # gui/canvas.py::Canvas (rework rozlíšení)
        self.card_renderer = card_renderer
        self.cards_in_flight: list[dict] = []
        self.done: bool = True
        self.card_speed: float = 40.0       # rýchla animácia
        self._talon_anim_started: bool = False

        # Cieľové pozície pre každého hráča (stred ruky) — gui/layout.py,
        # ukotvené rovnako ako ruky (pri 1080p: 930 / (1620,410) / 20 / (50,410)).
        self.target_positions = layout.game().trick_collect_targets

    def start(self, played_cards: list[tuple[int, object]],
              winner_index: int):
        """
        Spustí animáciu — karty letia k víťazovi.
        played_cards: [(player_index, card), ...]
        """
        self.cards_in_flight = []
        self.done = False

        target_x, target_y = self.target_positions[winner_index]

        # Štartové pozície kariet na stole
        start_positions = layout.game().trick_positions

        for i, (player_idx, card) in enumerate(played_cards):
            sx, sy = start_positions[player_idx]
            self.cards_in_flight.append({
                "card": card,
                "player_index": player_idx,
                "x": float(sx),
                "y": float(sy),
                "target_x": float(target_x),
                "target_y": float(target_y),
                "arrived": False,
                "delay": i * 80         # ms — letia postupne
            })

        self._start_time = pygame.time.get_ticks()

    def update(self):
        """Aktualizuje pozície kariet."""
        if self.done:
            return

        now = pygame.time.get_ticks()

        for card in self.cards_in_flight:
            if card["arrived"]:
                continue

            # Delay — karty letia postupne
            if now < self._start_time + card["delay"]:
                continue

            dx = card["target_x"] - card["x"]
            dy = card["target_y"] - card["y"]
            dist = (dx ** 2 + dy ** 2) ** 0.5

            if dist <= self.card_speed:
                card["arrived"] = True
            else:
                card["x"] += dx / dist * self.card_speed
                card["y"] += dy / dist * self.card_speed

        # Hotovo ak všetky doleteli
        if all(c["arrived"] for c in self.cards_in_flight):
            self.done = True
            self.cards_in_flight = []

    def draw(self):
        """Nakreslí karty v lete."""
        if self.done:
            return

        now = pygame.time.get_ticks()

        for card in self.cards_in_flight:
            if card["arrived"]:
                continue
            if now < self._start_time + card["delay"]:
                # Karta ešte neletí — nakresli ju na mieste
                img = self.card_renderer._get_card_image(card["card"])
                self.canvas.blit(img, (int(card["x"]), int(card["y"])))
                continue

            img = self.card_renderer._get_card_image(card["card"])
            self.canvas.blit(img, (int(card["x"]), int(card["y"])))

    @property
    def is_done(self) -> bool:
        return self.done

    def __repr__(self) -> str:
        return f"TrickAnimation(done={self.done})"