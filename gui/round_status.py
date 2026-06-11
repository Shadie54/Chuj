# gui/round_status.py

import pygame
import os
from config import (
    COLOR_WHITE, COLOR_GRAY, COLOR_GOLD,
    COLOR_GREEN, COLOR_RED, COLOR_YELLOW,
    ROUND_STATUS_X, ROUND_STATUS_Y, ROUND_STATUS_W, ROUND_STATUS_H,
    NO_PENALTY_STREAK, get_font, SUIT_ICONS_PATH
)


class RoundStatus:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_small = get_font( 24)  # bolo 20
        self.font_medium = get_font( 30)  # bolo 26
        self.font_large = get_font( 38)  # bolo 32

        # Declaration badges
        self._declaration_badges = {}
        for key in ("all", "none"):
            path = os.path.join("assets", "graphics", f"{key}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                self._declaration_badges[key] = pygame.transform.scale(img, (30, 30))
            except FileNotFoundError:
                self._declaration_badges[key] = None

        # Rozmery
        self.x = ROUND_STATUS_X
        self.y = ROUND_STATUS_Y
        self.w = ROUND_STATUS_W
        self.h = ROUND_STATUS_H

        # Gulička rozmery
        self.bullet_r = 8
        self.bullet_spacing = 20

        icon_h = 25
        self._icons = {}
        for suit in ("leaf", "acorn"):
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@small.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                w, h = img.get_size()
                new_w = int(w * icon_h / h)
                self._icons[suit] = pygame.transform.scale(img, (30,30))
            except FileNotFoundError:
                self._icons[suit] = None

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, players: list, current_round=None):
        """Nakreslí panel so stavom kola."""
        self._draw_bg()

        round_number = current_round.round_number if current_round else None
        deal_seed = current_round.deal_seed if current_round else None
        self._draw_title(round_number, deal_seed)

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

    def _draw_title(self, round_number, deal_seed):
        if round_number is not None:
            round_text = f"KOLO {round_number}"
        else:
            round_text = "KOLO"

        title = self.font_medium.render(round_text, True, COLOR_GOLD)
        title_rect = title.get_rect(
            left=self.x + 30,  # bolo centerx
            top=self.y + 8
        )
        self.screen.blit(title, title_rect)

        if deal_seed is not None:
            seed = self.font_small.render(f" ({deal_seed})", True, COLOR_GRAY)  # pridaj medzeru
            seed_rect = seed.get_rect(
                right=self.x + self.w - 8,
                centery=title_rect.centery  # rovnaká výška ako KOLO
            )
            self.screen.blit(seed, seed_rect)

        pygame.draw.line(self.screen, COLOR_GOLD,
                         (self.x + 10, self.y + 43),
                         (self.x + self.w - 10, self.y + 43), width=1)

    def _draw_players(self, players: list, current_round=None):
        """Nakreslí riadok pre každého hráča."""
        y_start = self.y + 48
        row_h = (self.h - 68) // len(players)

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

            streak_end_x = self.x + 10 + NO_PENALTY_STREAK * self.bullet_spacing + self.bullet_r
            icon_x = max(self.x + 10 + name_surf.get_width() + 6, streak_end_x + 10)

            # Ikonky horníkov
            if current_round:
                for suit in ("leaf", "acorn"):
                    if current_round.illuminated_by.get(suit) == i:
                        icon = self._icons.get(suit)
                        if icon:
                            self.screen.blit(icon, (icon_x, y + 2))
                            icon_x += icon.get_width() + 4
            # Declaration badge
            if current_round and current_round.declaration_player == i:
                badge = self._declaration_badges.get(current_round.declaration_type)
                if badge:
                    self.screen.blit(badge, (icon_x, y + 2))
                    icon_x += badge.get_width() + 4

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
            self._draw_streak(x=self.x + 10, y=y + 35, streak=streak)  # bolo y + 22

    def _draw_streak(self, x: int, y: int, streak: int):
        """Nakreslí 5 guličiek — zelené pre sériu, sivé prázdne."""
        max_show = NO_PENALTY_STREAK
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