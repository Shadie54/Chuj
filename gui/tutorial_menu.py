# gui/tutorial_menu.py
#
# Podmenu "Tutoriál" — výber kapitoly. Zoznam kapitol (ich id a poradie)
# dostáva zvonku (main.py, z tutorial_main.py::CHAPTERS), aby to ostalo
# jediné miesto pravdy — tu sa id iba prekladajú na zobrazované mená
# (CHAPTER_LABELS). Vizuálne kopíruje gui/menu.py (rovnaké farby, rovnaký
# štýl tlačidiel), aby pôsobilo ako súčasť tej istej obrazovky.

import pygame
import sys
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE,
    BUTTON_RADIUS, get_font
)

CHAPTER_LABELS = {
    "zaklady": "Základy",
    "trening": "Tréning",
}


class TutorialMenu:
    """Výber kapitoly tutoriálu.

    run() vráti buď id zvolenej kapitoly (napr. "zaklady"), alebo "back"
    (návrat do hlavného menu bez spustenia kapitoly).
    """

    def __init__(self, screen: pygame.Surface, chapter_ids: list[str]):
        self.screen = screen
        self.clock = pygame.time.Clock()

        self.font_button = get_font(FONT_SIZE_LARGE)
        self.font_title = get_font(60)

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        btn_w = 340
        btn_h = 65
        center_x = SCREEN_WIDTH // 2

        buttons_data = [
            (CHAPTER_LABELS.get(cid, cid), cid, COLOR_BUTTON_PRIMARY)
            for cid in chapter_ids
        ]
        buttons_data.append(("Späť", "back", COLOR_BUTTON_SECONDARY))

        start_y = 420
        # Rovnaký ochranný posun ako v gui/menu.py — na nižšom rozlíšení by
        # posledné tlačidlo vypadlo pod okraj.
        last_bottom = start_y + (len(buttons_data) - 1) * 85 + btn_h
        if last_bottom > SCREEN_HEIGHT - 40:
            start_y -= last_bottom - (SCREEN_HEIGHT - 40)

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
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        self._draw_title()
        for btn in self.buttons:
            self._draw_button(btn)

    def _draw_title(self):
        title_bottom_padding = 60
        first_btn_y = self.buttons[0]["rect"].top

        shadow = self.font_title.render("TUTORIÁL", True, (0, 0, 0))
        title = self.font_title.render("TUTORIÁL", True, COLOR_GOLD)
        rect = title.get_rect(
            centerx=SCREEN_WIDTH // 2,
            bottom=first_btn_y - title_bottom_padding
        )
        self.screen.blit(shadow, (rect.x + 3, rect.y + 3))
        self.screen.blit(title, rect)

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
        return "TutorialMenu()"
