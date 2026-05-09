# gui/info_overlay.py

import pygame
import os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_RED, COLOR_GREEN,
    COLOR_BUTTON_SECONDARY, CARDS_MEDIUM_PATH, CARD_SIZE_MEDIUM,
    COLOR_PENALTY, COLOR_BONUS, COLOR_ILLUMINATED, get_font, SUIT_ICONS_PATH
)


class InfoOverlay:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.visible = False
        self.font_small = get_font(22)
        self.font_medium = get_font(30)
        self.font_large = get_font(48)
        self._card_cache: dict[str, pygame.Surface] = {}

        self.btn_close = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)

        self.active_tab = "bodovanie"

        tab_w, tab_h = 220, 45
        cx = SCREEN_WIDTH // 2
        self.tab_bodovanie = pygame.Rect(cx - tab_w - 10, 75, tab_w, tab_h)
        self.tab_pravidla  = pygame.Rect(cx + 10,         75, tab_w, tab_h)

        self.content_y = 135
        # ikonky farieb
        self._suit_icons: dict[str, pygame.Surface] = {}
        self._load_suit_icons()
    # ------------------------------------------------------------------
    # Viditeľnosť
    # ------------------------------------------------------------------

    def show(self):    self.visible = True
    def hide(self):    self.visible = False
    def toggle(self):  self.visible = not self.visible

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_i):
                self.hide()
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_close.collidepoint(event.pos):
                self.hide()
                return True
            if self.tab_bodovanie.collidepoint(event.pos):
                self.active_tab = "bodovanie"
                return True
            if self.tab_pravidla.collidepoint(event.pos):
                self.active_tab = "pravidla"
                return True
            return True
        return False

    # ------------------------------------------------------------------
    # Hlavné kreslenie
    # ------------------------------------------------------------------

    def draw(self):
        if not self.visible:
            return

        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 245))
        self.screen.blit(dark, (0, 0))

        # Nadpis
        title = self.font_large.render("PRAVIDLÁ A BODOVANIE", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(centerx=SCREEN_WIDTH // 2, top=18))
        pygame.draw.line(self.screen, COLOR_GOLD, (80, 68), (SCREEN_WIDTH - 80, 68), 1)

        # Zavrieť
        pygame.draw.rect(self.screen, COLOR_BUTTON_SECONDARY,
                         self.btn_close, border_radius=6)
        pygame.draw.rect(self.screen, COLOR_GOLD,
                         self.btn_close, width=2, border_radius=6)
        x = self.font_medium.render("X", True, COLOR_WHITE)
        self.screen.blit(x, x.get_rect(center=self.btn_close.center))

        self._draw_tabs()

        if self.active_tab == "bodovanie":
            self._draw_scoring()
        else:
            self._draw_rules()

    # ------------------------------------------------------------------
    # Záložky
    # ------------------------------------------------------------------

    def _draw_tabs(self):
        for tab, label, key in (
            (self.tab_bodovanie, "Bodovanie", "bodovanie"),
            (self.tab_pravidla,  "Pravidlá",  "pravidla"),
        ):
            active = self.active_tab == key
            pygame.draw.rect(self.screen,
                             (45, 30, 12) if active else (20, 12, 5),
                             tab, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_GOLD, tab, width=2, border_radius=6)
            surf = self.font_small.render(label, True,
                                          COLOR_GOLD if active else COLOR_GRAY)
            self.screen.blit(surf, surf.get_rect(center=tab.center))

    # ------------------------------------------------------------------
    # Záložka: BODOVANIE
    # ------------------------------------------------------------------

    def _draw_scoring(self):
        y = self.content_y + 10

        def draw_section(x, cy, title, content_fn, col_w):
            """Dynamická sekcia — content_fn(x, y, col_w) -> výška obsahu."""
            # Zisti výšku obsahu
            content_h = content_fn(x, cy, col_w, measure_only=True)
            box_h = 36 + content_h + 20

            box = pygame.Surface((col_w, box_h), pygame.SRCALPHA)
            box.fill((20, 12, 5, 160))
            self.screen.blit(box, (x, cy))
            pygame.draw.rect(self.screen, COLOR_GOLD, (x, cy, 3, box_h))

            title_surf = self.font_medium.render(title, True, COLOR_GOLD)
            self.screen.blit(title_surf, (x + 14, cy + 10))
            line_y = cy + 10 + title_surf.get_height() + 4
            pygame.draw.line(self.screen, (80, 60, 20),
                             (x + 14, line_y), (x + col_w - 14, line_y), 1)

            content_fn(x, line_y + 10, col_w, measure_only=False)
            return cy + box_h + 14

        full_w = SCREEN_WIDTH - 120
        col_x = 60
        col_w2 = (full_w - 40) // 2

        # ── SEKCIA 1: HODNOTY KARIET (plná šírka) ──────────────────────────
        def content_karty(x, y, w, measure_only):
            ranks = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]
            card_w, card_h = 95, 153
            gap = 12
            total_w = len(ranks) * (card_w + gap) - gap
            x0 = SCREEN_WIDTH // 2 - total_w // 2
            if not measure_only:
                for i, rank in enumerate(ranks):
                    cx = x0 + i * (card_w + gap)
                    img = self._load_card("heart", rank)
                    if img:
                        self.screen.blit(
                            pygame.transform.scale(img, (card_w, card_h)), (cx, y))
                    pts = self.font_small.render("1b", True, COLOR_PENALTY)
                    self.screen.blit(pts, pts.get_rect(
                        centerx=cx + card_w // 2, top=y + card_h + 4))
            return card_h + 30

        y = draw_section(col_x, y, "HODNOTY KARIET", content_karty, full_w)

        # ── SEKCIA 2: HORNÍCI + BONUSY (2 stĺpce) ─────────────────────────
        def content_hornici(x, y, w, measure_only):
            specials = [
                ("leaf", "over", "8b", "16b pri vysvietení", None),
                ("acorn", "over", "4b", "8b pri vysvietení", "+ červené = 2b (ak obaja)"),
            ]
            card_w, card_h = 110, 177
            if not measure_only:
                block_w = w // 2
                for i, (suit, rank, base, illum, note) in enumerate(specials):
                    bx = x + i * block_w + 14
                    img = self._load_card(suit, rank)
                    if img:
                        self.screen.blit(
                            pygame.transform.scale(img, (card_w, card_h)), (bx, y))
                    tx = bx + card_w + 14
                    ty = y + 16
                    s = self.font_medium.render(base, True, COLOR_PENALTY)
                    self.screen.blit(s, (tx, ty));
                    ty += 34
                    s = self.font_small.render(illum, True, COLOR_ILLUMINATED)
                    self.screen.blit(s, (tx, ty));
                    ty += 26
                    if note:
                        s = self.font_small.render(note, True, COLOR_ILLUMINATED)
                        self.screen.blit(s, (tx, ty))
            return card_h + 10

        def content_bonusy(x, y, w, measure_only):
            bonuses = [
                (COLOR_BONUS, "−10b", "Sweep — všetky trestné karty v kole"),
                (COLOR_BONUS, "−10b", "Séria — 5 kôl za sebou bez trestu"),
                (COLOR_BONUS, "−10b", "Záväzok splnený: Nechytím nič"),
                (COLOR_BONUS, "−20b", "Záväzok splnený: Beriem všetko"),
                (COLOR_PENALTY, "+20b", "Nesplnený: Beriem všetko → hráč +20b"),
                (COLOR_PENALTY, "−10b", "Nesplnený: Nechytím nič → ostatní −10b"),
                (COLOR_GRAY, "Reset", "Presne 100b → resetuje sa na 90b"),
                (COLOR_GRAY, "90b+", "Horníci sa nepočítajú nad 90b"),
            ]
            row_h = 30
            if not measure_only:
                for idx, (color, badge, text) in enumerate(bonuses):
                    self._draw_badge_line(x + 14, y + idx * row_h, badge, text, color)
            return len(bonuses) * row_h

        # Horníci a bonusy vedľa seba
        cy_h = y
        cy_b = y

        # Zisti výšky
        h_hornici = content_hornici(col_x, y, col_w2, measure_only=True) + 36 + 20 + 14
        h_bonusy = content_bonusy(col_x, y, col_w2, measure_only=True) + 36 + 20 + 14

        # Kresli ľavý box — horníci
        box_h = content_hornici(col_x, y, col_w2, measure_only=True) + 36 + 20
        box = pygame.Surface((col_w2, box_h), pygame.SRCALPHA)
        box.fill((20, 12, 5, 160))
        self.screen.blit(box, (col_x, y))
        pygame.draw.rect(self.screen, COLOR_GOLD, (col_x, y, 3, box_h))
        t = self.font_medium.render("HORNÍCI", True, COLOR_GOLD)
        self.screen.blit(t, (col_x + 14, y + 10))
        line_y = y + 10 + t.get_height() + 4
        pygame.draw.line(self.screen, (80, 60, 20),
                         (col_x + 14, line_y), (col_x + col_w2 - 14, line_y), 1)
        content_hornici(col_x, line_y + 10, col_w2, measure_only=False)

        # Kresli pravý box — bonusy
        bx2 = col_x + col_w2 + 40
        box_h2 = content_bonusy(bx2, y, col_w2, measure_only=True) + 36 + 20
        box2 = pygame.Surface((col_w2, box_h2), pygame.SRCALPHA)
        box2.fill((20, 12, 5, 160))
        self.screen.blit(box2, (bx2, y))
        pygame.draw.rect(self.screen, COLOR_GOLD, (bx2, y, 3, box_h2))
        t2 = self.font_medium.render("BONUSY A PRAVIDLÁ", True, COLOR_GOLD)
        self.screen.blit(t2, (bx2 + 14, y + 10))
        line_y2 = y + 10 + t2.get_height() + 4
        pygame.draw.line(self.screen, (80, 60, 20),
                         (bx2 + 14, line_y2), (bx2 + col_w2 - 14, line_y2), 1)
        content_bonusy(bx2, line_y2 + 10, col_w2, measure_only=False)

    # ------------------------------------------------------------------
    # Záložka: PRAVIDLÁ
    # ------------------------------------------------------------------

    def _draw_rules(self):
        y = self.content_y + 10
        col_w = (SCREEN_WIDTH - 160) // 2
        col1_x = 60
        col2_x = col1_x + col_w + 40

        def draw_section(x, cy, title, lines):
            """Nakreslí sekciu s accent linkou a obsahom, vráti nové cy."""
            # Obsah — zisti výšku najprv
            content_lines = [l for l in lines if l != ""]
            empty_lines = lines.count("")
            content_h = len(content_lines) * 27 + empty_lines * 10 + 10
            box_h = 36 + content_h + 14  # nadpis + obsah + padding

            # Karta — polopriesvitné pozadie
            box = pygame.Surface((col_w, box_h), pygame.SRCALPHA)
            box.fill((20, 12, 5, 160))
            self.screen.blit(box, (x, cy))

            # Zlatá accent linka vľavo
            pygame.draw.rect(self.screen, COLOR_GOLD, (x, cy, 3, box_h))

            # Nadpis sekcie
            title_surf = self.font_medium.render(title, True, COLOR_GOLD)
            self.screen.blit(title_surf, (x + 14, cy + 10))

            # Oddeľovač pod nadpisom
            line_y = cy + 10 + title_surf.get_height() + 4
            pygame.draw.line(self.screen, (80, 60, 20),
                             (x + 14, line_y), (x + col_w - 14, line_y), 1)

            # Obsah
            text_y = line_y + 10
            for line in lines:
                if not line:
                    text_y += 10
                    continue
                surf = self._render_with_icons(line, self.font_small, COLOR_WHITE)
                self.screen.blit(surf, (x + 14, text_y))
                text_y += 27

            return cy + box_h + 14  # medzera medzi sekciami

        # ══ STĹPEC 1 ══
        cy1 = y
        cy1 = draw_section(col1_x, cy1, "CIEĽ HRY", [
            "Hráč ktorý ako prvý prekročí 100 bodov",
            "prehráva a stáva sa Chujom.",
            "Cieľom je nazbierať čo najmenej bodov.",
        ])

        cy1 = draw_section(col1_x, cy1, "PRIEBEH KOLA", [
            "1.  Rozdanie — každý dostane 8 kariet",
            "2.  Vysvietenie — možnosť priznať horníka",
            "3.  Záväzok — Beriem všetko / Nechytím nič",
            "4.  8 štichov — hráči zahrajú všetky karty",
            "5.  Bodovanie — spočítajú sa trestné body",
        ])

        cy1 = draw_section(col1_x, cy1, "ŠTICHY", [
            "Leader zahrá kartu a určí farbu štichu.",
            "Ostatní MUSIA zahrať kartu rovnakej farby.",
            "Ak nemáš danú farbu — zahraj čokoľvek.",
            "Najvyššia karta v hranej farbe vyhráva.",
            "Víťaz štichu začína nasledujúci štich.",
            "V prvom štichu sa nesmie hrať červeň.",
        ])

        # ══ STĹPEC 2 ══
        cy2 = y
        cy2 = draw_section(col2_x, cy2, "VYSVIETENIE", [
            "Pred prvým štichom môžeš priznať Q♠, Q♣",
            "alebo oboch horníkov.",
            "Vysvietený horník je viditeľný všetkým.",
            "Vysvietený Q♠ = 16b  (bežne 8b)",
            "Vysvietený Q♣ = 8b   (bežne 4b)",
            "Obaja vysvietení → červené = 2b (bežne 1b)",
        ])

        cy2 = draw_section(col2_x, cy2, "ZÁVÄZOK", [
            "Beriem všetko — musíš vyhrať 8 štichov.",
            "  Splnený: −20b pre teba, ostatní 0b",
            "  Nesplnený: +20b pre teba, ostatní 0b",
            "",
            "Nechytím nič — nesmieš chytiť štich.",
            "  Splnený: −10b pre teba, ostatní 0b",
            "  Nesplnený: ostatní −10b, ty 0b",
        ])

        cy2 = draw_section(col2_x, cy2, "ŠPECIÁLNE PRAVIDLÁ", [
            "Sweep  — všetky trestné karty → −10b",
            "Séria  — 5 kôl bez trestného bodu → −10b",
            "Reset  — presne 100b → resetuje sa na 90b",
            "90b+   — horníci sa nepočítajú (0b)",
        ])

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _section_title(self, text: str, x: int, y: int,
                        center: bool = False):
        surf = self.font_medium.render(text, True, COLOR_GOLD)
        rx = x if not center else surf.get_rect(centerx=x).x
        self.screen.blit(surf, (rx, y))
        line_y = y + surf.get_height() + 2
        line_w = surf.get_width() if not center else SCREEN_WIDTH - 160
        lx = rx if not center else 80
        pygame.draw.line(self.screen, COLOR_GOLD,
                         (lx, line_y), (lx + line_w, line_y), 1)

    def _text_block(self, x: int, y: int, max_w: int,
                    lines: list[str]) -> int:
        """Vypíše blok textu, vráti y po poslednom riadku."""
        for line in lines:
            if not line:
                y += 10
                continue
            surf = self._render_with_icons(line, self.font_small, COLOR_WHITE)
            self.screen.blit(surf, (x, y))
            y += 24
        return y

    def _draw_badge_line(self, x: int, y: int, badge: str,
                          text: str, color: tuple):
        """Nakreslí riadok s farebným odznakom a textom."""
        # Odznak
        badge_surf = self.font_small.render(badge, True, color)
        bw = badge_surf.get_width() + 16
        bh = badge_surf.get_height() + 6
        bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 120))
        self.screen.blit(bg, (x, y - 3))
        pygame.draw.rect(self.screen, color,
                         (x, y - 3, bw, bh), width=1, border_radius=4)
        self.screen.blit(badge_surf, (x + 8, y))

        # Text
        txt = self.font_small.render(text, True, COLOR_WHITE)
        self.screen.blit(txt, (x + bw + 10, y))

    def _load_card(self, suit: str, rank: str) -> pygame.Surface | None:
        key = f"{suit}-{rank}"
        if key not in self._card_cache:
            path = os.path.join(CARDS_MEDIUM_PATH, f"{suit}-{rank}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                self._card_cache[key] = pygame.transform.scale(img, CARD_SIZE_MEDIUM)
            except FileNotFoundError:
                self._card_cache[key] = None
        return self._card_cache[key]

    def _load_suit_icons(self):
        """Načíta malé suit ikony a škáluje ich na výšku textu."""
        from config import SUIT_ICONS_PATH  # treba pridať do config.py
        icon_h = 22  # výška ikony = výška riadku font_small
        suits = {
            "♠": "leaf",
            "♣": "acorn",
            "♥": "heart",
            "●": "bell",
        }
        for symbol, suit in suits.items():
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@small.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                # Zachovaj pomer strán, výška = icon_h
                w, h = img.get_size()
                new_w = int(w * icon_h / h)
                self._suit_icons[symbol] = pygame.transform.scale(
                    img, (new_w, icon_h)
                )
            except FileNotFoundError:
                self._suit_icons[symbol] = None

    def _render_with_icons(self, text: str, font: pygame.font.Font,
                           color: tuple) -> pygame.Surface:
        """
        Vykreslí text kde suit symboly sú nahradené ikonkami.
        Vracia Surface so zloženým výsledkom.
        """
        import re
        # Rozdeľ text na časti — text a symboly
        parts = re.split(r'([♠♣♥●])', text)

        surfaces = []
        total_w = 0
        max_h = font.get_height()

        for part in parts:
            if part in self._suit_icons and self._suit_icons[part]:
                surf = self._suit_icons[part]
            elif part:
                surf = font.render(part, True, color)
            else:
                continue
            surfaces.append(surf)
            total_w += surf.get_width()
            max_h = max(max_h, surf.get_height())

        if not surfaces:
            return font.render(text, True, color)

        result = pygame.Surface((total_w, max_h), pygame.SRCALPHA)
        x = 0
        for surf in surfaces:
            # Vertikálne centrovanie
            y = (max_h - surf.get_height()) // 2
            result.blit(surf, (x, y))
            x += surf.get_width()

        return result

    def __repr__(self) -> str:
        return f"InfoOverlay(visible={self.visible})"