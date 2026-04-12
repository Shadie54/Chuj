# gui/info_overlay.py

import pygame
import os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    SUIT_ICONS_PATH,
    COLOR_BUTTON_SECONDARY, CARDS_MEDIUM_PATH, CARD_SIZE_MEDIUM
)


class InfoOverlay:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.visible = False
        self.font_small = pygame.font.SysFont(None, 36)
        self.font_medium = pygame.font.SysFont(None, 48)
        self.font_large = pygame.font.SysFont(None, 64)
        self._card_cache: dict[str, pygame.Surface] = {}
        self._icon_cache: dict[str, pygame.Surface] = {}

        # Rozmery overlay — celá obrazovka
        self.overlay_w = SCREEN_WIDTH
        self.overlay_h = SCREEN_HEIGHT
        self.overlay_x = 0
        self.overlay_y = 0

        # Tlačidlo zavrieť — pravý horný roh
        self.btn_close = pygame.Rect(
            SCREEN_WIDTH - 60,
            20,
            40, 40
        )

        self.active_tab = "bodovanie"    # "bodovanie" alebo "pravidla"

        # Záložky
        tab_w = 200
        tab_h = 45
        center_x = SCREEN_WIDTH // 2
        self.tab_bodovanie = pygame.Rect(
            center_x - tab_w - 10,
            80,
            tab_w, tab_h
        )
        self.tab_pravidla = pygame.Rect(
            center_x + 10,
            80,
            tab_w, tab_h
        )

        self.content_y = 145

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def toggle(self):
        self.visible = not self.visible

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Spracuje udalosť.
        Vracia True ak overlay zachytil event.
        """
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_i:
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
            # Klik mimo overlay — zavri
            overlay_rect = pygame.Rect(
                self.overlay_x, self.overlay_y,
                self.overlay_w, self.overlay_h
            )
            if not overlay_rect.collidepoint(event.pos):
                self.hide()
                return True
            return True  # Blokuj klikanie cez overlay

        return False

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self):
        if not self.visible:
            return

        # Tmavý overlay celej obrazovky
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 240))
        self.screen.blit(dark, (0, 0))

        # Nadpis
        title = self.font_large.render("PRAVIDLÁ A BODOVANIE", True, COLOR_GOLD)
        title_rect = title.get_rect(
            centerx=SCREEN_WIDTH // 2,
            top=20
        )
        self.screen.blit(title, title_rect)

        # Zlatá čiara pod nadpisom
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (100, 65), (SCREEN_WIDTH - 100, 65),
            width=1
        )

        # Tlačidlo zavrieť
        pygame.draw.rect(self.screen, COLOR_BUTTON_SECONDARY,
                        self.btn_close, border_radius=6)
        pygame.draw.rect(self.screen, COLOR_GOLD,
                        self.btn_close, width=2, border_radius=6)
        x_surf = self.font_medium.render("✕", True, COLOR_WHITE)
        self.screen.blit(x_surf, x_surf.get_rect(center=self.btn_close.center))

        # Záložky
        self._draw_tabs()

        # Obsah podľa aktívnej záložky
        if self.active_tab == "bodovanie":
            self._draw_card_values()
            self._draw_trump_values()
        else:
            self._draw_rules()

    def _draw_tabs(self):
        """Nakreslí záložky Bodovanie / Pravidlá."""
        for tab, label in (
            (self.tab_bodovanie, "Bodovanie"),
            (self.tab_pravidla, "Pravidlá"),
        ):
            active = (
                (label == "Bodovanie" and self.active_tab == "bodovanie") or
                (label == "Pravidlá" and self.active_tab == "pravidla")
            )
            bg_color = (40, 28, 10) if active else (20, 12, 5)
            pygame.draw.rect(self.screen, bg_color, tab, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_GOLD, tab, width=2, border_radius=6)
            text_color = COLOR_GOLD if active else COLOR_GRAY
            surf = self.font_small.render(label, True, text_color)
            self.screen.blit(surf, surf.get_rect(center=tab.center))

    def _draw_card_values(self):
        """Bodovanie kariet — všetky hodnoty srdce od najvyššej."""
        ranks_ordered = ["ace", "ten", "king", "over", "under", "nine", "eight", "seven"]
        points = {"ace": 11, "ten": 10, "king": 4, "over": 3, "under": 2,
                  "nine": 0, "eight": 0, "seven": 0}

        card_w, card_h = 130, 210
        spacing = 20
        total_w = len(ranks_ordered) * (card_w + spacing) - spacing
        x_start = SCREEN_WIDTH // 2 - total_w // 2
        y = self.content_y + 20

        for i, rank in enumerate(ranks_ordered):
            cx = x_start + i * (card_w + spacing)

            # Obrázok karty
            img = self._load_card("heart", rank)
            if img:
                img = pygame.transform.scale(img, (card_w, card_h))
                self.screen.blit(img, (cx, y))

            # Body
            pts = points[rank]
            color = COLOR_GOLD if pts > 0 else COLOR_GRAY
            pts_surf = self.font_medium.render(str(pts), True, color)
            pts_rect = pts_surf.get_rect(
                centerx=cx + card_w // 2,
                top=y + card_h + 8
            )
            self.screen.blit(pts_surf, pts_rect)

    def _draw_trump_values(self):
        """Hodnoty tromfov — páry od žaluďa po srdce."""
        trump_data = [
            ("acorn", 100),
            ("leaf", 80),
            ("bell", 60),
            ("heart", 40),
        ]

        card_w, card_h = 130, 210
        pair_w = card_w * 2 + 10
        spacing = 60
        total_w = len(trump_data) * (pair_w + spacing) - spacing
        x_start = SCREEN_WIDTH // 2 - total_w // 2

        # Oddeľovacia čiara
        sep_y = self.content_y + 210 + 70
        pygame.draw.line(
            self.screen, COLOR_GRAY,
            (100, sep_y), (SCREEN_WIDTH - 100, sep_y),
            width=1
        )

        y = sep_y + 20

        for i, (suit, points) in enumerate(trump_data):
            cx = x_start + i * (pair_w + spacing)

            # Kráľ
            king_img = self._load_card(suit, "king")
            if king_img:
                king_img = pygame.transform.scale(king_img, (card_w, card_h))
                self.screen.blit(king_img, (cx, y))

            # Horník
            over_img = self._load_card(suit, "over")
            if over_img:
                over_img = pygame.transform.scale(over_img, (card_w, card_h))
                self.screen.blit(over_img, (cx + card_w + 10, y))

            # Body
            pts_surf = self.font_large.render(str(points), True, COLOR_GOLD)
            pts_rect = pts_surf.get_rect(
                centerx=cx + pair_w // 2,
                top=y + card_h + 8
            )
            self.screen.blit(pts_surf, pts_rect)

    def _draw_rules(self):
        """Nakreslí pravidlá hry."""

        sections = [
            ("CIEĽ HRY", [
                "Prvý hráč ktorý dosiahne 1000 bodov vyhráva.",
            ]),
            ("PRIEBEH KOLA", [
                "1. Rozdanie — každý dostane 10 kariet, 2 idú do talonu",
                "2. Dražba — hráči dražia kto zoberie talon (min. 50)",
                "3. Talon — víťaz zoberie 2 karty, zahodí 2",
                "   (nemožno zahodiť eso ani desiatku)",
                "4. Štychy — hráči hrajú 10 štychov",
                "5. Bodovanie — víťaz musí splniť povinnosť",
            ]),
            ("DRAŽBA", [
                "• Hráč s povinnosťou (P) začína automaticky na 50",
                "• Každý môže pridávať po 10 alebo pasovať",
                "• Kto vydraží, zoberie talon a môže navýšiť povinnosť",
                "• Ak nikto nepridá, povinnosť berie hráč (P) za 50",
            ]),
            ("ŠTYCHY", [
                "• Leader zahrá ľubovoľnú kartu",
                "• Ostatní MUSIA zahrať kartu rovnakej farby",
                "• Ak nemáš farbu — MUSÍŠ zahrať tromfovú farbu",
                "• Ak nemáš ani farbu ani tromf — zahraj čokoľvek",
                "• Vyššia karta v hranej farbe vyhráva štych",
                "• Tromfová karta bije všetky ostatné farby",
                "• Víťaz štychu začína ďalší štych",
            ]),
            ("TROMFY", [
                "• Tromf = kráľ + horník (K+Q) rovnakej farby na ruke",
                "• Hlásiť môžeš až od 2. štychu",
                "• Musíš byť leader (začínať štych)",
                "• Tromf nahlásiš vynesením kráľa ALEBO horníka",
                "• Tromfová farba sa stáva najsilnejšou",
                "• Tromf môže byť zmenený zahlásením nového tromfu",
            ]),
            ("BODOVANIE", [
                "• Víťaz dražby MUSÍ nazbierať aspoň toľko bodov",
                "  koľko vydražil (povinnosť)",
                "• Splnil povinnosť = dostane body rovné povinnosti",
                "• Nesplnil = odpočítajú sa mu body povinnosti",
                "• Ostatní hráči vždy dostanú zaokrúhlené body",
                "• Body: A=11, 10=10, K=4, Q=3, J=2",
                "• Body za tromf sa pripočítajú automaticky",
            ]),
        ]

        # 2 stĺpce
        col_w = (SCREEN_WIDTH - 120) // 2
        col1_x = 60
        col2_x = 60 + col_w + 40
        y = self.content_y + 10

        # Rozdeľ sekcie do 2 stĺpcov
        col1_sections = sections[:3]  # Cieľ, Priebeh, Dražba
        col2_sections = sections[3:]  # Štychy, Tromfy, Bodovanie

        for col_x, col_sections in [(col1_x, col1_sections), (col2_x, col2_sections)]:
            cy = y
            for title, lines in col_sections:
                # Nadpis sekcie
                title_surf = self.font_medium.render(title, True, COLOR_GOLD)
                self.screen.blit(title_surf, (col_x, cy))
                cy += 28

                # Oddeľovacia čiara pod nadpisom
                pygame.draw.line(
                    self.screen, COLOR_GOLD,
                    (col_x, cy), (col_x + col_w, cy),
                    width=1
                )
                cy += 8

                # Riadky
                for line in lines:
                    surf = self.font_small.render(line, True, COLOR_WHITE)
                    self.screen.blit(surf, (col_x, cy))
                    cy += 22

                cy += 15  # Medzera medzi sekciami

    # ------------------------------------------------------------------
    # Načítanie obrázkov
    # ------------------------------------------------------------------

    def _load_card(self, suit: str, rank: str) -> pygame.Surface | None:
        """Načíta obrázok karty (medium)."""
        key = f"{suit}-{rank}"
        if key not in self._card_cache:
            path = os.path.join(CARDS_MEDIUM_PATH, f"{suit}-{rank}.png")  # ← medium
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, CARD_SIZE_MEDIUM)  # ← medium
                self._card_cache[key] = img
            except FileNotFoundError:
                self._card_cache[key] = None
        return self._card_cache[key]

    def _load_icon(self, suit: str, size: int) -> pygame.Surface | None:
        """Načíta ikonku farby."""
        key = f"{suit}-{size}"
        if key not in self._icon_cache:
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@medium.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, (size, size))
                self._icon_cache[key] = img
            except FileNotFoundError:
                self._icon_cache[key] = None
        return self._icon_cache[key]

    def __repr__(self) -> str:
        return f"InfoOverlay(visible={self.visible})"