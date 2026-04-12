# gui/chujogram_panel.py

import pygame
from config import (
    SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GRAY, COLOR_GOLD,
    BULLET_RADIUS, BULLET_COLOR,
    NUM_PLAYERS
)


class ChujogramPanel:
    def __init__(self, screen: pygame.Surface, player_names: list[str]):
        self.screen = screen
        self.player_names = player_names  # fixné poradie od začiatku hry

        self.font_small = pygame.font.SysFont(None, 28)
        self.font_medium = pygame.font.SysFont(None, 36)
        self.font_large = pygame.font.SysFont(None, 48)

        # Rozmery panelu
        self.panel_w = 480
        self.panel_h = SCREEN_HEIGHT
        self.panel_y = 0

        # Animácia
        self.visible = False
        self.panel_x = -self.panel_w      # začína mimo obrazovky
        self.target_x = 0                  # cieľ = 0 (viditeľný)
        self.hidden_x = -self.panel_w      # schovaný = mimo obrazovky
        self.anim_speed = 25               # px za frame

        # Tlačidlo CH
        self.btn_w = 40
        self.btn_h = 180
        self.btn_x = 0                     # bude sa meniť s panelom
        self.btn_y = SCREEN_HEIGHT - self.btn_h - 20

        # Scrollovanie
        self.scroll_y = 0
        self.scroll_speed = 20

        # Layout
        self.header_h = 80
        self.col_w = (self.panel_w - 20) // NUM_PLAYERS
        self.row_h = 45
        self.content_x = 10

    # ------------------------------------------------------------------
    # Zobrazenie / skrytie
    # ------------------------------------------------------------------

    def toggle(self):
        """Prepne viditeľnosť panelu."""
        self.visible = not self.visible

    # ------------------------------------------------------------------
    # Aktualizácia animácie
    # ------------------------------------------------------------------

    def update(self):
        """Aktualizuje pozíciu panelu (animácia)."""
        target = self.target_x if self.visible else self.hidden_x

        if self.panel_x < target:
            self.panel_x = min(self.panel_x + self.anim_speed, target)
        elif self.panel_x > target:
            self.panel_x = max(self.panel_x - self.anim_speed, target)

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Spracuje udalosť.
        Vracia True ak panel zachytil event.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            btn_rect = self._btn_rect()
            if btn_rect.collidepoint(event.pos):
                self.toggle()
                return True

            # Klik na panel — zachyť
            panel_rect = pygame.Rect(
                self.panel_x, self.panel_y,
                self.panel_w, self.panel_h
            )
            if panel_rect.collidepoint(event.pos) and self.visible:
                return True

        # Scrollovanie
        if event.type == pygame.MOUSEWHEEL:
            panel_rect = pygame.Rect(
                self.panel_x, self.panel_y,
                self.panel_w, self.panel_h
            )
            mouse_pos = pygame.mouse.get_pos()
            if panel_rect.collidepoint(mouse_pos):
                self.scroll_y = max(
                    0, self.scroll_y - event.y * self.scroll_speed
                )
                return True

        return False

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, bullet_history: list[list[int]],
             round_scores: list[list[int]]):
        """
        Nakreslí panel.
        bullet_history: [[0,1,0,0], ...] pre každé kolo
        round_scores: [[0,5,3,12], ...] body každého hráča v kole
        """
        self.update()

        # Tlačidlo — vždy viditeľné
        self._draw_btn()

        # Nekresli panel ak je úplne schovaný
        if self.panel_x <= self.hidden_x:
            return

        # Pozadie panelu
        panel_surf = pygame.Surface(
            (self.panel_w, self.panel_h), pygame.SRCALPHA
        )
        panel_surf.fill((15, 8, 3, 235))
        self.screen.blit(panel_surf, (self.panel_x, self.panel_y))

        # Pravý okraj
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (self.panel_x + self.panel_w, 0),
            (self.panel_x + self.panel_w, self.panel_h),
            width=2
        )

        # Obsah
        self._draw_header()
        self._draw_content(bullet_history, round_scores)

    def _draw_header(self):
        """Nakreslí hlavičku s menami hráčov."""
        # Nadpis
        title = self.font_large.render("CHUJOGRAM", True, COLOR_GOLD)
        title_rect = title.get_rect(
            centerx=self.panel_x + self.panel_w // 2,
            top=10
        )
        self.screen.blit(title, title_rect)

        # Oddeľovacia čiara
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (self.panel_x + 5, 40),
            (self.panel_x + self.panel_w - 5, 40),
            width=1
        )

        # Mená hráčov — skrátené
        for i, name in enumerate(self.player_names):
            x = self.panel_x + self.content_x + i * self.col_w + self.col_w // 2
            short_name = name[:10]
            surf = self.font_small.render(short_name, True, COLOR_WHITE)
            rect = surf.get_rect(centerx=x, top=45)
            self.screen.blit(surf, rect)

            # Vertikálna čiara medzi stĺpcami
            if i > 0:
                pygame.draw.line(
                    self.screen, COLOR_GRAY,
                    (self.panel_x + self.content_x + i * self.col_w, 42),
                    (self.panel_x + self.content_x + i * self.col_w,
                     self.panel_h - 5),
                    width=1
                )

        # Čiara pod hlavičkou
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (self.panel_x + 5, self.header_h),
            (self.panel_x + self.panel_w - 5, self.header_h),
            width=1
        )

    def _draw_content(self, bullet_history, round_scores):
        if not bullet_history:
            return

        # round_scores už obsahuje total_score → žiadna akumulácia
        clip_rect = pygame.Rect(
            self.panel_x, self.header_h,
            self.panel_w, self.panel_h - self.header_h
        )
        self.screen.set_clip(clip_rect)

        bullet_positions = []

        for round_idx, round_bullets in enumerate(bullet_history):
            y = self.header_h + round_idx * self.row_h - self.scroll_y + 10

            if y < self.header_h - self.row_h:
                bullet_positions.append([None] * NUM_PLAYERS)
                continue
            if y > self.panel_h:
                bullet_positions.append([None] * NUM_PLAYERS)
                continue

            round_bullet_positions = []

            for player_idx in range(NUM_PLAYERS):
                x = self.panel_x + self.content_x + \
                    player_idx * self.col_w + self.col_w // 2

                # Priamo total_score ← žiadna akumulácia
                if round_idx < len(round_scores):
                    score = round_scores[round_idx][player_idx]
                    score_surf = self.font_small.render(
                        str(score), True, COLOR_WHITE
                    )
                    score_rect = score_surf.get_rect(centerx=x, top=y)
                    self.screen.blit(score_surf, score_rect)

                has_bullet = round_bullets[player_idx] if \
                    player_idx < len(round_bullets) else 0

                if has_bullet:
                    bullet_y = y + 20
                    pygame.draw.circle(
                        self.screen, BULLET_COLOR,
                        (x, bullet_y), BULLET_RADIUS
                    )
                    pygame.draw.circle(
                        self.screen, COLOR_WHITE,
                        (x, bullet_y), BULLET_RADIUS, width=1
                    )
                    round_bullet_positions.append((x, bullet_y))
                else:
                    round_bullet_positions.append(None)

            bullet_positions.append(round_bullet_positions)

        self._draw_connections(bullet_positions)
        self.screen.set_clip(None)

    def _draw_connections(self, bullet_positions: list):
        """Nakreslí spojnice medzi guličkami."""
        for round_idx, round_pos in enumerate(bullet_positions):
            active = [(i, pos) for i, pos in enumerate(round_pos) if pos]

            # Horizontálne spojnice v rovnakom kole
            if len(active) > 1:
                for i in range(len(active) - 1):
                    pygame.draw.line(
                        self.screen, BULLET_COLOR,
                        active[i][1], active[i + 1][1],
                        width=2
                    )

            # Diagonálne/vertikálne spojnice s predchádzajúcim kolom
            if round_idx > 0:
                prev_round = bullet_positions[round_idx - 1]
                prev_active = [pos for pos in prev_round if pos]
                curr_active = [pos for pos in round_pos if pos]

                if prev_active and curr_active:
                    # Spoj poslednú guličku predchádzajúceho kola
                    # s prvou guličkou aktuálneho kola
                    pygame.draw.line(
                        self.screen, BULLET_COLOR,
                        prev_active[-1], curr_active[0],
                        width=2
                    )

    def _draw_btn(self):
        """Nakreslí tlačidlo CHUJOGRAM."""
        btn_rect = self._btn_rect()

        # Pozadie
        btn_surf = pygame.Surface(
            (self.btn_w, self.btn_h), pygame.SRCALPHA
        )
        btn_surf.fill((15, 8, 3, 220))
        self.screen.blit(btn_surf, (btn_rect.x, btn_rect.y))

        # Okraj
        color = COLOR_GOLD if self.visible else COLOR_GRAY
        pygame.draw.rect(
            self.screen, color,
            btn_rect, width=2,
            border_radius=5
        )

        # Text vertikálne — CHUJOGRAM
        for i, char in enumerate("CHUJOGRAM"):
            surf = self.font_small.render(char, True, COLOR_GOLD)
            rect = surf.get_rect(
                centerx=btn_rect.centerx,
                top=btn_rect.top + 8 + i * 18
            )
            self.screen.blit(surf, rect)

    def _btn_rect(self) -> pygame.Rect:
        from config import BUTTON_SORT_X, BUTTON_SORT_Y, BUTTON_SORT_WIDTH
        return pygame.Rect(
            BUTTON_SORT_X + BUTTON_SORT_WIDTH + 20,
            BUTTON_SORT_Y,
            40,  # ← pevná úzka šírka namiesto BUTTON_SORT_WIDTH
            self.btn_h
        )

    def __repr__(self) -> str:
        return f"ChujogramPanel(visible={self.visible})"