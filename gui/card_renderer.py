# gui/card_renderer.py

import pygame
import os
from game.card import Card
from game.trick import Trick
from config import (
    CARDS_MEDIUM_PATH, CARDS_SMALL_PATH, CARD_BACK_IMAGE,
    CARD_SIZE_MEDIUM, CARD_SIZE_SMALL,
    COLOR_GREEN, COLOR_WHITE,
    HAND_CONFIGS, TRICK_START_POSITIONS
)


class CardRenderer:
    def __init__(self, screen: pygame.Surface, debug: bool = False):
        self.screen = screen
        self.debug = debug
        self._cache: dict[str, pygame.Surface] = {}     # cache načítaných obrázkov
        self.hand_configs = HAND_CONFIGS
        self.trick_positions = TRICK_START_POSITIONS
    # ------------------------------------------------------------------
    # Načítanie obrázkov
    # ------------------------------------------------------------------

    def _load_image(self, filename: str, size: tuple, path: str) -> pygame.Surface:
        """Načíta obrázok z disku alebo z cache."""
        key = f"{path}/{filename}"
        if key not in self._cache:
            full_path = os.path.join(path, filename)
            try:
                img = pygame.image.load(full_path).convert_alpha()
                img = pygame.transform.scale(img, size)
                self._cache[key] = img
            except FileNotFoundError:
                # Ak obrázok chýba — nakreslíme placeholder
                surf = pygame.Surface(size, pygame.SRCALPHA)
                surf.fill((200, 200, 200))
                font = pygame.font.SysFont(None, 18)
                text = font.render(filename[:10], True, (0, 0, 0))
                surf.blit(text, (5, size[1] // 2 - 10))
                self._cache[key] = surf
        return self._cache[key]

    def _get_card_image(self, card: Card, size: str = "medium") -> pygame.Surface:
        """Vráti obrázok karty."""
        path = CARDS_MEDIUM_PATH if size == "medium" else CARDS_SMALL_PATH
        card_size = CARD_SIZE_MEDIUM if size == "medium" else CARD_SIZE_SMALL
        return self._load_image(card.image_name, card_size, path)

    def _get_card_back(self, size: str = "medium") -> pygame.Surface:
        """Vráti obrázok zadnej strany karty."""
        path = CARDS_MEDIUM_PATH if size == "medium" else CARDS_SMALL_PATH
        card_size = CARD_SIZE_MEDIUM if size == "medium" else CARD_SIZE_SMALL
        return self._load_image(CARD_BACK_IMAGE, card_size, path)

    # ------------------------------------------------------------------
    # Kreslenie ruky hráča
    # ------------------------------------------------------------------

    def draw_hand(self, cards, player_index, is_human,
                  selected_cards, highlight_playable,
                  lead_suit,selected_illumination=None, trick_number: int = 0):
        """Nakreslí ruku hráča."""
        if not cards:
            return

        config = self.hand_configs[player_index]
        show_faces = is_human or self.debug

        for i, card in enumerate(cards):
            # PC2 — obráť poradie kreslenia
            if player_index == 2:
                display_index = len(cards) - 1 - i
            else:
                display_index = i

            x, y = self._card_position(config, display_index)

            # Posun vybranej karty (talon)
            if card in selected_cards:
                y -= 20 if config["direction"] == "horizontal" else 0
                x -= 20 if config["direction"] == "vertical" else 0

            # Posun vysvietených horníkov ← presunuté sem
            if selected_illumination and card in selected_illumination:
                if config["direction"] == "horizontal":
                    if player_index == 2:
                        y += 20  # PC2 — dole
                    else:
                        y -= 20  # PC0 — hore (hráč)
                else:
                    if player_index == 1:
                        x += 20  # PC1 — doprava
                    else:
                        x -= 20  # PC3 — doľava

            if show_faces:
                img = self._get_card_image(card)
            else:
                # AI karta — skontroluj či je vysvietená
                if selected_illumination and card in selected_illumination:
                    img = self._get_card_image(card)  # líc namiesto rubu
                else:
                    img = self._get_card_back()

            # Rotácia
            if config["direction"] == "vertical":
                if player_index == 3:
                    img = pygame.transform.rotate(img, -90)
                else:
                    img = pygame.transform.rotate(img, 90)
            elif player_index == 2:
                img = pygame.transform.rotate(img, 180)

            self.screen.blit(img, (x, y))  # ← teraz na správnej pozícii

            # Zvýraznenie hrateľných kariet
            if highlight_playable and show_faces:
                from game.hand import Hand
                h = Hand()
                h.add_cards(cards)
                playable = h.get_playable_cards(lead_suit, trick_number)
                if card in playable:
                    self._draw_highlight(x, y, CARD_SIZE_MEDIUM, COLOR_GREEN)
                else:
                    self._draw_highlight(x, y, CARD_SIZE_MEDIUM, (100, 100, 100, 100))

    @staticmethod
    def _card_position(config: dict, index: int) -> tuple[int, int]:
        """Vypočíta pozíciu karty v ruke podľa konfigurácie."""
        if config["direction"] == "horizontal":
            x = config["x"] + index * config["offset"]
            y = config["y"]
        else:
            x = config["x"]
            y = config["y"] + index * config["offset"]
        return x, y

    def _draw_highlight(self, x: int, y: int, size: tuple, color: tuple):
        """Nakreslí farebný okraj okolo karty."""
        rect = pygame.Rect(x - 2, y - 2, size[0] + 4, size[1] + 4)
        pygame.draw.rect(self.screen, color, rect, width=3, border_radius=5)

    # ------------------------------------------------------------------
    # Kreslenie štichu na stole
    # ------------------------------------------------------------------

    def draw_trick(self, trick: Trick):
        """Nakreslí aktuálny štich na stole."""
        for player_index, card in trick.played_cards:
            pos = self.trick_positions[player_index]
            img = self._get_card_image(card)
            rect = img.get_rect(center=pos)
            self.screen.blit(img, rect)

            # V debug móde zobraz index hráča
            if self.debug:
                font = pygame.font.SysFont(None, 20)
                label = font.render(str(player_index), True, COLOR_WHITE)
                self.screen.blit(label, (rect.x, rect.y - 15))

    # ------------------------------------------------------------------
    # Detekcia kliku na kartu
    # ------------------------------------------------------------------

    def get_clicked_card(self, pos: tuple[int, int],
                         cards: list[Card],
                         player_index: int) -> Card | None:
        """
        Vráti kartu na ktorú hráč klikol.
        Prechádza karty od poslednej (vrchnej) po prvú.
        """
        if not cards:
            return None

        config = self.hand_configs[player_index]
        card_w, card_h = CARD_SIZE_MEDIUM

        # Prechádzame od konca (vrchná karta je naposledy kreslená)
        for i in range(len(cards) - 1, -1, -1):
            x, y = self._card_position(config, i)

            if config["direction"] == "vertical":
                # Rotovaná karta má prehodené rozmery
                rect = pygame.Rect(x, y, card_h, card_w)
            else:
                rect = pygame.Rect(x, y, card_w, card_h)

            if rect.collidepoint(pos):
                return cards[i]

        return None

    def __repr__(self) -> str:
        return f"CardRenderer(debug={self.debug}, cached={len(self._cache)} images)"