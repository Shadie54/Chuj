# gui/round_status.py

import pygame
import os
from gui import layout
from config import (
    COLOR_WHITE, COLOR_GRAY, COLOR_GOLD,
    COLOR_GREEN, COLOR_RED, COLOR_YELLOW,
    NO_PENALTY_STREAK, SUIT_ICONS_PATH
)


class RoundStatus:
    def __init__(self, canvas):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.font_small = self.canvas.font(24)  # bolo 20
        self.font_medium = self.canvas.font(30)  # bolo 26
        self.font_large = self.canvas.font(38)  # bolo 32

        # Declaration badges
        self._declaration_badges = {}
        for key in ("all", "none"):
            path = os.path.join("assets", "graphics", f"{key}.png")
            try:
                self._declaration_badges[key] = self.canvas.image(path, (45, 45))  # bolo 30 (test +50%)
            except (FileNotFoundError, pygame.error):
                self._declaration_badges[key] = None

        # Rozmery
        # Vpravo dole, ukotvený k spodnému okraju (gui/layout.py)
        self.x, self.y, self.w, self.h = layout.game().round_status_rect()

        # Gulička rozmery
        self.bullet_r = 8
        self.bullet_spacing = 20

        self._icons = {}
        for suit in ("leaf", "acorn"):
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@small.png")
            try:
                self._icons[suit] = self.canvas.image(path, (30, 30))
            except (FileNotFoundError, pygame.error):
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
        self.canvas.overlay(pygame.Rect((self.x, self.y), (self.w, self.h)), (20, 12, 5, 210))
        self.canvas.rect(COLOR_GOLD,
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
        self.canvas.blit(title, title_rect)

        if deal_seed is not None:
            # Len pre zobrazenie — oddeľovač tisícok medzerou (napr. 27 856 498),
            # samotná hodnota deal_seed (v tester_main.py --seed X a pod.) sa nemení.
            seed_text = f"{deal_seed:,}".replace(",", " ")
            seed = self.font_small.render(f" ({seed_text})", True, COLOR_GRAY)  # pridaj medzeru
            seed_rect = seed.get_rect(
                right=self.x + self.w - 8,
                centery=title_rect.centery  # rovnaká výška ako KOLO
            )
            self.canvas.blit(seed, seed_rect)

        self.canvas.line(COLOR_GOLD,
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
            self.canvas.blit(name_surf, (self.x + 10, y))

            streak_end_x = self.x + 10 + NO_PENALTY_STREAK * self.bullet_spacing + self.bullet_r
            icon_x = max(self.x + 10 + name_surf.get_width() + 6, streak_end_x + 10)

            # Ikonky horníkov
            if current_round:
                for suit in ("leaf", "acorn"):
                    if current_round.illuminated_by.get(suit) == i:
                        icon = self._icons.get(suit)
                        if icon:
                            self.canvas.blit(icon, (icon_x, y + 2))
                            icon_x += icon.get_width() + 4
            # Declaration badge
            if current_round and current_round.declaration_player == i:
                badge = self._declaration_badges.get(current_round.declaration_type)
                if badge:
                    self.canvas.blit(badge, (icon_x, y + 2))
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
            self.canvas.blit(pts_surf, pts_rect)

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
                self.canvas.circle(COLOR_GREEN, (cx, y), self.bullet_r)
                self.canvas.circle(COLOR_WHITE, (cx, y), self.bullet_r, width=1)
            else:
                # Prázdna sivá
                self.canvas.circle(COLOR_GRAY, (cx, y), self.bullet_r, width=1)

        # Bonus text ak dosiahol max
        if streak >= max_show:
            bonus_surf = self.font_small.render("-10b!", True, COLOR_GREEN)
            self.canvas.blit(bonus_surf, (x + max_show * self.bullet_spacing + 5, y - 6))

    def __repr__(self) -> str:
        return "RoundStatus()"