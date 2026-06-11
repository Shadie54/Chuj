# gui/game_over_screen.py

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_RED,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS, get_font
)


class GameOverScreen:
    def __init__(self, screen: pygame.Surface, players: list,
                 loser, round_number: int, game_state=None):
        """
        players: zoznam všetkých hráčov
        loser: porazený hráč (najviac bodov nad 100)
        round_number: počet odohraných kôl
        """
        self.screen = screen
        self.players = players
        self.loser = loser
        self.round_number = round_number
        self.game_state = game_state
        self.show_chujogram = False
        self.clock = pygame.time.Clock()


        self.font_title = get_font(90)  # bolo 120
        self.font_large = get_font(FONT_SIZE_LARGE + 8)  # bolo +16
        self.font_medium = get_font(FONT_SIZE_MEDIUM + 2)  # bolo FONT_SIZE_MEDIUM

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        btn_w = 220
        btn_h = 60
        center_x = SCREEN_WIDTH // 2
        btn_y = SCREEN_HEIGHT - 180

        self.btn_new_game = pygame.Rect(center_x - btn_w - 20, btn_y, btn_w, btn_h)
        self.btn_menu = pygame.Rect(center_x + 20, btn_y, btn_w, btn_h)
        self.btn_chujogram = pygame.Rect( center_x - btn_w // 2, 285, btn_w, btn_h)

        self.hover = {"new_game": False, "menu": False, "chujogram": False}

        self.chujogram_scroll = 0

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
                if event.type == pygame.MOUSEWHEEL:
                    if self.show_chujogram:
                        self.chujogram_scroll = max(
                            0, self.chujogram_scroll - event.y * 20
                        )

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self.show_chujogram:
                            self.show_chujogram = False
                        elif self.btn_chujogram.collidepoint(event.pos):
                            self.show_chujogram = True
                        elif self.btn_new_game.collidepoint(event.pos):
                            return "new_game"
                        elif self.btn_menu.collidepoint(event.pos):
                            return "menu"

            self.hover["new_game"] = self.btn_new_game.collidepoint(mouse_pos)
            self.hover["menu"] = self.btn_menu.collidepoint(mouse_pos)
            self.hover["chujogram"] = self.btn_chujogram.collidepoint(mouse_pos)

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
        if self.show_chujogram:
            self._draw_chujogram_overlay()

    def _draw_title(self):
        """Nakreslí nadpis."""
        is_human_loser = self.loser.is_human

        if is_human_loser:
            title_text = "SI CHUJ! :D"
            title_color = COLOR_RED
        else:
            title_text = "VÍŤAZSTVO!"
            title_color = COLOR_GOLD

        title = self.font_title.render(title_text, True, title_color)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 110))  # bolo 130

        self.screen.blit(title, title_rect)

        # Meno porazeného
        loser_text = f"{self.loser.name} prehral s {self.loser.total_score} bodmi!"
        loser_surf = self.font_large.render(loser_text, True, COLOR_WHITE)
        loser_rect = loser_surf.get_rect(center=(SCREEN_WIDTH // 2, 195))  # bolo 220
        self.screen.blit(loser_surf, loser_rect)

        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (SCREEN_WIDTH // 2 - 400, 235),
            (SCREEN_WIDTH // 2 + 400, 235),
            width=2
        )

    def _draw_scores(self):
        """Nakreslí finálne skóre."""
        title = self.font_medium.render("FINÁLNE SKÓRE", True, COLOR_GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 265))
        self.screen.blit(title, title_rect)

        # Zoraď hráčov podľa skóre (najmenej = najlepší)
        sorted_players = sorted(
            self.players, key=lambda p: p.total_score
        )

        panel_w = 650  # bolo 600
        panel_h = 60  # bolo 55
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        start_y = 380     # bolo 300

        for i, player in enumerate(sorted_players):
            y = start_y + i * 80         # bolo i * 75
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
            rank_rect = rank_surf.get_rect(right=panel_x + 65, top=y + 12)  # zarovnaný vpravo
            self.screen.blit(rank_surf, rank_rect)

            # Meno
            name_color = COLOR_RED if is_loser else COLOR_WHITE
            name_surf = self.font_large.render(player.name, True, name_color)
            self.screen.blit(name_surf, (panel_x + 75, y + 12))   # bolo +70, +10

            # Skóre
            score_surf = self.font_large.render(
                str(player.total_score), True, name_color
            )
            score_rect = score_surf.get_rect(
                right=panel_x + panel_w - 15,
                top=y + 10
            )
            self.screen.blit(score_surf, score_rect)

    def _draw_chujogram_overlay(self):
        from gui.chujogram_panel import ChujogramPanel

        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 240))
        self.screen.blit(dark, (0, 0))

        if not hasattr(self, '_chujogram_panel'):
            self._chujogram_panel = ChujogramPanel(
                self.screen,
                [p.name for p in self.players]
            )
            # Vycentruj panel
            self._chujogram_panel.panel_x = SCREEN_WIDTH // 2 - self._chujogram_panel.panel_w // 2
            self._chujogram_panel.panel_y = 50
            self._chujogram_panel.panel_h = SCREEN_HEIGHT - 100
            self._chujogram_panel.visible = True

        panel = self._chujogram_panel
        panel.scroll_y = self.chujogram_scroll
        panel._draw_header()
        panel._draw_content(
            self.game_state.bullet_history,
            self.game_state.round_scores_history
        )

        # Border
        pygame.draw.rect(self.screen, COLOR_GOLD,
                         (panel.panel_x, panel.panel_y,
                          panel.panel_w, panel.panel_h),
                         width=2, border_radius=8)

        # Hint
        hint = self.font_medium.render("Klikni pre zavretie", True, COLOR_GRAY)
        self.screen.blit(hint, hint.get_rect(
            centerx=SCREEN_WIDTH // 2, bottom=SCREEN_HEIGHT - 20
        ))

    def _draw_info(self):
        """Nakreslí info o hre."""
        info_text = f"Hra trvala {self.round_number} kôl"
        info_surf = self.font_medium.render(info_text, True, COLOR_GRAY)
        info_rect = info_surf.get_rect(
            center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 240)  # bolo -200
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
        self._draw_btn(
            self.btn_chujogram, "Chujogram",
            COLOR_BUTTON_SECONDARY, self.hover["chujogram"]
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