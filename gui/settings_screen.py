# gui/settings_screen.py

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_GREEN, COLOR_YELLOW, COLOR_RED,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS
)


class SettingsScreen:
    def __init__(self, screen: pygame.Surface, settings: dict):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.settings = settings.copy()

        self.font_title = pygame.font.SysFont(None, 72)
        self.font_large = pygame.font.SysFont(None, FONT_SIZE_LARGE)
        self.font_medium = pygame.font.SysFont(None, FONT_SIZE_MEDIUM)

        # Pozadie
        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        self.difficulties = ["easy", "medium", "hard"]
        self.difficulty_labels = {
            "easy": "Ľahká",
            "medium": "Stredná",
            "hard": "Ťažká"
        }
        self.difficulty_colors = {
            "easy": COLOR_GREEN,
            "medium": COLOR_YELLOW,
            "hard": COLOR_RED
        }

        # Tlačidlá pre 3 AI hráčov
        btn_w = 160
        btn_h = 55
        center_x = SCREEN_WIDTH // 2
        spacing = 200

        self.ai_buttons = {}
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        row_start_y = SCREEN_HEIGHT // 2 - 80

        for ai_idx, (name, key) in enumerate(zip(ai_names, ai_keys)):
            row_y = row_start_y + ai_idx * 100
            buttons = []
            for i, diff in enumerate(self.difficulties):
                x = center_x - spacing + i * spacing
                buttons.append({
                    "difficulty": diff,
                    "rect": pygame.Rect(
                        x - btn_w // 2, row_y, btn_w, btn_h
                    ),
                    "hover": False,
                    "key": key
                })
            self.ai_buttons[name] = buttons

        # Tlačidlo späť
        self.back_button = {
            "rect": pygame.Rect(
                center_x - 150, SCREEN_HEIGHT - 120, 300, 60
            ),
            "hover": False
        }

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
                        result = self._handle_click(event.pos)
                        if result == "back":
                            return self.settings

            self._update_hover(mouse_pos)
            self._draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        for name, buttons in self.ai_buttons.items():
            for btn in buttons:
                if btn["rect"].collidepoint(pos):
                    self.settings[btn["key"]] = btn["difficulty"]
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
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        self._draw_title()
        self._draw_ai_sections()
        self._draw_back_button()

    def _draw_title(self):
        title = self.font_title.render("NASTAVENIA", True, COLOR_GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)

        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (SCREEN_WIDTH // 2 - 300, 160),
            (SCREEN_WIDTH // 2 + 300, 160),
            width=2
        )

    def _draw_ai_sections(self):
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        for name, key in zip(ai_names, ai_keys):
            buttons = self.ai_buttons[name]

            # Label — nad tlačidlami
            label_y = buttons[0]["rect"].top - 35
            label_surf = self.font_large.render(name, True, COLOR_WHITE)
            label_rect = label_surf.get_rect(
                center=(SCREEN_WIDTH // 2, label_y)
            )
            self.screen.blit(label_surf, label_rect)

            # Tlačidlá obtiažnosti
            current = self.settings[key]
            for btn in buttons:
                diff = btn["difficulty"]
                is_selected = (diff == current)
                base_color = self.difficulty_colors[diff]

                overlay = pygame.Surface(
                    (btn["rect"].width, btn["rect"].height),
                    pygame.SRCALPHA
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

    def _draw_back_button(self):
        rect = self.back_button["rect"]
        color = COLOR_BUTTON_PRIMARY if self.back_button["hover"] \
            else COLOR_BUTTON_SECONDARY

        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, 220))
        self.screen.blit(overlay, (rect.x, rect.y))

        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            rect, width=2, border_radius=BUTTON_RADIUS
        )

        text = self.font_large.render("← Späť", True, COLOR_WHITE)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def __repr__(self) -> str:
        return "SettingsScreen()"