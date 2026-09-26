# gui/stats_screen.py
#
# Profil hráča a jeho štatistiky. Vizuál zámerne kopíruje
# gui/settings_screen.py (tmavé panely, zlatý rám, rovnaký nadpis aj
# tlačidlo Späť), aby obrazovky pôsobili ako jedna rodina.
#
# Všetky čísla pochádzajú z game/profile.py — tu sa nič nepočíta, len
# vykresľuje. Vďaka tomu sa dá obsah meniť bez zásahu do zberu dát.

import pygame
import sys

from game.profile import (
    DEFAULT_NAME, Stats, load_profiles, save_profiles,
)
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_DARK_GRAY,
    COLOR_GREEN, COLOR_RED,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY, COLOR_PANEL_BG,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL,
    BUTTON_RADIUS, get_font,
)

# Menovka hráča sa na dvoch miestach skracuje na 10 znakov (panel KOLO v
# gui/round_status.py a hlavička Chujogramu) — stĺpec Chujogramu je na
# viac aj priúzky. Obmedzenie držíme na rovnakej hodnote, nech platí, že
# čo si napíšeš, to aj všade uvidíš.
MAX_NAME_LEN = 10


class StatsScreen:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()

        self.font_title = get_font(64)
        self.font_large = get_font(FONT_SIZE_LARGE)
        self.font_medium = get_font(FONT_SIZE_MEDIUM)
        self.font_small = get_font(FONT_SIZE_SMALL)
        self.font_value = get_font(30)

        try:
            self.bg = pygame.image.load("assets/graphics/table.jpg").convert()
            self.bg = pygame.transform.scale(
                self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT)
            )
        except FileNotFoundError:
            self.bg = None

        self.profiles, self.active = load_profiles()
        self.profile = self.profiles[self.active]
        self.stats: Stats = self.profile.stats()

        # Premenovanie profilu — jednoduché textové pole, aktivuje sa
        # kliknutím naň. Esc zruší, Enter potvrdí.
        self.editing_name = False
        self.name_buffer = ""
        self._caret_timer = 0

        center_x = SCREEN_WIDTH // 2
        self.panel_width = min(1100, SCREEN_WIDTH - 120)
        panel_x = center_x - self.panel_width // 2
        col_w = (self.panel_width - 20) // 2

        top = 170
        self.panel_name = pygame.Rect(panel_x, top, self.panel_width, 92)
        self.name_field = pygame.Rect(
            panel_x + 210, top + 22, 320, 48
        )
        self.rename_button = {
            "rect": pygame.Rect(panel_x + 552, top + 22, 170, 48),
            "hover": False,
        }

        body_top = self.panel_name.bottom + 18
        # Výška panelov sa dopočíta z počtu riadkov (viď _sections()).
        self.col_x = (panel_x, panel_x + col_w + 20)
        self.col_w = col_w
        self.body_top = body_top

        self.back_button = {
            "rect": pygame.Rect(center_x - 150, SCREEN_HEIGHT - 70, 300, 50),
            "hover": False,
        }

    # ------------------------------------------------------------------
    # Obsah
    # ------------------------------------------------------------------

    def _sections(self) -> list[tuple[str, list[tuple[str, str, tuple]]]]:
        """Zoznam (nadpis, [(popis, hodnota, farba), ...])."""
        s = self.stats
        none = COLOR_WHITE

        def pct(v: float) -> str:
            return f"{v:.0f} %"

        def num(v: float, d: int = 1) -> str:
            return f"{v:.{d}f}"

        if s.games == 0:
            return [(
                "ZATIAĽ ŽIADNE DÁTA",
                # Prázdna hodnota → vykreslí sa len popis, teda súvislá
                # veta namiesto riadku tabuľky.
                [("Odohraj prvú hru a štatistiky sa tu objavia.", "", COLOR_GRAY)]
            )]

        win_color = COLOR_GREEN if s.win_rate >= 50 else COLOR_RED

        bilancia = [
            ("Odohraté hry", str(s.games), none),
            ("Výhry", str(s.wins), COLOR_GREEN),
            ("Prehry (bol si Chuj)", str(s.losses), COLOR_RED),
            ("Úspešnosť", pct(s.win_rate), win_color),
            ("Priemerné umiestnenie", num(s.avg_placement, 2), none),
            ("Séria bez prehry", str(s.current_streak), none),
            ("Najdlhšia séria", str(s.best_streak), COLOR_GOLD),
            ("Nedohraté hry", str(s.abandoned), COLOR_GRAY),
        ]

        skore = [
            ("Priemerné skóre", num(s.avg_score), none),
            ("Najlepšia hra", str(s.best_game), COLOR_GREEN),
            ("Najhoršia hra", str(s.worst_game), COLOR_RED),
            ("Body na kolo", num(s.avg_round_points), none),
        ]

        kola = [
            ("Odohraté kolá", str(s.rounds), none),
            ("Čisté kolá (0 b)", f"{s.clean_rounds}  ({pct(s.clean_rate)})",
             COLOR_GREEN),
            ("Najdlhšia čistá séria", str(s.longest_clean_streak), COLOR_GOLD),
            ("Bonus za 5 čistých", str(s.streak_bonus), COLOR_GREEN),
            ("Reset zo 100 na 90", str(s.reset_100), none),
        ]

        karty = [
            ("Zelený horník", str(s.leaf_over_caught), COLOR_RED),
            ("Žaluďový horník", str(s.acorn_over_caught), COLOR_RED),
            ("Srdcia spolu", str(s.hearts_caught), none),
            ("Srdcia na kolo", num(s.avg_hearts_per_round), none),
            ("Vysvietenia", str(s.illuminated), none),
            ("Z toho schytal vlastného", str(s.illuminated_caught_own), COLOR_RED),
            ("Úspešnosť vysvietenia",
             pct(s.illumination_success) if s.illuminated else "—",
             COLOR_GREEN if s.illumination_success >= 50 else COLOR_RED),
        ]

        specialty = [
            ("Zhabal všetko (sweep)", str(s.sweeps), COLOR_GREEN),
            ("„Nechytím nič\" — vyhlásené", str(s.declared_none), none),
            ("    z toho splnené",
             f"{s.declared_none_ok}  ({pct(s.declared_none_rate)})"
             if s.declared_none else "—", COLOR_GREEN),
            ("„Beriem všetko\" — vyhlásené", str(s.declared_all), none),
            ("    z toho splnené",
             f"{s.declared_all_ok}  ({pct(s.declared_all_rate)})"
             if s.declared_all else "—", COLOR_GREEN),
        ]

        return [
            ("BILANCIA", bilancia),
            ("SKÓRE", skore),
            ("KOLÁ", kola),
            ("KARTY A HORNÍCI", karty),
            ("ZÁVÄZKY A ŠPECIALITY", specialty),
        ]

    # ------------------------------------------------------------------
    # Slučka
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
                    if self.editing_name:
                        if event.key == pygame.K_ESCAPE:
                            self.editing_name = False
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self._commit_name()
                        elif event.key == pygame.K_BACKSPACE:
                            self.name_buffer = self.name_buffer[:-1]
                        elif event.unicode and event.unicode.isprintable():
                            if len(self.name_buffer) < MAX_NAME_LEN:
                                self.name_buffer += event.unicode
                        continue
                    if event.key == pygame.K_ESCAPE:
                        return "menu"

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._handle_click(event.pos) == "back":
                        return "menu"

            self.back_button["hover"] = self.back_button["rect"].collidepoint(
                mouse_pos
            )
            self.rename_button["hover"] = \
                self.rename_button["rect"].collidepoint(mouse_pos)

            self._draw()
            pygame.display.flip()

    def _handle_click(self, pos) -> str | None:
        if self.name_field.collidepoint(pos) or \
                self.rename_button["rect"].collidepoint(pos):
            if self.editing_name:
                self._commit_name()
            else:
                self.editing_name = True
                self.name_buffer = self.profile.name
            return None

        # Klik mimo poľa počas písania = potvrdenie.
        if self.editing_name:
            self._commit_name()

        if self.back_button["rect"].collidepoint(pos):
            return "back"
        return None

    def _commit_name(self):
        """Uloží premenovaný profil. Prázdne meno sa ignoruje, aby
        nevznikol profil bez mena."""
        self.editing_name = False
        new_name = self.name_buffer.strip()
        if not new_name or new_name == self.profile.name:
            return
        if new_name in self.profiles and new_name != self.profile.name:
            # Meno už existuje — nesmieme prepísať cudzí profil.
            return
        old_name = self.profile.name
        self.profile.name = new_name
        self.profiles.pop(old_name, None)
        self.profiles[new_name] = self.profile
        self.active = new_name
        save_profiles(self.profiles, self.active)

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render("PROFIL", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 88)))
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (SCREEN_WIDTH // 2 - 220, 128), (SCREEN_WIDTH // 2 + 220, 128),
            width=2
        )

        self._draw_name_panel()
        self._draw_sections()
        self._draw_back_button()

    def _draw_name_panel(self):
        self._panel_bg(self.panel_name)
        label = self.font_medium.render("MENO HRÁČA", True, COLOR_GOLD)
        self.screen.blit(
            label, label.get_rect(midleft=(self.panel_name.left + 28,
                                           self.name_field.centery))
        )

        active = self.editing_name
        pygame.draw.rect(
            self.screen, (12, 8, 4), self.name_field, border_radius=8
        )
        pygame.draw.rect(
            self.screen, COLOR_GOLD if active else COLOR_DARK_GRAY,
            self.name_field, width=2, border_radius=8
        )

        text = self.name_buffer if active else self.profile.name
        surf = self.font_value.render(text, True, COLOR_WHITE)
        self.screen.blit(
            surf, surf.get_rect(midleft=(self.name_field.left + 14,
                                         self.name_field.centery))
        )
        if active:
            self._caret_timer = (self._caret_timer + 1) % 60
            if self._caret_timer < 30:
                cx = self.name_field.left + 16 + surf.get_width() + 2
                pygame.draw.line(
                    self.screen, COLOR_WHITE,
                    (cx, self.name_field.top + 10),
                    (cx, self.name_field.bottom - 10), width=2
                )

        self._draw_button(
            self.rename_button,
            "Hotovo" if active else "Premenovať",
            COLOR_BUTTON_PRIMARY if active else COLOR_BUTTON_SECONDARY
        )

    def _draw_sections(self):
        sections = self._sections()
        # Rozmery sú navrhnuté tak, aby sa na 1080p zmestili všetky
        # sekcie do dvoch stĺpcov aj s rezervou — inak by ich poistka
        # nižšie ticho zahodila. Na nižších obrazovkách sa riadky ešte
        # stiahnu.
        compact = SCREEN_HEIGHT < 950
        row_h = 24 if compact else 28
        head_h = 44 if compact else 50
        pad_bottom = 10 if compact else 12
        gap = 12 if compact else 14

        col_bottom = [self.body_top, self.body_top]
        for idx, (title, rows) in enumerate(sections):
            # Striedavo do ľavého a pravého stĺpca, vždy do toho kratšieho —
            # tým sa panely samé vyvážia bez ručného ladenia výšok.
            col = 0 if col_bottom[0] <= col_bottom[1] else 1
            h = head_h + len(rows) * row_h + pad_bottom
            rect = pygame.Rect(self.col_x[col], col_bottom[col], self.col_w, h)
            if rect.bottom > self.back_button["rect"].top - 12:
                # Poistka pre veľmi nízke rozlíšenia. Na bežnej obrazovke
                # sem kód nemá doraziť — ak by sa to stalo, je to signál
                # pridať rolovanie, nie mlčky zahodiť ďalšie sekcie.
                break
            self._panel_bg(rect)

            label = self.font_medium.render(title, True, COLOR_GOLD)
            self.screen.blit(
                label, label.get_rect(midleft=(rect.left + 24, rect.top + 28))
            )
            pygame.draw.line(
                self.screen, COLOR_DARK_GRAY,
                (rect.left + 20, rect.top + 48),
                (rect.right - 20, rect.top + 48), width=1
            )

            y = rect.top + head_h
            for name, value, color in rows:
                n = self.font_small.render(name, True, COLOR_GRAY)
                self.screen.blit(n, (rect.left + 24, y + 4))
                v = self.font_small.render(str(value), True, color)
                self.screen.blit(
                    v, v.get_rect(topright=(rect.right - 24, y + 4))
                )
                y += row_h

            col_bottom[col] = rect.bottom + gap

    def _panel_bg(self, rect: pygame.Rect):
        surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        surf.fill((*COLOR_PANEL_BG, 210))
        self.screen.blit(surf, (rect.x, rect.y))
        pygame.draw.rect(self.screen, COLOR_GOLD, rect, width=2, border_radius=14)

    def _draw_button(self, btn: dict, text: str, color: tuple):
        rect = btn["rect"]
        shade = tuple(min(255, c + 30) for c in color) if btn.get("hover") else color
        pygame.draw.rect(self.screen, shade, rect, border_radius=BUTTON_RADIUS)
        pygame.draw.rect(
            self.screen, COLOR_GOLD, rect, width=2, border_radius=BUTTON_RADIUS
        )
        surf = self.font_small.render(text, True, COLOR_WHITE)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def _draw_back_button(self):
        self._draw_button(self.back_button, "Späť do menu", COLOR_BUTTON_SECONDARY)
