# gui/speech_bubble.py

import pygame
import os
from config import (
    TABLE_CENTER_X,
    COLOR_WHITE, COLOR_GOLD, COLOR_YELLOW, COLOR_GREEN, COLOR_RED,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    SUIT_ICONS_PATH, SCREEN_WIDTH, SCREEN_HEIGHT, get_font
)


class SpeechBubble:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = get_font(FONT_SIZE_MEDIUM + 4)
        self.font_medium = get_font(FONT_SIZE_MEDIUM)

        self._icon_cache: dict[str, pygame.Surface] = {}

        # Aktívne bubliny [{player_index, text, suit, timer, color}]
        self.bubbles: list[dict] = []

        # Pozície bublín pre každého hráča
        self.bubble_positions = {
            0: (TABLE_CENTER_X, 820),  # hráč dole — ok
            1: (SCREEN_WIDTH - 520, 380),  # PC1 vpravo — viac doľava od kariet (bolo -380)
            2: (TABLE_CENTER_X, 380),  # PC2 hore — trochu nižšie (bolo 180)
            3: (520, 380),  # PC3 vľavo — viac doprava od kariet (bolo 380)
        }

    # ------------------------------------------------------------------
    # Pridanie bubliny
    # ------------------------------------------------------------------

    def show_trump(self, player_index: int, suit: str,
                   is_new: bool = False, duration_ms: int = 4000):
        """Zobrazí tromfovú bublinu."""
        text = "NOVÝ TROMF!" if is_new else "TROMF!"
        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=suit,
            duration_ms=duration_ms,
            color=COLOR_GOLD
        )

    def show_bid(self, player_index: int, text: str,
                 duration_ms: int = 5000):
        """Zobrazí biddingová bublinu."""
        if text is None:
            display_text = "Ja nič"
            color = (150, 150, 150)
        else:
            display_text = text
            color = COLOR_YELLOW

        self._add_bubble(
            player_index=player_index,
            text=display_text,
            suit=None,
            duration_ms=duration_ms,
            color=color
        )

    def show_instruction(self, player_index: int, text: str):
        """
        Zobrazí inštrukciu ako bublinu hráča.
        Ostáva zobrazená kým ju manuálne neodstránime.
        """
        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=None,
            duration_ms=99999999,  # "nekonečno" — zmizne manuálne
            color=COLOR_WHITE
        )

    def hide_instruction(self, player_index: int):
        """Odstráni inštrukčnú bublinu."""
        self.bubbles = [
            b for b in self.bubbles
            if b["player_index"] != player_index
        ]

    def _add_bubble(self, player_index: int, text: str,
                    suit: str | None, duration_ms: int, color: tuple):
        """Pridá bublinu do zoznamu."""
        # Odstráň existujúcu bublinu toho istého hráča
        self.bubbles = [
            b for b in self.bubbles
            if b["player_index"] != player_index
        ]
        self.bubbles.append({
            "player_index": player_index,
            "text": text,
            "suit": suit,
            "timer": pygame.time.get_ticks() + duration_ms,
            "color": color
        })

    # ------------------------------------------------------------------
    # Aktualizácia
    # ------------------------------------------------------------------

    def update(self):
        """Odstráni expirované bubliny."""
        now = pygame.time.get_ticks()
        self.bubbles = [
            b for b in self.bubbles
            if now < b["timer"]
        ]

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self):
        """Nakreslí všetky aktívne bubliny."""
        self.update()
        for bubble in self.bubbles:
            self._draw_bubble(bubble)

    def _draw_bubble(self, bubble: dict):
        """Nakreslí jednu bublinu."""
        player_index = bubble["player_index"]
        cx, cy = self.bubble_positions[player_index]

        text_surf = self.font_large.render(bubble["text"], True, bubble["color"])
        text_w = text_surf.get_width()
        text_h = text_surf.get_height()

        # Rozmery bubliny
        icon_size = 40 if bubble["suit"] else 0
        padding = 16
        bubble_w = max(text_w, icon_size) + padding * 2
        bubble_h = text_h + icon_size + padding * 2 + (8 if bubble["suit"] else 0)

        bx = cx - bubble_w // 2
        by = cy - bubble_h

        # Pozadie bubliny
        overlay = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
        overlay.fill((20, 12, 5, 220))
        self.screen.blit(overlay, (bx, by))

        # Okraj
        pygame.draw.rect(
            self.screen, bubble["color"],
            (bx, by, bubble_w, bubble_h),
            width=2, border_radius=12
        )

        # Chvost bubliny (trojuholník)
        self._draw_tail(cx, by + bubble_h, by, bubble_w, bubble_h, player_index, bubble["color"])

        # Text
        text_rect = text_surf.get_rect(
            centerx=cx,
            top=by + padding
        )
        self.screen.blit(text_surf, text_rect)

        # Ikonka farby (ak je tromf)
        if bubble["suit"]:
            icon = self._load_icon(bubble["suit"], icon_size)
            if icon:
                icon_rect = icon.get_rect(
                    centerx=cx,
                    top=by + padding + text_h + 8
                )
                self.screen.blit(icon, icon_rect)

    def _draw_tail(self, cx: int, base_y: int, by: int, bubble_w: int, bubble_h: int,
                   player_index: int, color: tuple):
        tail_size = 12
        bx = cx - bubble_w // 2

        if player_index == 0:
            # Hráč dole — chvost dole (zo spodku bubliny)
            points = [
                (cx - tail_size, base_y),
                (cx + tail_size, base_y),
                (cx, base_y + tail_size * 2)
            ]
        elif player_index == 1:
            # PC1 vpravo — chvost doprava (z pravého okraja bubliny)
            mid_y = by + bubble_h // 2
            right_x = bx + bubble_w
            points = [
                (right_x, mid_y - tail_size),
                (right_x, mid_y + tail_size),
                (right_x + tail_size * 2, mid_y)
            ]
        elif player_index == 2:
            # PC2 hore — chvost hore (z vrchného okraja bubliny)
            points = [
                (cx - tail_size, by),
                (cx + tail_size, by),
                (cx, by - tail_size * 2)
            ]
        else:
            # PC3 vľavo — chvost doľava (z ľavého okraja bubliny)
            mid_y = by + bubble_h // 2
            points = [
                (bx, mid_y - tail_size),
                (bx, mid_y + tail_size),
                (bx - tail_size * 2, mid_y)
            ]

        pygame.draw.polygon(self.screen, color, points)

    def _load_icon(self, suit: str, size: int) -> pygame.Surface | None:
        """Načíta ikonku farby."""
        key = f"{suit}-{size}"
        if key not in self._icon_cache:
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@medium.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, (size, size))
                self._icon_cache[key] = img
            except FileNotFoundError:
                self._icon_cache[key] = None
        return self._icon_cache[key]

    def show_round_result(self, player_index: int, points: int,
                          is_bidder: bool, fulfilled: bool = True):
        """Zobrazí výsledok kola ako bublinu."""
        if is_bidder:
            if fulfilled:
                text = f"+{points}"
                color = COLOR_GREEN
            else:
                text = f"-{points}"
                color = COLOR_RED
        else:
            text = f"+{points}"
            color = COLOR_GREEN

        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=None,
            duration_ms=3000,
            color=color
        )

    def __repr__(self) -> str:
        return f"SpeechBubble(active={len(self.bubbles)})"