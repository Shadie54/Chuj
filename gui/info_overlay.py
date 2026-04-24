# gui/info_overlay.py

import pygame
import os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_RED, COLOR_GREEN,
    COLOR_BUTTON_SECONDARY, CARDS_MEDIUM_PATH, CARD_SIZE_MEDIUM,
    COLOR_PENALTY, COLOR_BONUS, COLOR_ILLUMINATED
)


class InfoOverlay:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.visible = False
        self.font_small  = pygame.font.SysFont(None, 30)
        self.font_medium = pygame.font.SysFont(None, 42)
        self.font_large  = pygame.font.SysFont(None, 60)
        self._card_cache: dict[str, pygame.Surface] = {}

        self.btn_close = pygame.Rect(SCREEN_WIDTH - 60, 20, 40, 40)

        self.active_tab = "bodovanie"

        tab_w, tab_h = 220, 45
        cx = SCREEN_WIDTH // 2
        self.tab_bodovanie = pygame.Rect(cx - tab_w - 10, 75, tab_w, tab_h)
        self.tab_pravidla  = pygame.Rect(cx + 10,         75, tab_w, tab_h)

        self.content_y = 135

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
        x = self.font_medium.render("✕", True, COLOR_WHITE)
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
        y = self.content_y + 5

        # ── Nadpis sekcie ──────────────────────────────────────────────
        self._section_title("HODNOTY KARIET", SCREEN_WIDTH // 2, y, center=True)
        y += 38

        # ── Červené karty (8 kusov) ────────────────────────────────────
        ranks = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]
        card_w, card_h = 105, 170
        gap = 14
        total_w = len(ranks) * (card_w + gap) - gap
        x0 = SCREEN_WIDTH // 2 - total_w // 2

        for i, rank in enumerate(ranks):
            cx = x0 + i * (card_w + gap)
            img = self._load_card("heart", rank)
            if img:
                self.screen.blit(pygame.transform.scale(img, (card_w, card_h)),
                                 (cx, y))
            # Body
            pts = self.font_medium.render("1b", True, COLOR_PENALTY)
            self.screen.blit(pts, pts.get_rect(centerx=cx + card_w // 2,
                                               top=y + card_h + 4))

        y += card_h + 38

        # ── Oddeľovač ─────────────────────────────────────────────────
        pygame.draw.line(self.screen, COLOR_GRAY,
                         (100, y), (SCREEN_WIDTH - 100, y), 1)
        y += 16

        # ── Horníci ───────────────────────────────────────────────────
        self._section_title("HORNÍCI", SCREEN_WIDTH // 2, y, center=True)
        y += 38

        specials = [
            ("leaf",  "over", "8b", "16b pri vysvietení"),
            ("acorn", "over", "4b", "8b pri vysvietení"),
        ]

        card_w2, card_h2 = 140, 226
        block_w = card_w2 + 260
        total_w2 = len(specials) * block_w
        x0 = SCREEN_WIDTH // 2 - total_w2 // 2

        for i, (suit, rank, base_pts, illum_pts) in enumerate(specials):
            bx = x0 + i * block_w
            img = self._load_card(suit, rank)
            if img:
                self.screen.blit(pygame.transform.scale(img, (card_w2, card_h2)),
                                 (bx, y))

            tx = bx + card_w2 + 18
            ty = y + 20

            # Základná hodnota
            s = self.font_medium.render(base_pts, True, COLOR_PENALTY)
            self.screen.blit(s, (tx, ty)); ty += 36

            # Vysvietená hodnota
            s = self.font_small.render(illum_pts, True, COLOR_ILLUMINATED)
            self.screen.blit(s, (tx, ty)); ty += 30

            # Dvojnásobok červenej
            if suit == "acorn":
                s = self.font_small.render("+ červené = 2b", True, COLOR_ILLUMINATED)
                self.screen.blit(s, (tx, ty)); ty += 26
                s = self.font_small.render("(ak obaja vysvietení)", True, COLOR_GRAY)
                self.screen.blit(s, (tx, ty))

        y += card_h2 + 20

        # ── Oddeľovač ─────────────────────────────────────────────────
        pygame.draw.line(self.screen, COLOR_GRAY,
                         (100, y), (SCREEN_WIDTH - 100, y), 1)
        y += 16

        # ── Bonusy ────────────────────────────────────────────────────
        self._section_title("BONUSY A ŠPECIÁLNE PRAVIDLÁ", SCREEN_WIDTH // 2,
                            y, center=True)
        y += 38

        bonuses = [
            (COLOR_BONUS,   "−10b",  "Chytím všetky trestné karty v kole  (Sweep)"),
            (COLOR_BONUS,   "−10b",  "5 kôl za sebou bez trestného bodu"),
            (COLOR_BONUS,   "−10b",  "Záväzok splnený: Nechytím nič"),
            (COLOR_BONUS,   "−20b",  "Záväzok splnený: Beriem všetko"),
            (COLOR_PENALTY, "+10b",  "Záväzok nesplnený → ostatní dostanú −10b"),
            (COLOR_GRAY,    "Reset", "Presne 100b → skóre sa resetuje na 90b"),
            (COLOR_GRAY,    "90b+",  "Nad 90b sa horníci počítajú len ako 1b"),
        ]

        col1_x = SCREEN_WIDTH // 2 - 500
        col2_x = SCREEN_WIDTH // 2 + 40
        half = len(bonuses) // 2 + len(bonuses) % 2

        for idx, (color, badge, text) in enumerate(bonuses):
            bx = col1_x if idx < half else col2_x
            by = y + (idx if idx < half else idx - half) * 34
            self._draw_badge_line(bx, by, badge, text, color)

    # ------------------------------------------------------------------
    # Záložka: PRAVIDLÁ
    # ------------------------------------------------------------------

    def _draw_rules(self):
        y = self.content_y + 5
        col_w = (SCREEN_WIDTH - 140) // 2
        col1_x = 70
        col2_x = 70 + col_w + 40

        # ══ STĹPEC 1 ══════════════════════════════════════════════════

        cy = y
        self._section_title("CIEĽ HRY", col1_x, cy)
        cy += 34
        cy = self._text_block(col1_x, cy, col_w, [
            "Hráč ktorý ako prvý prekročí 100 bodov prehráva a stáva sa Chujom.",
            "Cieľom je nazbierať čo najmenej trestných bodov.",
        ])
        cy += 16

        self._section_title("PRIEBEH KOLA", col1_x, cy)
        cy += 34
        steps = [
            ("1.", "Rozdanie — každý hráč dostane 8 kariet"),
            ("2.", "Vysvietenie — možnosť priznať horníka/ov"),
            ("3.", "Záväzok — možnosť vyhlásiť Beriem všetko / Nechytím nič"),
            ("4.", "8 štichov — hráči zahrajú všetky karty"),
            ("5.", "Bodovanie — spočítajú sa trestné body"),
        ]
        for num, text in steps:
            num_s = self.font_small.render(num, True, COLOR_GOLD)
            txt_s = self.font_small.render(text, True, COLOR_WHITE)
            self.screen.blit(num_s, (col1_x, cy))
            self.screen.blit(txt_s, (col1_x + 28, cy))
            cy += 26
        cy += 16

        self._section_title("ŠTICHY", col1_x, cy)
        cy += 34
        cy = self._text_block(col1_x, cy, col_w, [
            "Leader zahrá ľubovoľnú kartu a určí farbu štichu.",
            "Ostatní MUSIA zahrať kartu rovnakej farby (priznať farbu).",
            "Ak nemáš danú farbu — zahraj čokoľvek.",
            "Najvyššia karta v hranej farbe vyhráva štich.",
            "Víťaz štichu začína nasledujúci štich.",
            "V prvom štichu sa nesmie hrať červeň.",
        ])

        # ══ STĹPEC 2 ══════════════════════════════════════════════════

        cy = y
        self._section_title("VYSVIETENIE", col2_x, cy)
        cy += 34
        cy = self._text_block(col2_x, cy, col_w, [
            "Pred prvým štichom môžeš priznať zeleného horníka (Q♠),",
            "žaluďového horníka (Q♣) alebo oboch.",
            "Vysvietený horník je viditeľný — všetci vedia kde je.",
            "Vysvietený zelený horník = 16b  (bežne 8b).",
            "Vysvietený žaluďový horník = 8b  (bežne 4b).",
            "Ak sú obaja vysvietení → červené karty = 2b (bežne 1b).",
        ])
        cy += 16

        self._section_title("ZÁVÄZOK", col2_x, cy)
        cy += 34
        cy = self._text_block(col2_x, cy, col_w, [
            "Beriem všetko — hráč musí vyhrať všetkých 8 štichov.",
            "  → Splnený: −20b pre hráča.",
            "  → Nesplnený: +20b pre hráča, ostatní nič.",
            "",
            "Nechytím nič — hráč nesmie chytiť žiadny trestný bod.",
            "  → Splnený: −10b pre hráča.",
            "  → Nesplnený: ostatní dostanú −10b.",
            "",
            "Záväzok musí vyhlásiť hráč ktorý začína štich.",
        ])
        cy += 16

        self._section_title("ŠPECIÁLNE PRAVIDLÁ", col2_x, cy)
        cy += 34
        specials = [
            ("Sweep",   "Chytíš všetky trestné karty → −10b"),
            ("Séria",   "5 kôl bez trestného bodu → −10b"),
            ("Reset",   "Presne 100b → skóre sa resetuje na 90b"),
            ("90b+",    "Nad 90b sa horníci nepočítajú (0b)"),
        ]
        for badge, text in specials:
            b = self.font_small.render(f"[{badge}]", True, COLOR_GOLD)
            t = self.font_small.render(text, True, COLOR_WHITE)
            self.screen.blit(b, (col2_x, cy))
            self.screen.blit(t, (col2_x + b.get_width() + 10, cy))
            cy += 26

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
            surf = self.font_small.render(line, True, COLOR_WHITE)
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

    def __repr__(self) -> str:
        return f"InfoOverlay(visible={self.visible})"