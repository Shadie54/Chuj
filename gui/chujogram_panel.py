# gui/chujogram_panel.py

import pygame
from gui import display, layout, ui_style
from config import (
    BULLET_RADIUS,
    NUM_PLAYERS
)

# Vzhľad (grafický rework 2026-10-28, štýl gui/ui_style.py) — spoločný aj
# pre Chujogram na obrazovke Koniec hry (gui/game_over_screen.py).
PANEL_FILL = (17, 11, 7, 255)       # nepriehľadné — ruka PC3 nepresvitá
COLUMN_LINE = (70, 54, 34)          # zvislé deliace čiary stĺpcov
QUARTER_LINE = ui_style.GOLD_SOFT   # čiara po každých 4 kolách
ROW_STRIPE = (255, 214, 140, 7)     # jemné pruhovanie riadkov (čitateľnosť)
SCORE_COLOR = ui_style.TEXT
SCORE_DANGER = (232, 112, 84)       # skóre nad 90 b — blízko prehry
DANGER_FROM = 91
BULLET_FILL = ui_style.GOLD
BULLET_RING = (90, 62, 20)
BULLET_LINE = ui_style.GOLD_SOFT


def score_color(score: int) -> tuple:
    return SCORE_DANGER if score >= DANGER_FROM else SCORE_COLOR


def draw_bullet(canvas, pos, radius: float = BULLET_RADIUS):
    canvas.circle(BULLET_FILL, pos, radius)
    canvas.circle(BULLET_RING, pos, radius, width=1)


def draw_connections(canvas, bullet_positions: list):
    """Spojnice guličiek — v rámci kola zľava doprava, medzi kolami
    posledná gulička predchádzajúceho s prvou nasledujúceho."""
    for round_idx, round_pos in enumerate(bullet_positions):
        active = [pos for pos in round_pos if pos]
        for a, b in zip(active, active[1:]):
            canvas.line(BULLET_LINE, a, b, width=2)
        if round_idx > 0:
            prev_active = [pos for pos in bullet_positions[round_idx - 1] if pos]
            if prev_active and active:
                canvas.line(BULLET_LINE, prev_active[-1], active[0], width=2)
    # Guličky ešte raz navrch — spojnice nesmú prečiarknuť ich stred.
    for round_pos in bullet_positions:
        for pos in round_pos:
            if pos:
                draw_bullet(canvas, pos)

class ChujogramPanel:
    def __init__(self, canvas, player_names: list[str]):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.player_names = player_names  # fixné poradie od začiatku hry

        self.font_small = self.canvas.font(22)  # bolo 28
        self.font_medium = self.canvas.font(28)  # bolo 36
        self.font_large = self.canvas.font(36)  # bolo 48

        # Rozmery panelu
        self.panel_w = 480
        self.panel_h = layout.game().l_h
        self.panel_y = 0

        # Animácia
        self.visible = False
        self.panel_x = -self.panel_w      # začína mimo obrazovky
        self.target_x = 0                  # cieľ = 0 (viditeľný)
        self.hidden_x = -self.panel_w      # schovaný = mimo obrazovky
        self.anim_speed = 25               # px za frame

        # Scrollovanie
        self.scroll_y = 0
        self.scroll_speed = 20

        # Layout
        self.header_h = 95
        self.col_w = (self.panel_w - 20) // NUM_PLAYERS
        self.row_h = 34  # bolo 45
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
            mouse_pos = display.mouse_pos()
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

        # Nekresli panel ak je úplne schovaný
        if self.panel_x <= self.hidden_x:
            return

        # Pozadie panelu + mäkký tieň napravo od neho + zlatohnedý okraj
        right = self.panel_x + self.panel_w
        for i, alpha in enumerate((70, 45, 25, 10)):
            self.canvas.overlay((right + i * 5, 0, 5, self.panel_h), (0, 0, 0, alpha))
        self.canvas.overlay(pygame.Rect((self.panel_x, self.panel_y),
                                        (self.panel_w, self.panel_h)), PANEL_FILL)
        self.canvas.line(ui_style.GOLD_SOFT, (right, 0), (right, self.panel_h),
                         width=2)

        # Obsah
        self._draw_header()
        self._draw_content(bullet_history, round_scores)

    def _draw_header(self):
        """Nadpis s ozdobnou linkou a mená hráčov."""
        cx = self.panel_x + self.panel_w // 2
        ui_style.draw_screen_title(self.canvas, "CHUJOGRAM", self.font_large,
                                   (cx, 26), line_half_w=150, line_gap=24)

        for i, name in enumerate(self.player_names):
            x = self.panel_x + self.content_x + i * self.col_w + self.col_w // 2
            surf = self.font_small.render(name[:10], True, ui_style.TEXT)
            self.canvas.blit(surf, surf.get_rect(centerx=x, top=62))

            # Zvislá čiara medzi stĺpcami
            if i > 0:
                lx = self.panel_x + self.content_x + i * self.col_w
                self.canvas.line(COLUMN_LINE, (lx, 60), (lx, self.panel_h - 5),
                                 width=1)

        # Čiara pod hlavičkou
        self.canvas.line(ui_style.GOLD_SOFT,
                         (self.panel_x + 8, self.header_h),
                         (self.panel_x + self.panel_w - 8, self.header_h), width=1)

    def _draw_content(self, bullet_history, round_scores):
        if not bullet_history:
            return

        # round_scores už obsahuje total_score → žiadna akumulácia
        clip_rect = pygame.Rect(
            self.panel_x, self.header_h,
            self.panel_w, self.panel_h - self.header_h
        )
        self.canvas.set_clip(clip_rect)

        bullet_positions = []

        for round_idx, round_bullets in enumerate(bullet_history):
            y = self.header_h + round_idx * self.row_h - self.scroll_y + 10

            # Jemné pruhovanie každého druhého riadku
            if round_idx % 2 == 1:
                self.canvas.overlay((self.panel_x + 6, y - 5, self.panel_w - 12,
                                     self.row_h), ROW_STRIPE)

            # Vodorovná čiara po každých 4 kolách
            if round_idx > 0 and round_idx % 4 == 0:
                line_y = y - 5
                self.canvas.line(QUARTER_LINE,
                    (self.panel_x + 5, line_y),
                    (self.panel_x + self.panel_w - 5, line_y),
                    width=1
                )

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
                        str(score), True, score_color(score)
                    )
                    score_rect = score_surf.get_rect(centerx=x, top=y)
                    self.canvas.blit(score_surf, score_rect)

                has_bullet = round_bullets[player_idx] if \
                    player_idx < len(round_bullets) else 0

                if has_bullet:
                    bullet_y = y + 30
                    draw_bullet(self.canvas, (x, bullet_y))
                    round_bullet_positions.append((x, bullet_y))
                else:
                    round_bullet_positions.append(None)

            bullet_positions.append(round_bullet_positions)

        self._draw_connections(bullet_positions)
        self.canvas.set_clip(None)

    def _draw_connections(self, bullet_positions: list):
        """Nakreslí spojnice medzi guličkami."""
        draw_connections(self.canvas, bullet_positions)

    def __repr__(self) -> str:
        return f"ChujogramPanel(visible={self.visible})"