# gui/menu.py

import pygame
import sys
import random
import os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    BUTTON_RADIUS,
    CARDS_MEDIUM_PATH, CARD_SIZE_MEDIUM,
    SUITS, RANKS
)


class Menu:
    def __init__(self, screen: pygame.Surface, show_continue: bool = False):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.show_continue = show_continue

        self.font_button = pygame.font.SysFont(None, FONT_SIZE_LARGE)
        self.font_medium = pygame.font.SysFont(None, FONT_SIZE_MEDIUM)

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        try:
            self.logo = pygame.image.load("assets/graphics/icon.png").convert_alpha()
            self.logo = pygame.transform.scale(self.logo, (280, 280))
        except FileNotFoundError:
            self.logo = None

        self.bg_cards = self._generate_bg_cards()

        btn_w = 300
        btn_h = 65
        center_x = SCREEN_WIDTH // 2

        buttons_data = []
        if show_continue:
            buttons_data.append(("Pokračovať", "continue", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Nová hra", "new_game", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Nastavenia", "settings", COLOR_BUTTON_SECONDARY))
        buttons_data.append(("Koniec", "quit", COLOR_BUTTON_SECONDARY))

        start_y = 320

        self.buttons = []
        for i, (label, action, color) in enumerate(buttons_data):
            self.buttons.append({
                "label": label,
                "action": action,
                "rect": pygame.Rect(
                    center_x - btn_w // 2,
                    start_y + i * 85,
                    btn_w, btn_h
                ),
                "color": color,
                "hover": False
            })

    def _generate_bg_cards(self) -> list[dict]:
        """Vygeneruje náhodné karty pre pozadie."""
        cards = []
        used_positions = []
        card_names = [
            f"{suit}-{rank}.png"
            for suit in SUITS for rank in RANKS
        ]
        selected = random.sample(card_names, 12)

        for filename in selected:
            path = os.path.join(CARDS_MEDIUM_PATH, filename)
            try:
                img = pygame.image.load(path).convert_alpha()
                w, h = CARD_SIZE_MEDIUM
                img = pygame.transform.scale(img, (int(w * 0.8), int(h * 0.8)))
                angle = random.uniform(-35, 35)
                img = pygame.transform.rotate(img, angle)

                attempts = 0
                x, y = 0, 0
                while attempts < 20:
                    x = random.randint(50, SCREEN_WIDTH - 200)
                    y = random.randint(50, SCREEN_HEIGHT - 200)
                    cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
                    if abs(x - cx) < 350 and abs(y - cy) < 300:
                        attempts += 1
                        continue
                    too_close = any(
                        abs(x - p[0]) < 120 and abs(y - p[1]) < 160
                        for p in used_positions
                    )
                    if too_close:
                        attempts += 1
                        continue
                    used_positions.append((x, y))
                    break

                img.set_alpha(240)
                cards.append({"image": img, "x": x, "y": y})
            except FileNotFoundError:
                continue

        return cards

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        action = self._handle_click(event.pos)
                        if action:
                            return action

            self._update_hover(mouse_pos)
            self._draw()
            pygame.display.flip()

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                return btn["action"]
        return None

    def _update_hover(self, mouse_pos: tuple[int, int]):
        for btn in self.buttons:
            btn["hover"] = btn["rect"].collidepoint(mouse_pos)

    def _draw(self):
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, (0, 0))

        for card in self.bg_cards:
            self.screen.blit(card["image"], (card["x"], card["y"]))

        center_overlay = pygame.Surface((500, SCREEN_HEIGHT), pygame.SRCALPHA)
        center_overlay.fill((0, 0, 0, 140))
        self.screen.blit(center_overlay, (SCREEN_WIDTH // 2 - 250, 0))

        self._draw_logo()
        self._draw_buttons()

    def _draw_logo(self):
        if self.logo:
            logo_rect = self.logo.get_rect(
                center=(SCREEN_WIDTH // 2, 150)
            )
            self.screen.blit(self.logo, logo_rect)
        else:
            font_title = pygame.font.SysFont(None, 120)
            shadow = font_title.render("CHUJ", True, (0, 0, 0))
            title = font_title.render("CHUJ", True, COLOR_GOLD)
            rect = title.get_rect(center=(SCREEN_WIDTH // 2, 150))
            self.screen.blit(shadow, (rect.x + 3, rect.y + 3))
            self.screen.blit(title, rect)

    def _draw_buttons(self):
        for btn in self.buttons:
            self._draw_button(btn)

    def _draw_button(self, btn: dict):
        rect = btn["rect"]
        color = btn["color"]
        alpha = 240 if btn["hover"] else 200

        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.screen.blit(overlay, (rect.x, rect.y))

        if btn["hover"]:
            hover_surf = pygame.Surface(
                (rect.width, rect.height), pygame.SRCALPHA
            )
            hover_surf.fill((255, 255, 255, 25))
            self.screen.blit(hover_surf, (rect.x, rect.y))

        border_color = COLOR_GOLD if btn["hover"] else COLOR_GRAY
        pygame.draw.rect(
            self.screen, border_color,
            rect, width=2, border_radius=BUTTON_RADIUS
        )

        text_color = COLOR_GOLD if btn["hover"] else COLOR_WHITE
        text_surf = self.font_button.render(btn["label"], True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        self.screen.blit(text_surf, text_rect)

    def __repr__(self) -> str:
        return "Menu()"