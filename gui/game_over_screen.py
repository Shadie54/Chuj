# gui/game_over_screen.py
#
# Od reworku rozlíšení (krok 4) kreslí cez gui/canvas.py v natívnom
# rozlíšení; pozadie stola so stmavením je statická vrstva.

import os
import pygame
import sys
from gui import display
from gui.canvas import StaticLayer
from gui import ui_style
from gui import chujogram_panel as cg
from config import (
    SCREEN_WIDTH,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_RED,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
)


class GameOverScreen:
    def __init__(self, screen: pygame.Surface, players: list,
                 losers: list, round_number: int, game_state=None):
        """
        players: zoznam všetkých hráčov
        losers: porazení hráči (najviac bodov nad 100; pri remíze na
            vrchole viacerí — pozri GameState.losers)
        round_number: počet odohraných kôl
        """
        # `screen` (logický povrch) sa nepoužíva — kreslí sa cez Canvas.
        self.screen = screen
        self.canvas = display.canvas()
        self._layer: StaticLayer | None = None
        self.players = players
        self.losers = losers
        self.round_number = round_number
        self.game_state = game_state
        self.show_chujogram = False
        self.clock = pygame.time.Clock()

        self.font_title = self.canvas.font(76)
        self.font_large = self.canvas.font(FONT_SIZE_LARGE + 8)
        self.font_medium = self.canvas.font(FONT_SIZE_MEDIUM + 2)
        self.font_small = self.canvas.font(FONT_SIZE_MEDIUM)

        # Fonty pre širší chujogram overlay (pozri _draw_chujogram_overlay)
        self.font_chj_title = self.canvas.font(48)
        self.font_chj_header_name = self.canvas.font(30)
        self.font_chj_header_score = self.canvas.font(24)
        self.font_chj_round_no = self.canvas.font(20)
        self.font_chj_cell = self.canvas.font(26)


        # "KRÁĽ CHUJ" meme — zobrazí sa vedľa nadpisu, keď prehral hráč
        # (nahrádza pôvodné textové "SI CHUJ! :D").
        try:
            self.chuj_meme = self.canvas.image(
                os.path.join("assets", "graphics", "chuj.png"), (120, 120))
        except (FileNotFoundError, pygame.error):
            self.chuj_meme = None

        self.hover = {"new_game": False, "menu": False, "chujogram": False}
        self.chujogram_scroll = 0

        # Panel a tlačidlá sa počítajú v _layout() — zavolané aj tu, nech
        # má aj úplne prvý frame (spracovanie udalostí prebieha PRED prvým
        # _draw()) platné súradnice tlačidiel.
        self._layout()

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = display.mouse_pos()

            for event in display.get_events():
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
            display.present()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _layout(self):
        """
        Prepočíta celý layout naraz — panel, titulok (jeho výška sa líši:
        "SI CHUJ" + meme vs. "VÍŤAZSTVO!" samotný text), riadky skóre,
        info text aj tlačidlá. Volá sa v __init__ aj na začiatku _draw(),
        aby tlačidlá vždy sedeli presne s tým, čo sa vykreslí — inak by
        klik mohol trafiť vedľa, keby sa niekedy zmenil obsah nad nimi.
        """
        self.panel_w = min(1000, SCREEN_WIDTH - 200)
        self.panel_x = SCREEN_WIDTH // 2 - self.panel_w // 2
        self.panel_y = 70
        self.panel_h = display.logical_height() - 140
        cx = self.panel_x + self.panel_w // 2

        y = self.panel_y + 40
        self._is_human_loser = any(p.is_human for p in self.losers)

        if self._is_human_loser:
            self._title_surf = self.font_title.render("SI CHUJ", True, COLOR_RED)
            block_h = max(
                120 if self.chuj_meme else 0, self._title_surf.get_height()
            )
        else:
            self._title_surf = self.font_title.render("VÍŤAZSTVO!", True, COLOR_GOLD)
            block_h = self._title_surf.get_height()

        self._title_block_top = y
        self._title_block_h = block_h
        y += block_h + 24

        # Pri remíze na vrchole (viacerí losers s rovnakým skóre) sa mená
        # spoja a sloveso prejde do množného čísla.
        loser_names = " a ".join(p.name for p in self.losers)
        loser_verb = "prehral" if len(self.losers) == 1 else "prehrali"
        loser_text = (
            f"{loser_names} {loser_verb} s {self.losers[0].total_score} bodmi!"
        )
        self._loser_surf = self.font_large.render(loser_text, True, COLOR_WHITE)
        self._loser_y = y
        y += self._loser_surf.get_height() + 22

        self._divider_y = y
        y += 34

        self._score_title_surf = self.font_medium.render(
            "FINÁLNE SKÓRE", True, COLOR_GOLD
        )
        self._score_title_y = y
        y += self._score_title_surf.get_height() + 22

        sorted_players = sorted(self.players, key=lambda p: p.total_score)
        row_w = self.panel_w - 120
        row_h = 58
        row_gap = 14
        row_x = cx - row_w // 2

        self._score_rows = []
        for i, player in enumerate(sorted_players):
            self._score_rows.append(
                (i, player, pygame.Rect(row_x, y, row_w, row_h))
            )
            y += row_h + row_gap

        y += 6
        self._info_surf = self.font_small.render(
            f"Hra trvala {self.round_number} kôl", True, COLOR_GRAY
        )
        self._info_y = y
        y += self._info_surf.get_height() + 30

        gap_top = y
        btn_h = 60
        btn_bottom = self.panel_y + self.panel_h - 36
        btn_y_main = btn_bottom - btn_h

        r_new_w, r_menu_w = 260, 220
        row_w_btn = r_new_w + r_menu_w + 24
        row_x_btn = cx - row_w_btn // 2
        self.btn_new_game = pygame.Rect(row_x_btn, btn_y_main, r_new_w, btn_h)
        self.btn_menu = pygame.Rect(
            self.btn_new_game.right + 24, btn_y_main, r_menu_w, btn_h
        )

        # Chujogram — vlastná veľkosť ako Nová hra/Menu, ale samostatne
        # vycentrovaný vo voľnom priestore nad nimi. Zámerne oddelené:
        # Nová hra/Menu rozhodujú o ďalšom kroku, Chujogram len ukazuje
        # priebeh hry ešte raz.
        chujogram_w = 220
        btn_y_chujogram = gap_top + max(0, (btn_y_main - gap_top) // 2 - btn_h // 2)
        self.btn_chujogram = pygame.Rect(
            cx - chujogram_w // 2, btn_y_chujogram, chujogram_w, btn_h
        )

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        self._layout()
        c = self.canvas
        if self._layer is None:
            self._layer = StaticLayer(c.target.get_size())
        if self._layer.needs_redraw("static"):
            with self._layer.drawing(c, key="static"):
                # Vzhľad: gui/ui_style.py (grafický rework 2026-10-27).
                ui_style.draw_backdrop(c)
        self._layer.blit_to(c.target)

        self._draw_panel()
        self._draw_title()
        self._draw_scores()
        self._draw_info()
        self._draw_buttons()
        if self.show_chujogram:
            self._draw_chujogram_overlay()

    def _draw_panel(self):
        """Centrálny panel — spoločný štýl obrazoviek mimo hry."""
        ui_style.draw_panel(
            self.canvas, (self.panel_x, self.panel_y, self.panel_w, self.panel_h))

    def _draw_title(self):
        """Nakreslí nadpis — pri prehre hráča "SI CHUJ" + meme vedľa seba."""
        cx = self.panel_x + self.panel_w // 2
        y = self._title_block_top

        if self._is_human_loser and self.chuj_meme:
            meme_w, meme_h = self.chuj_meme.get_size()
            gap = 24
            total_w = meme_w + gap + self._title_surf.get_width()
            block_x = cx - total_w // 2
            block_center_y = y + self._title_block_h // 2

            self.canvas.blit(self.chuj_meme, (block_x, y))
            title_rect = self._title_surf.get_rect(
                midleft=(block_x + meme_w + gap, block_center_y)
            )
        else:
            title_rect = self._title_surf.get_rect(centerx=cx, top=y)

        self.canvas.blit(self._title_surf, title_rect)

        # Meno porazeného
        self.canvas.blit(
            self._loser_surf,
            self._loser_surf.get_rect(centerx=cx, top=self._loser_y)
        )

        self.canvas.line(ui_style.GOLD_SOFT,
            (self.panel_x + 60, self._divider_y),
            (self.panel_x + self.panel_w - 60, self._divider_y),
            width=2
        )

    def _draw_scores(self):
        """Nakreslí finálne skóre."""
        cx = self.panel_x + self.panel_w // 2
        self.canvas.blit(
            self._score_title_surf,
            self._score_title_surf.get_rect(centerx=cx, top=self._score_title_y)
        )

        for i, player, rect in self._score_rows:
            is_loser = player in self.losers

            self.canvas.overlay(
                rect, (200, 60, 40, 80) if is_loser else (30, 20, 12, 200),
                border_radius=8)

            border_color = COLOR_RED if is_loser else (98, 76, 46)
            self.canvas.rect(border_color, rect, width=2, border_radius=8)

            # Miesto podľa reálneho skóre, nie podľa pozície v zoradenom
            # zozname — pri remíze (rovnaké skóre) tak dvaja hráči dostanú
            # rovnaké číslo miesta, rovnaký princíp ako GameRecord.placement
            # (game/profile.py). Bez tohto by `enumerate` pri remíze
            # prideľoval #3 a #4 ľubovoľne podľa poradia hráčov.
            rank = 1 + sum(
                1 for p in self.players if p.total_score < player.total_score
            )
            rank_color = COLOR_GOLD if rank == 1 else COLOR_GRAY
            rank_surf = self.font_large.render(f"#{rank}", True, rank_color)
            self.canvas.blit(
                rank_surf,
                rank_surf.get_rect(right=rect.left + 60, centery=rect.centery)
            )

            name_color = COLOR_RED if is_loser else COLOR_WHITE
            name_surf = self.font_large.render(player.name, True, name_color)
            self.canvas.blit(
                name_surf,
                name_surf.get_rect(left=rect.left + 72, centery=rect.centery)
            )

            score_surf = self.font_large.render(
                str(player.total_score), True, name_color
            )
            self.canvas.blit(
                score_surf,
                score_surf.get_rect(right=rect.right - 15, centery=rect.centery)
            )

    def _draw_info(self):
        """Nakreslí info o hre."""
        cx = self.panel_x + self.panel_w // 2
        self.canvas.blit(
            self._info_surf, self._info_surf.get_rect(centerx=cx, top=self._info_y)
        )

    def _draw_buttons(self):
        self._draw_btn(self.btn_chujogram, "Chujogram", 2,
                       self.hover["chujogram"])
        self._draw_btn(self.btn_new_game, "Nová hra", 1,
                       self.hover["new_game"])
        self._draw_btn(self.btn_menu, "Menu", 3, self.hover["menu"])

    def _draw_btn(self, rect: pygame.Rect, text: str, tier: int, hover: bool):
        ui_style.draw_button(self.canvas, rect, text, self.font_large,
                             tier, hover)

    # ------------------------------------------------------------------
    # Chujogram overlay — širší layout naprieč celou obrazovkou
    # ------------------------------------------------------------------

    def _draw_chujogram_overlay(self):
        """
        Vlastné (nie ChujogramPanel) vykreslenie — ChujogramPanel má natvrdo
        panel_w=480, navrhnutých pre bočný vysúvací panel počas hry
        (gui/screen.py). Tu, ako samostatná obrazovka, má chujogram celú
        šírku k dispozícii, tak ju aj využije: väčšie fonty, hlavička so
        skóre hráča priamo v stĺpci, zvýraznený stĺpec porazeného.

        Pozadie je zámerne plne nepriehľadné (predtým malo alfa 240/255 a
        cez neho bolo slabo vidno text spod — skóre, tlačidlá).
        """
        # Pozadie stola (ako ostatné obrazovky) — obsah Konca hry pod
        # Chujogramom sa nekreslí, takže nemá čo presvitať.
        ui_style.draw_backdrop(self.canvas, extra_dim=60)

        num_players = len(self.players)
        panel_w = min(1500, SCREEN_WIDTH - 240)
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = 60
        panel_h = display.logical_height() - 120
        cx = panel_x + panel_w // 2

        self.canvas.overlay((panel_x, panel_y, panel_w, panel_h), (17, 11, 7, 255),
                            border_radius=ui_style.PANEL_RADIUS)
        ui_style.draw_panel(self.canvas, (panel_x, panel_y, panel_w, panel_h))

        y = panel_y + 28
        title_h = self.font_chj_title.get_height()
        ui_style.draw_screen_title(self.canvas, "CHUJOGRAM", self.font_chj_title,
                                   (cx, y + title_h // 2),
                                   line_half_w=240, line_gap=title_h // 2 + 10)
        y += title_h + 34

        round_col_w = 90
        content_x = panel_x + 30
        cols_w = panel_w - 60 - round_col_w
        col_w = cols_w // num_players
        cols_x0 = content_x + round_col_w
        bottom_limit = panel_y + panel_h - 70   # necháva miesto na hint dole

        header_top = y
        header_h = 84
        for i, player in enumerate(self.players):
            cx_col = cols_x0 + i * col_w + col_w // 2
            is_loser = player in self.losers
            if is_loser:
                self.canvas.overlay((cols_x0 + i * col_w + 4, header_top,
                                     col_w - 8, header_h), (200, 60, 40, 55))

            name_color = cg.SCORE_DANGER if is_loser else ui_style.TEXT
            name_surf = self.font_chj_header_name.render(player.name, True, name_color)
            self.canvas.blit(
                name_surf, name_surf.get_rect(centerx=cx_col, top=header_top + 8)
            )
            score_color = (230, 140, 120) if is_loser else ui_style.GOLD
            score_surf = self.font_chj_header_score.render(
                f"{player.total_score} b", True, score_color
            )
            self.canvas.blit(
                score_surf, score_surf.get_rect(centerx=cx_col, top=header_top + 42)
            )

            if i > 0:
                self.canvas.line(cg.COLUMN_LINE,
                    (cols_x0 + i * col_w, header_top),
                    (cols_x0 + i * col_w, bottom_limit),
                    width=1
                )

        y = header_top + header_h + 6
        self.canvas.line(ui_style.GOLD_SOFT,
            (content_x, y), (panel_x + panel_w - 30, y), width=2
        )
        content_top = y + 20

        bullet_history = self.game_state.bullet_history if self.game_state else []
        round_scores_history = (
            self.game_state.round_scores_history if self.game_state else []
        )

        clip_rect = pygame.Rect(
            panel_x, content_top, panel_w, bottom_limit - content_top
        )
        self.canvas.set_clip(clip_rect)

        row_h = 54
        bullet_positions = []
        for round_idx in range(len(round_scores_history)):
            ry = content_top + round_idx * row_h - self.chujogram_scroll

            if ry < content_top - row_h or ry > bottom_limit:
                bullet_positions.append([None] * num_players)
                continue

            if round_idx % 2 == 1:
                self.canvas.overlay((content_x - 10, ry - 8,
                                     panel_w - 40, row_h), cg.ROW_STRIPE)
            if round_idx > 0 and round_idx % 4 == 0:
                line_y = ry - 8
                self.canvas.line(cg.QUARTER_LINE,
                    (content_x, line_y), (panel_x + panel_w - 30, line_y),
                    width=1
                )

            round_no_surf = self.font_chj_round_no.render(
                f"{round_idx + 1}.", True, ui_style.TEXT_DIM
            )
            self.canvas.blit(
                round_no_surf,
                round_no_surf.get_rect(left=content_x, centery=ry + row_h // 2 - 6)
            )

            round_positions = []
            for player_idx in range(num_players):
                cxp = cols_x0 + player_idx * col_w + col_w // 2

                score = round_scores_history[round_idx][player_idx]
                score_surf = self.font_chj_cell.render(str(score), True,
                                                       cg.score_color(score))
                self.canvas.blit(score_surf, score_surf.get_rect(centerx=cxp, top=ry))

                has_bullet = (
                    bullet_history[round_idx][player_idx]
                    if round_idx < len(bullet_history)
                    and player_idx < len(bullet_history[round_idx])
                    else 0
                )
                if has_bullet:
                    by = ry + 34
                    cg.draw_bullet(self.canvas, (cxp, by))
                    round_positions.append((cxp, by))
                else:
                    round_positions.append(None)

            bullet_positions.append(round_positions)

        self._draw_bullet_connections(bullet_positions)
        self.canvas.set_clip(None)

        hint = self.font_medium.render("Klikni pre zavretie", True, ui_style.TEXT_DIM)
        self.canvas.blit(
            hint, hint.get_rect(centerx=cx, bottom=panel_y + panel_h - 18)
        )

    def _draw_bullet_connections(self, bullet_positions: list):
        """Spojnice medzi guličkami — rovnaká logika ako ChujogramPanel."""
        cg.draw_connections(self.canvas, bullet_positions)

    def __repr__(self) -> str:
        return "GameOverScreen()"
