# gui/game_over_screen.py

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_RED, COLOR_PANEL_BG,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS, BULLET_RADIUS, BULLET_COLOR, get_font
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

        self.font_title = get_font(76)
        self.font_large = get_font(FONT_SIZE_LARGE + 8)
        self.font_medium = get_font(FONT_SIZE_MEDIUM + 2)
        self.font_small = get_font(FONT_SIZE_MEDIUM)

        # Fonty pre širší chujogram overlay (pozri _draw_chujogram_overlay)
        self.font_chj_title = get_font(48)
        self.font_chj_header_name = get_font(30)
        self.font_chj_header_score = get_font(24)
        self.font_chj_round_no = get_font(20)
        self.font_chj_cell = get_font(26)

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        # "KRÁĽ CHUJ" meme — zobrazí sa vedľa nadpisu, keď prehral hráč
        # (nahrádza pôvodné textové "SI CHUJ! :D").
        try:
            meme_img = pygame.image.load("assets/graphics/chuj.png").convert_alpha()
            self.chuj_meme = pygame.transform.smoothscale(meme_img, (120, 120))
        except FileNotFoundError:
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
        self.panel_h = SCREEN_HEIGHT - 140
        cx = self.panel_x + self.panel_w // 2

        y = self.panel_y + 40
        self._is_human_loser = self.loser.is_human

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

        loser_text = f"{self.loser.name} prehral s {self.loser.total_score} bodmi!"
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

        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        self._draw_panel()
        self._draw_title()
        self._draw_scores()
        self._draw_info()
        self._draw_buttons()
        if self.show_chujogram:
            self._draw_chujogram_overlay()

    def _draw_panel(self):
        """Centrálny panel — rovnaký vizuálny jazyk ako SettingsScreen."""
        panel_surf = pygame.Surface((self.panel_w, self.panel_h), pygame.SRCALPHA)
        panel_surf.fill((*COLOR_PANEL_BG, 225))
        self.screen.blit(panel_surf, (self.panel_x, self.panel_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (self.panel_x, self.panel_y, self.panel_w, self.panel_h),
            width=2, border_radius=14
        )

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

            self.screen.blit(self.chuj_meme, (block_x, y))
            title_rect = self._title_surf.get_rect(
                midleft=(block_x + meme_w + gap, block_center_y)
            )
        else:
            title_rect = self._title_surf.get_rect(centerx=cx, top=y)

        self.screen.blit(self._title_surf, title_rect)

        # Meno porazeného
        self.screen.blit(
            self._loser_surf,
            self._loser_surf.get_rect(centerx=cx, top=self._loser_y)
        )

        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (self.panel_x + 60, self._divider_y),
            (self.panel_x + self.panel_w - 60, self._divider_y),
            width=2
        )

    def _draw_scores(self):
        """Nakreslí finálne skóre."""
        cx = self.panel_x + self.panel_w // 2
        self.screen.blit(
            self._score_title_surf,
            self._score_title_surf.get_rect(centerx=cx, top=self._score_title_y)
        )

        for i, player, rect in self._score_rows:
            is_loser = player == self.loser

            row_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            row_surf.fill((200, 60, 40, 80) if is_loser else (20, 12, 5, 160))
            self.screen.blit(row_surf, rect.topleft)

            border_color = COLOR_RED if is_loser else COLOR_GRAY
            pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=8)

            rank_color = COLOR_GOLD if i == 0 else COLOR_GRAY
            rank_surf = self.font_large.render(f"#{i + 1}", True, rank_color)
            self.screen.blit(
                rank_surf,
                rank_surf.get_rect(right=rect.left + 60, centery=rect.centery)
            )

            name_color = COLOR_RED if is_loser else COLOR_WHITE
            name_surf = self.font_large.render(player.name, True, name_color)
            self.screen.blit(
                name_surf,
                name_surf.get_rect(left=rect.left + 72, centery=rect.centery)
            )

            score_surf = self.font_large.render(
                str(player.total_score), True, name_color
            )
            self.screen.blit(
                score_surf,
                score_surf.get_rect(right=rect.right - 15, centery=rect.centery)
            )

    def _draw_info(self):
        """Nakreslí info o hre."""
        cx = self.panel_x + self.panel_w // 2
        self.screen.blit(
            self._info_surf, self._info_surf.get_rect(centerx=cx, top=self._info_y)
        )

    def _draw_buttons(self):
        self._draw_btn(
            self.btn_chujogram, "Chujogram",
            COLOR_BUTTON_SECONDARY, self.hover["chujogram"]
        )
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
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        dark.fill((8, 5, 2))
        self.screen.blit(dark, (0, 0))

        num_players = len(self.players)
        panel_w = min(1500, SCREEN_WIDTH - 240)
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = 60
        panel_h = SCREEN_HEIGHT - 120
        cx = panel_x + panel_w // 2

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((*COLOR_PANEL_BG, 235))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD, (panel_x, panel_y, panel_w, panel_h),
            width=2, border_radius=14
        )

        y = panel_y + 28
        title = self.font_chj_title.render("CHUJOGRAM", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(centerx=cx, top=y))
        y += title.get_height() + 26

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
            is_loser = player == self.loser
            if is_loser:
                hl = pygame.Surface((col_w - 8, header_h), pygame.SRCALPHA)
                hl.fill((200, 60, 40, 55))
                self.screen.blit(hl, (cols_x0 + i * col_w + 4, header_top))

            name_color = COLOR_RED if is_loser else COLOR_WHITE
            name_surf = self.font_chj_header_name.render(player.name, True, name_color)
            self.screen.blit(
                name_surf, name_surf.get_rect(centerx=cx_col, top=header_top + 8)
            )
            score_color = (230, 140, 120) if is_loser else COLOR_GOLD
            score_surf = self.font_chj_header_score.render(
                f"{player.total_score} b", True, score_color
            )
            self.screen.blit(
                score_surf, score_surf.get_rect(centerx=cx_col, top=header_top + 42)
            )

            if i > 0:
                pygame.draw.line(
                    self.screen, COLOR_GRAY,
                    (cols_x0 + i * col_w, header_top),
                    (cols_x0 + i * col_w, bottom_limit),
                    width=1
                )

        y = header_top + header_h + 6
        pygame.draw.line(
            self.screen, COLOR_GOLD,
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
        self.screen.set_clip(clip_rect)

        row_h = 54
        bullet_positions = []
        for round_idx in range(len(round_scores_history)):
            ry = content_top + round_idx * row_h - self.chujogram_scroll

            if ry < content_top - row_h or ry > bottom_limit:
                bullet_positions.append([None] * num_players)
                continue

            if round_idx > 0 and round_idx % 4 == 0:
                line_y = ry - 8
                pygame.draw.line(
                    self.screen, COLOR_GOLD,
                    (content_x, line_y), (panel_x + panel_w - 30, line_y),
                    width=1
                )

            round_no_surf = self.font_chj_round_no.render(
                f"{round_idx + 1}.", True, COLOR_GRAY
            )
            self.screen.blit(
                round_no_surf,
                round_no_surf.get_rect(left=content_x, centery=ry + row_h // 2 - 6)
            )

            round_positions = []
            for player_idx in range(num_players):
                cxp = cols_x0 + player_idx * col_w + col_w // 2

                score = round_scores_history[round_idx][player_idx]
                score_surf = self.font_chj_cell.render(str(score), True, COLOR_WHITE)
                self.screen.blit(score_surf, score_surf.get_rect(centerx=cxp, top=ry))

                has_bullet = (
                    bullet_history[round_idx][player_idx]
                    if round_idx < len(bullet_history)
                    and player_idx < len(bullet_history[round_idx])
                    else 0
                )
                if has_bullet:
                    by = ry + 34
                    pygame.draw.circle(self.screen, BULLET_COLOR, (cxp, by), BULLET_RADIUS)
                    pygame.draw.circle(
                        self.screen, COLOR_WHITE, (cxp, by), BULLET_RADIUS, width=1
                    )
                    round_positions.append((cxp, by))
                else:
                    round_positions.append(None)

            bullet_positions.append(round_positions)

        self._draw_bullet_connections(bullet_positions)
        self.screen.set_clip(None)

        hint = self.font_medium.render("Klikni pre zavretie", True, COLOR_GRAY)
        self.screen.blit(
            hint, hint.get_rect(centerx=cx, bottom=panel_y + panel_h - 18)
        )

    def _draw_bullet_connections(self, bullet_positions: list):
        """Spojnice medzi guličkami — rovnaká logika ako ChujogramPanel."""
        for round_idx, round_pos in enumerate(bullet_positions):
            active = [(i, pos) for i, pos in enumerate(round_pos) if pos]
            if len(active) > 1:
                for i in range(len(active) - 1):
                    pygame.draw.line(
                        self.screen, BULLET_COLOR,
                        active[i][1], active[i + 1][1], width=2
                    )
            if round_idx > 0:
                prev_active = [pos for pos in bullet_positions[round_idx - 1] if pos]
                curr_active = [pos for pos in round_pos if pos]
                if prev_active and curr_active:
                    pygame.draw.line(
                        self.screen, BULLET_COLOR,
                        prev_active[-1], curr_active[0], width=2
                    )

    def __repr__(self) -> str:
        return "GameOverScreen()"
