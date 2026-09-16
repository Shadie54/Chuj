# gui/settings_screen.py

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_DARK_GRAY, COLOR_BLACK,
    COLOR_GREEN, COLOR_YELLOW, COLOR_RED,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    COLOR_PANEL_BG,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL,
    BUTTON_RADIUS, get_font,
    ANIMATION_SPEED_MIN, ANIMATION_SPEED_MAX, ANIMATION_SPEED_DEFAULT
)


class SettingsScreen:
    def __init__(self, screen: pygame.Surface, settings: dict):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.settings = settings.copy()
        if "animation_speed" not in self.settings:
            self.settings["animation_speed"] = ANIMATION_SPEED_DEFAULT

        self.font_title   = get_font(64)
        self.font_large   = get_font(FONT_SIZE_LARGE)
        self.font_medium  = get_font(FONT_SIZE_MEDIUM)
        self.font_small   = get_font(FONT_SIZE_SMALL)

        # Pozadie obrazovky
        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        self.difficulties = ["easy", "medium", "hard"]
        self.difficulty_labels = {
            "easy":   "Ľahká",
            "medium": "Stredná",
            "hard":   "Ťažká"
        }
        self.difficulty_colors = {
            "easy":   COLOR_GREEN,
            "medium": COLOR_YELLOW,
            "hard":   COLOR_RED
        }

        center_x = SCREEN_WIDTH // 2
        self.center_x = center_x
        self.panel_width = min(1000, SCREEN_WIDTH - 120)
        panel_x = center_x - self.panel_width // 2

        gap = 26
        content_top = 180

        # ------------------------------------------------------------
        # Panel 1 — AI obtiažnosť (popis a tlačidlá vodorovne v riadku)
        # ------------------------------------------------------------
        btn_w, btn_h = 150, 52
        btn_gap = 18
        row_side_pad = 40
        ai_top_pad = 65
        ai_row_h = 80
        ai_bottom_pad = 20
        ai_panel_h = ai_top_pad + 3 * ai_row_h + ai_bottom_pad

        self.panel_ai = pygame.Rect(panel_x, content_top, self.panel_width, ai_panel_h)

        buttons_total_w = 3 * btn_w + 2 * btn_gap
        buttons_start_x = self.panel_ai.right - row_side_pad - buttons_total_w

        self.ai_buttons = {}
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys  = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        for ai_idx, (name, key) in enumerate(zip(ai_names, ai_keys)):
            row_top = self.panel_ai.top + ai_top_pad + ai_idx * ai_row_h
            row_y = row_top + (ai_row_h - btn_h) // 2
            buttons = []
            for i, diff in enumerate(self.difficulties):
                x = buttons_start_x + i * (btn_w + btn_gap)
                buttons.append({
                    "difficulty": diff,
                    "rect": pygame.Rect(x, row_y, btn_w, btn_h),
                    "hover": False,
                    "key":   key
                })
            self.ai_buttons[name] = buttons

        self.ai_label_x = self.panel_ai.left + row_side_pad

        # ------------------------------------------------------------
        # Panel 2 — Animácie (rýchlosť, slider)
        # ------------------------------------------------------------
        anim_panel_h = 165
        self.panel_anim = pygame.Rect(
            panel_x, self.panel_ai.bottom + gap, self.panel_width, anim_panel_h
        )

        slider_pad = 80
        self.slider_rect = pygame.Rect(
            self.panel_anim.left + slider_pad,
            self.panel_anim.top + 105,
            self.panel_anim.width - slider_pad * 2,
            6
        )
        self.slider_handle_radius = 13
        self.slider_dragging = False

        # ------------------------------------------------------------
        # Panel 3 — Pozadie
        # ------------------------------------------------------------
        self.bg_options = ["table.jpg", "table1.jpg", "table2.jpg", "table3.jpg", "table4.jpg", "table5.jpg"]
        self.bg_labels  = ["Stôl", "Stôl 1", "Stôl 2", "Stôl 3", "Stôl 4", "Makita"]
        self.bg_thumbnails = {}

        thumb_w, thumb_h = 150, 88
        thumb_gap = 16
        self._load_thumbnails(thumb_w, thumb_h)

        bg_top_pad = 62
        bg_label_h = 30
        bg_bottom_pad = 14
        bg_panel_h = bg_top_pad + thumb_h + bg_label_h + bg_bottom_pad

        self.panel_bg = pygame.Rect(
            panel_x, self.panel_anim.bottom + gap, self.panel_width, bg_panel_h
        )

        total_w = len(self.bg_options) * (thumb_w + thumb_gap) - thumb_gap
        thumb_start = center_x - total_w // 2
        thumb_y = self.panel_bg.top + bg_top_pad

        self.bg_rects = []
        for i in range(len(self.bg_options)):
            x = thumb_start + i * (thumb_w + thumb_gap)
            self.bg_rects.append(pygame.Rect(x, thumb_y, thumb_w, thumb_h))

        # Tlačidlo späť
        self.back_button = {
            "rect":  pygame.Rect(center_x - 150, SCREEN_HEIGHT - 70, 300, 50),
            "hover": False
        }

    # ------------------------------------------------------------------
    # Načítanie miniatúr
    # ------------------------------------------------------------------

    def _load_thumbnails(self, thumb_w: int, thumb_h: int):
        for fname in self.bg_options:
            try:
                img = pygame.image.load(f"assets/graphics/{fname}").convert()
                self.bg_thumbnails[fname] = pygame.transform.scale(img, (thumb_w, thumb_h))
            except FileNotFoundError:
                self.bg_thumbnails[fname] = None

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> dict:
        while True:
            self.clock.tick(60)
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return self.settings

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if self._slider_hit(event.pos):
                            self.slider_dragging = True
                            self._update_slider_from_pos(event.pos[0])
                        else:
                            result = self._handle_click(event.pos)
                            if result == "back":
                                return self.settings

                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.slider_dragging = False

                if event.type == pygame.MOUSEMOTION:
                    if self.slider_dragging:
                        self._update_slider_from_pos(event.pos[0])

            self._update_hover(mouse_pos)
            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Slider — rýchlosť animácií
    # ------------------------------------------------------------------

    def _slider_hit(self, pos: tuple[int, int]) -> bool:
        """Rozšírená hit-oblasť okolo trati slidera (ľahšie sa trafí)."""
        hit_rect = self.slider_rect.inflate(20, self.slider_handle_radius * 3)
        return hit_rect.collidepoint(pos)

    def _update_slider_from_pos(self, mouse_x: int):
        frac = (mouse_x - self.slider_rect.left) / self.slider_rect.width
        frac = max(0.0, min(1.0, frac))
        value = ANIMATION_SPEED_MIN + frac * (ANIMATION_SPEED_MAX - ANIMATION_SPEED_MIN)
        self.settings["animation_speed"] = round(value, 2)

    def _slider_handle_pos(self) -> tuple[int, int]:
        value = self.settings.get("animation_speed", ANIMATION_SPEED_DEFAULT)
        frac = (value - ANIMATION_SPEED_MIN) / (ANIMATION_SPEED_MAX - ANIMATION_SPEED_MIN)
        frac = max(0.0, min(1.0, frac))
        x = self.slider_rect.left + int(frac * self.slider_rect.width)
        y = self.slider_rect.centery
        return x, y

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        for name, buttons in self.ai_buttons.items():
            for btn in buttons:
                if btn["rect"].collidepoint(pos):
                    self.settings[btn["key"]] = btn["difficulty"]
                    return None

        for i, (fname, rect) in enumerate(zip(self.bg_options, self.bg_rects)):
            if rect.collidepoint(pos):
                self.settings["table_bg"] = fname
                return None

        if self.back_button["rect"].collidepoint(pos):
            return "back"

        return None

    def _update_hover(self, mouse_pos: tuple[int, int]):
        for buttons in self.ai_buttons.values():
            for btn in buttons:
                btn["hover"] = btn["rect"].collidepoint(mouse_pos)
        self.back_button["hover"] = self.back_button["rect"].collidepoint(
            mouse_pos
        )

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        self._draw_title()

        self._draw_panel(self.panel_ai, "OBTIAŽNOSŤ POČÍTAČOV")
        self._draw_ai_sections()

        self._draw_panel(self.panel_anim, "RÝCHLOSŤ ANIMÁCIÍ")
        self._draw_speed_slider()

        self._draw_panel(self.panel_bg, "POZADIE STOLA")
        self._draw_bg_section()

        self._draw_back_button()

    def _draw_title(self):
        title = self.font_title.render("NASTAVENIA", True, COLOR_GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 95))
        self.screen.blit(title, title_rect)

        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (SCREEN_WIDTH // 2 - 260, 135),
            (SCREEN_WIDTH // 2 + 260, 135),
            width=2
        )

    def _draw_panel(self, rect: pygame.Rect, title: str):
        """Nakreslí zaoblený panel s tmavým pozadím, zlatým okrajom a nadpisom."""
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        panel_surf.fill((*COLOR_PANEL_BG, 210))
        self.screen.blit(panel_surf, (rect.x, rect.y))
        pygame.draw.rect(self.screen, COLOR_GOLD, rect, width=2, border_radius=14)

        label = self.font_medium.render(title, True, COLOR_GOLD)
        label_rect = label.get_rect(midleft=(rect.left + 28, rect.top + 30))
        self.screen.blit(label, label_rect)

        pygame.draw.line(
            self.screen, COLOR_DARK_GRAY,
            (rect.left + 24, rect.top + 52),
            (rect.right - 24, rect.top + 52),
            width=1
        )

    def _draw_ai_sections(self):
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys  = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        for row_idx, (name, key) in enumerate(zip(ai_names, ai_keys)):
            buttons = self.ai_buttons[name]
            row_centery = buttons[0]["rect"].centery

            label_surf = self.font_medium.render(name, True, COLOR_WHITE)
            label_rect = label_surf.get_rect(midleft=(self.ai_label_x, row_centery))
            self.screen.blit(label_surf, label_rect)

            if row_idx > 0:
                divider_y = buttons[0]["rect"].top - 14
                pygame.draw.line(
                    self.screen, COLOR_DARK_GRAY,
                    (self.panel_ai.left + 24, divider_y),
                    (self.panel_ai.right - 24, divider_y),
                    width=1
                )

            current = self.settings[key]
            for btn in buttons:
                diff        = btn["difficulty"]
                is_selected = (diff == current)
                base_color  = self.difficulty_colors[diff]

                overlay = pygame.Surface(
                    (btn["rect"].width, btn["rect"].height), pygame.SRCALPHA
                )
                if is_selected:
                    overlay.fill((*base_color, 230))
                elif btn["hover"]:
                    overlay.fill((*base_color, 120))
                else:
                    overlay.fill((40, 25, 10, 180))
                self.screen.blit(overlay, (btn["rect"].x, btn["rect"].y))

                border_color = base_color if is_selected or btn["hover"] \
                    else COLOR_GRAY
                border_width = 3 if is_selected else 1
                pygame.draw.rect(
                    self.screen, border_color,
                    btn["rect"], width=border_width,
                    border_radius=BUTTON_RADIUS
                )

                text_color = (0, 0, 0) if is_selected else COLOR_WHITE
                text = self.font_medium.render(
                    self.difficulty_labels[diff], True, text_color
                )
                text_rect = text.get_rect(center=btn["rect"].center)
                self.screen.blit(text, text_rect)

    def _draw_speed_slider(self):
        track = self.slider_rect

        # Popisky nad traťou
        lbl_slow = self.font_small.render("Pomalšie", True, COLOR_GRAY)
        lbl_fast = self.font_small.render("Rýchlejšie", True, COLOR_GRAY)
        self.screen.blit(lbl_slow, (track.left, track.top - 28))
        lbl_fast_rect = lbl_fast.get_rect(topright=(track.right, track.top - 28))
        self.screen.blit(lbl_fast, lbl_fast_rect)

        # Trať (nevyplnená)
        pygame.draw.line(
            self.screen, COLOR_DARK_GRAY,
            (track.left, track.centery), (track.right, track.centery),
            width=6
        )

        handle_x, handle_y = self._slider_handle_pos()

        # Trať (vyplnená časť po handle)
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (track.left, track.centery), (handle_x, handle_y),
            width=6
        )

        handle_color = COLOR_YELLOW if self.slider_dragging else COLOR_GOLD
        pygame.draw.circle(self.screen, handle_color, (handle_x, handle_y), self.slider_handle_radius)
        pygame.draw.circle(self.screen, COLOR_BLACK, (handle_x, handle_y), self.slider_handle_radius, width=2)

        value = self.settings.get("animation_speed", ANIMATION_SPEED_DEFAULT)
        value_text = self.font_medium.render(f"{value:.1f}×", True, COLOR_WHITE)
        value_rect = value_text.get_rect(midtop=(self.center_x, track.bottom + 16))
        self.screen.blit(value_text, value_rect)

    def _draw_bg_section(self):
        current = self.settings.get("table_bg", "table.jpg")

        for i, (fname, rect) in enumerate(zip(self.bg_options, self.bg_rects)):
            is_selected = (fname == current)
            is_hover    = rect.collidepoint(pygame.mouse.get_pos())

            thumb = self.bg_thumbnails.get(fname)
            if thumb:
                self.screen.blit(thumb, rect)
            else:
                fallback = pygame.Surface((rect.w, rect.h))
                fallback.fill((40, 25, 10))
                self.screen.blit(fallback, rect)

            border_color = COLOR_GOLD if is_selected else (
                COLOR_WHITE if is_hover else COLOR_GRAY
            )
            border_width = 3 if is_selected else 1
            pygame.draw.rect(
                self.screen, border_color, rect,
                width=border_width, border_radius=6
            )

            lbl      = self.font_small.render(
                self.bg_labels[i], True,
                COLOR_GOLD if is_selected else COLOR_WHITE
            )
            lbl_rect = lbl.get_rect(
                centerx=rect.centerx, top=rect.bottom + 6
            )
            self.screen.blit(lbl, lbl_rect)

    def _draw_back_button(self):
        rect  = self.back_button["rect"]
        color = COLOR_BUTTON_PRIMARY if self.back_button["hover"] \
            else COLOR_BUTTON_SECONDARY

        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, 220))
        self.screen.blit(overlay, (rect.x, rect.y))

        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            rect, width=2, border_radius=BUTTON_RADIUS
        )

        text      = self.font_large.render("← Späť", True, COLOR_WHITE)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def __repr__(self) -> str:
        return "SettingsScreen()"
