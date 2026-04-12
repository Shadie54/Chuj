# gui/round_status.py

import pygame
from config import (
    COLOR_WHITE, COLOR_GRAY, COLOR_GOLD,
    COLOR_GREEN, COLOR_RED, COLOR_YELLOW,
    ROUND_STATUS_X, ROUND_STATUS_Y, ROUND_STATUS_W, ROUND_STATUS_H,
    NO_PENALTY_STREAK
)


class RoundStatus:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_small = pygame.font.SysFont(None, 24)  # bolo 20
        self.font_medium = pygame.font.SysFont(None, 30)  # bolo 26
        self.font_large = pygame.font.SysFont(None, 38)  # bolo 32

        # Rozmery
        self.x = ROUND_STATUS_X
        self.y = ROUND_STATUS_Y
        self.w = ROUND_STATUS_W
        self.h = ROUND_STATUS_H

        # Gulička rozmery
        self.bullet_r = 6
        self.bullet_spacing = 16

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, players: list, current_round=None):
        """Nakreslí panel so stavom kola."""
        self._draw_bg()
        self._draw_title(current_round)
        self._draw_players(players, current_round)

    def _draw_bg(self):
        """Nakreslí pozadie panelu."""
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        overlay.fill((20, 12, 5, 210))
        self.screen.blit(overlay, (self.x, self.y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (self.x, self.y, self.w, self.h),
            width=2, border_radius=10
        )

    def _draw_title(self, current_round=None):
        """Nakreslí nadpis."""
        # Číslo kola
        round_text = "KOLO"
        if current_round:
            from game.game_state import GameState
        title = self.font_medium.render(round_text, True, COLOR_GOLD)
        title_rect = title.get_rect(
            centerx=self.x + self.w // 2,
            top=self.y + 8
        )
        self.screen.blit(title, title_rect)

        # Oddeľovacia čiara
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (self.x + 10, self.y + 30),
            (self.x + self.w - 10, self.y + 30),
            width=1
        )

    def _draw_players(self, players: list, current_round=None):
        """Nakreslí riadok pre každého hráča."""
        y_start = self.y + 38
        row_h = (self.h - 45) // len(players)

        for i, player in enumerate(players):
            y = y_start + i * row_h

            # Zvýraznenie ak je na ťahu
            is_current = (
                current_round and
                current_round.phase == "tricks" and
                current_round.get_current_player_index() == i
            )
            name_color = COLOR_YELLOW if is_current else COLOR_WHITE

            # Meno
            name_surf = self.font_small.render(
                player.name[:10], True, name_color
            )
            self.screen.blit(name_surf, (self.x + 10, y))

            # Body aktuálneho kola
            pts = player.round_points
            if pts > 0:
                pts_color = COLOR_RED
                pts_text = f"+{pts}b"
            else:
                pts_color = COLOR_GRAY
                pts_text = "0b"

            pts_surf = self.font_small.render(pts_text, True, pts_color)
            pts_rect = pts_surf.get_rect(
                right=self.x + self.w - 10,
                top=y
            )
            self.screen.blit(pts_surf, pts_rect)

            # Zelené guličky — séria bez trestných bodov
            streak = player.no_penalty_streak
            self._draw_streak(x=self.x + 10, y=y + 22, streak=streak)  # bolo y + 16

    def _draw_streak(self, x: int, y: int, streak: int):
        """Nakreslí 5 guličiek — zelené pre sériu, sivé prázdne."""
        max_show = max_show = NO_PENALTY_STREAK
        for i in range(max_show):
            cx = x + i * self.bullet_spacing + self.bullet_r
            if i < streak:
                # Plná zelená
                pygame.draw.circle(self.screen, COLOR_GREEN, (cx, y), self.bullet_r)
                pygame.draw.circle(self.screen, COLOR_WHITE, (cx, y), self.bullet_r, width=1)
            else:
                # Prázdna sivá
                pygame.draw.circle(self.screen, COLOR_GRAY, (cx, y), self.bullet_r, width=1)

        # Bonus text ak dosiahol max
        if streak >= max_show:
            bonus_surf = self.font_small.render("-10b!", True, COLOR_GREEN)
            self.screen.blit(bonus_surf, (x + max_show * self.bullet_spacing + 5, y - 6))

    def __repr__(self) -> str:
        return "RoundStatus()"