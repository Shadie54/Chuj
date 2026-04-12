# gui/game_over_screen.py

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_RED,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS
)


class GameOverScreen:
    def __init__(self, screen: pygame.Surface, players: list,
                 loser, round_number: int):
        """
        players: zoznam všetkých hráčov
        loser: porazený hráč (najviac bodov nad 100)
        round_number: počet odohraných kôl
        """
        self.screen = screen
        self.players = players
        self.loser = loser
        self.round_number = round_number
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont(None, 120)
        self.font_large = pygame.font.SysFont(None, FONT_SIZE_LARGE + 16)
        self.font_medium = pygame.font.SysFont(None, FONT_SIZE_MEDIUM)

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        btn_w = 220
        btn_h = 60
        center_x = SCREEN_WIDTH // 2
        btn_y = SCREEN_HEIGHT - 160

        self.btn_new_game = pygame.Rect(
            center_x - btn_w - 20, btn_y, btn_w, btn_h
        )
        self.btn_menu = pygame.Rect(
            center_x + 20, btn_y, btn_w, btn_h
        )
        self.hover = {"new_game": False, "menu": False}

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "menu"

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self.btn_new_game.collidepoint(event.pos):
                            return "new_game"
                        if self.btn_menu.collidepoint(event.pos):
                            return "menu"

            self.hover["new_game"] = self.btn_new_game.collidepoint(mouse_pos)
            self.hover["menu"] = self.btn_menu.collidepoint(mouse_pos)

            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        self._draw_title()
        self._draw_scores()
        self._draw_info()
        self._draw_buttons()

    def _draw_title(self):
        """Nakreslí nadpis."""
        is_human_loser = self.loser.is_human

        if is_human_loser:
            title_text = "SI CHUJ! 😄"
            title_color = COLOR_RED
        else:
            title_text = "VÍŤAZSTVO!"
            title_color = COLOR_GOLD

        title = self.font_title.render(title_text, True, title_color)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 130))
        self.screen.blit(title, title_rect)

        # Meno porazeného
        loser_text = f"{self.loser.name} prehral s {self.loser.total_score} bodmi!"
        loser_surf = self.font_large.render(loser_text, True, COLOR_WHITE)
        loser_rect = loser_surf.get_rect(center=(SCREEN_WIDTH // 2, 220))
        self.screen.blit(loser_surf, loser_rect)

        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (SCREEN_WIDTH // 2 - 400, 260),
            (SCREEN_WIDTH // 2 + 400, 260),
            width=2
        )

    def _draw_scores(self):
        """Nakreslí finálne skóre."""
        title = self.font_medium.render("FINÁLNE SKÓRE", True, COLOR_GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 300))
        self.screen.blit(title, title_rect)

        # Zoraď hráčov podľa skóre (najmenej = najlepší)
        sorted_players = sorted(
            self.players, key=lambda p: p.total_score
        )

        panel_w = 600
        panel_h = 55
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        start_y = 340

        for i, player in enumerate(sorted_players):
            y = start_y + i * 70
            is_loser = player == self.loser

            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            if is_loser:
                overlay.fill((200, 60, 40, 80))
            else:
                overlay.fill((20, 12, 5, 160))
            self.screen.blit(overlay, (panel_x, y))

            border_color = COLOR_RED if is_loser else COLOR_GRAY
            pygame.draw.rect(
                self.screen, border_color,
                (panel_x, y, panel_w, panel_h),
                width=2, border_radius=8
            )

            # Poradie
            rank_text = f"#{i + 1}"
            rank_color = COLOR_GOLD if i == 0 else COLOR_GRAY
            rank_surf = self.font_large.render(rank_text, True, rank_color)
            self.screen.blit(rank_surf, (panel_x + 15, y + 10))

            # Meno
            name_color = COLOR_RED if is_loser else COLOR_WHITE
            name_surf = self.font_large.render(player.name, True, name_color)
            self.screen.blit(name_surf, (panel_x + 70, y + 10))

            # Skóre
            score_surf = self.font_large.render(
                str(player.total_score), True, name_color
            )
            score_rect = score_surf.get_rect(
                right=panel_x + panel_w - 15,
                top=y + 10
            )
            self.screen.blit(score_surf, score_rect)

            # Guličky
            if player.bullets > 0:
                bullets_text = "●" * min(player.bullets, 10)
                bullets_surf = self.font_medium.render(
                    bullets_text, True, COLOR_RED
                )
                self.screen.blit(
                    bullets_surf,
                    (panel_x + 70, y + panel_h - 18)
                )

    def _draw_info(self):
        """Nakreslí info o hre."""
        info_text = f"Hra trvala {self.round_number} kôl"
        info_surf = self.font_medium.render(info_text, True, COLOR_GRAY)
        info_rect = info_surf.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 200)
        )
        self.screen.blit(info_surf, info_rect)

    def _draw_buttons(self):
        self._draw_btn(
            self.btn_new_game, "Nová hra",
            COLOR_BUTTON_PRIMARY, self.hover["new_game"]
        )
        self._draw_btn(
            self.btn_menu, "Menu",
            COLOR_BUTTON_SECONDARY, self.hover["menu"]
        )

    def _draw_btn(self, rect: pygame.Rect, text: str,
                  color: tuple, hover: bool):
        alpha = 240 if hover else 200
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.screen.blit(overlay, rect.topleft)

        border_color = COLOR_WHITE if hover else COLOR_GOLD
        pygame.draw.rect(
            self.screen, border_color,
            rect, width=2, border_radius=BUTTON_RADIUS
        )

        surf = self.font_large.render(text, True, COLOR_WHITE)
        text_rect = surf.get_rect(center=rect.center)
        self.screen.blit(surf, text_rect)

    def __repr__(self) -> str:
        return "GameOverScreen()"