# gui/scoreboard.py

import pygame
import os
from game.player import Player
from game.round import Round
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_YELLOW, COLOR_GREEN, COLOR_RED,
     COLOR_GRAY, COLOR_GOLD,
    COLOR_PENALTY, COLOR_ILLUMINATED,
    WINNING_SCORE, SUIT_ICONS_PATH,
    HIGH_SCORE_THRESHOLD
)


class Scoreboard:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_small = pygame.font.SysFont(None, 20)
        self.font_medium = pygame.font.SysFont(None, 26)
        self.font_large = pygame.font.SysFont(None, 34)
        self._icon_cache: dict[str, pygame.Surface] = {}

        # Rozmery — horizontálny layout
        self.panel_h = 80
        self.panel_y = SCREEN_HEIGHT - self.panel_h - 10
        self.panel_x = SCREEN_WIDTH // 2 - 600
        self.panel_w = 1200
        self.player_w = self.panel_w // 4

    # ------------------------------------------------------------------
    # Hlavná metóda
    # ------------------------------------------------------------------

    def draw(self, players: list[Player], current_round: Round | None):
        """Nakreslí scoresheet panel."""
        self._draw_panel_bg()
        self._draw_players(players, current_round)
        self._draw_round_info(current_round)

    # ------------------------------------------------------------------
    # Pozadie
    # ------------------------------------------------------------------

    def _draw_panel_bg(self):
        """Nakreslí pozadie panelu."""
        overlay = pygame.Surface(
            (self.panel_w, self.panel_h), pygame.SRCALPHA
        )
        overlay.fill((20, 12, 5, 210))
        self.screen.blit(overlay, (self.panel_x, self.panel_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (self.panel_x, self.panel_y, self.panel_w, self.panel_h),
            width=2, border_radius=10
        )

    # ------------------------------------------------------------------
    # Hráči
    # ------------------------------------------------------------------

    def _draw_players(self, players: list[Player],
                      current_round: Round | None):
        """Nakreslí skóre každého hráča."""
        for i, player in enumerate(players):
            x = self.panel_x + i * self.player_w
            y = self.panel_y

            is_current = (
                current_round and
                current_round.phase == "tricks" and
                current_round.get_current_player_index() == i
            )

            # Oddeľovacia čiara medzi hráčmi
            if i > 0:
                pygame.draw.line(
                    self.screen, COLOR_GRAY,
                    (x, y + 5), (x, y + self.panel_h - 5),
                    width=1
                )

            # Meno
            name_color = COLOR_YELLOW if is_current else COLOR_WHITE
            indicator = "► " if is_current else ""
            name_surf = self.font_medium.render(
                f"{indicator}{player.name}", True, name_color
            )
            self.screen.blit(
                name_surf,
                (x + 10, y + 8)
            )

            # Skóre
            score_color = self._score_color(player.total_score)
            score_surf = self.font_large.render(
                str(player.total_score), True, score_color
            )
            self.screen.blit(score_surf, (x + 10, y + 32))

            # Body v kole
            if current_round and current_round.phase == "tricks":
                round_pts = player.round_points
                if round_pts > 0:
                    pts_color = COLOR_PENALTY
                    pts_text = f"+{round_pts}b"
                else:
                    pts_color = COLOR_GRAY
                    pts_text = "0b"
                pts_surf = self.font_small.render(pts_text, True, pts_color)
                pts_rect = pts_surf.get_rect(
                    right=x + self.player_w - 10,
                    top=y + 35
                )
                self.screen.blit(pts_surf, pts_rect)

            # Vysvietenie ikonky
            if current_round:
                self._draw_illumination_icons(player, x, y)

            # Guličky
            self._draw_bullets(player, x, y)

            # Progress bar
            self._draw_progress_bar(
                x=x + 10,
                y=y + self.panel_h - 14,
                width=self.player_w - 20,
                height=6,
                value=player.total_score,
                max_value=WINNING_SCORE
            )

    def _draw_illumination_icons(self, player: Player, x: int, y: int):
        """Nakreslí ikonky vysvietených horníkov."""
        icon_x = x + self.player_w - 30
        icon_y = y + 8

        if player.illuminated_leaf:
            icon = self._load_icon("leaf", 20)
            if icon:
                self.screen.blit(icon, (icon_x, icon_y))
            icon_x -= 25

        if player.illuminated_acorn:
            icon = self._load_icon("acorn", 20)
            if icon:
                self.screen.blit(icon, (icon_x, icon_y))

    def _draw_bullets(self, player: Player, x: int, y: int):
        """Nakreslí guličky hráča."""
        if player.bullets == 0:
            return

        bullet_x = x + 10
        bullet_y = y + self.panel_h - 22

        for i in range(min(player.bullets, 10)):
            pygame.draw.circle(
                self.screen, COLOR_PENALTY,
                (bullet_x + i * 14, bullet_y), 5
            )

    # ------------------------------------------------------------------
    # Info o kole
    # ------------------------------------------------------------------

    def _draw_round_info(self, current_round: Round | None):
        """Nakreslí info o aktuálnom kole."""
        if not current_round:
            return

        # Fáza a štych — v strede nad panelom
        phase_labels = {
            "dealing": "Rozdávanie",
            "game_declaration": "Záväzok",
            "revealing": "Vysvietenie",
            "tricks": f"Štych {current_round.trick_number + 1} / 8",
            "scoring": "Bodovanie",
            "done": "Koniec kola"
        }
        phase_text = phase_labels.get(
            current_round.phase, current_round.phase
        )

        phase_surf = self.font_medium.render(phase_text, True, COLOR_GOLD)
        phase_rect = phase_surf.get_rect(
            centerx=SCREEN_WIDTH // 2,
            bottom=self.panel_y - 8
        )
        self.screen.blit(phase_surf, phase_rect)

        # Vysvietenie stavu
        if current_round.leaf_illuminated or current_round.acorn_illuminated:
            parts = []
            if current_round.leaf_illuminated:
                parts.append("Zelený ×2")
            if current_round.acorn_illuminated:
                parts.append("Žaluďový ×2")
            if current_round.leaf_illuminated and current_round.acorn_illuminated:
                parts.append("Srdcia ×2")

            illum_text = " | ".join(parts)
            illum_surf = self.font_small.render(
                illum_text, True, COLOR_ILLUMINATED
            )
            illum_rect = illum_surf.get_rect(
                centerx=SCREEN_WIDTH // 2,
                bottom=self.panel_y - 30
            )
            self.screen.blit(illum_surf, illum_rect)

    # ------------------------------------------------------------------
    # Pomocné metódy
    # ------------------------------------------------------------------
    @staticmethod
    def _score_color(score: int) -> tuple:
        """Vráti farbu skóre."""
        if score >= WINNING_SCORE:
            return COLOR_RED
        if score >= HIGH_SCORE_THRESHOLD:
            return COLOR_YELLOW
        if score == 0:
            return COLOR_GREEN
        return COLOR_WHITE

    def _draw_progress_bar(self, x: int, y: int, width: int,
                           height: int, value: int, max_value: int):
        """Nakreslí progress bar."""
        pygame.draw.rect(
            self.screen, COLOR_GRAY,
            (x, y, width, height), border_radius=3
        )

        fill_ratio = max(0, min(value / max_value, 1.0)) if max_value > 0 else 0
        fill_width = int(width * fill_ratio)

        if fill_width > 0:
            if value >= HIGH_SCORE_THRESHOLD:
                color = COLOR_RED
            elif value >= max_value * 0.5:
                color = COLOR_YELLOW
            else:
                color = COLOR_GOLD
            pygame.draw.rect(
                self.screen, color,
                (x, y, fill_width, height), border_radius=3
            )

        pygame.draw.rect(
            self.screen, COLOR_WHITE,
            (x, y, width, height), width=1, border_radius=3
        )

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

    def __repr__(self) -> str:
        return "Scoreboard()"