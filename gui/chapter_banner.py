# gui/chapter_banner.py
#
# Horný pás s názvom kapitoly a tlačidlom "Preskočiť".
#
# Jedna komponenta pre OBE kapitoly tutoriálu:
#   - kapitola 1 ("TUTORIÁL — PRIEBEH KOLA") ním nahradila vlastné
#     kreslenie v tutorial/tutorial_screen.py::_draw_title_bar(),
#   - kapitola 2 ("TRÉNINGOVÁ HRA") ho tým dostáva úplne zadarmo —
#     dovtedy nemala ako dať najavo, že nejde o ostrú hru, ani ako z nej
#     odísť ďalej.
#
# Zapína sa cez nastavenie "chapter_banner" (názov kapitoly) v settings
# dicte, ktorý dostane gui/screen.py::Screen. Ostrá hra ho nenastavuje,
# takže tam pás nie je vôbec.
#
# Pozri claude/08_TUTORIAL_REFACTOR_DESIGN.md §5.

import pygame

from config import (
    SCREEN_WIDTH, COLOR_WHITE, COLOR_GOLD, COLOR_BUTTON_SECONDARY,
    BUTTON_RADIUS, FONT_SIZE_SMALL, FONT_SIZE_LARGE, get_font,
)

BANNER_H = 80


class ChapterBanner:
    """Pás cez celú šírku obrazovky s názvom kapitoly a tlačidlom vpravo."""

    def __init__(self, screen: pygame.Surface, title: str,
                 button_label: str = "Preskočiť"):
        self.screen = screen
        self.title = title
        self.button_label = button_label
        self.font_small = get_font(FONT_SIZE_SMALL)
        self.font_large = get_font(FONT_SIZE_LARGE)
        self.button = pygame.Rect(SCREEN_WIDTH - 190, 24, 150, 44)

    def draw(self) -> pygame.Rect:
        """Nakreslí pás a vráti obdĺžnik tlačidla."""
        banner = pygame.Surface((SCREEN_WIDTH, BANNER_H), pygame.SRCALPHA)
        banner.fill((0, 0, 0, 190))
        self.screen.blit(banner, (0, 0))
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (0, BANNER_H), (SCREEN_WIDTH, BANNER_H), width=1
        )

        title_surf = self.font_large.render(self.title, True, COLOR_GOLD)
        self.screen.blit(
            title_surf, title_surf.get_rect(centerx=SCREEN_WIDTH // 2, top=24)
        )

        overlay = pygame.Surface(
            (self.button.width, self.button.height), pygame.SRCALPHA
        )
        overlay.fill((*COLOR_BUTTON_SECONDARY, 220))
        self.screen.blit(overlay, self.button.topleft)
        pygame.draw.rect(
            self.screen, COLOR_GOLD, self.button,
            width=2, border_radius=BUTTON_RADIUS
        )
        label = self.font_small.render(self.button_label, True, COLOR_WHITE)
        self.screen.blit(label, label.get_rect(center=self.button.center))
        return self.button

    def hit(self, pos) -> bool:
        return self.button.collidepoint(pos)

    def __repr__(self) -> str:
        return f"ChapterBanner({self.title!r})"
