# gui/menu.py
#
# Hlavné menu. Od reworku rozlíšení (krok 4, claude/11_RESOLUTION_REWORK_
# ANALYSIS.md) kreslí cez gui/canvas.py — v logických súradniciach
# (1920×1080/1200, rovnaké čísla ako predtým), ale priamo v natívnom
# rozlíšení okna: ostrý text aj karty na 4K, pozadie stola aj v pásmach
# pri 21:9.
#
# Všetko okrem tlačidiel (pozadie, stmavenie, karty, logo) sa kreslí raz
# do statickej vrstvy (gui/canvas.py::StaticLayer) — každú snímku sa len
# blitne a navrch sa nakreslia tlačidlá s hoverom. Predtým sa pri každej
# snímke alokovali dva povrchy cez celú obrazovku (pri 4K ~10 ms).

import pygame
import sys
import random
import os
from gui import display
from gui.canvas import LSurf, StaticLayer
from gui.ui_style import (
    BTN_RADIUS, BTN_TIERS, BTN_BORDER_HOVER, BTN_TEXT_HOVER,
    apply_lighting as _apply_lighting,
    apply_center_shade as _apply_center_shade,
    blit_soft_ellipse as _blit_soft_ellipse,
)
from config import (
    SCREEN_WIDTH,
    COLOR_GOLD,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM,
    CARD_SIZE_MEDIUM,
    SUITS, RANKS,
)

BG_PATH = os.path.join("assets", "graphics", "table.jpg")
LOGO_PATH = os.path.join("assets", "graphics", "chuj_logo.png")
LOGO_W = 560

# --- Vzhľad (grafický rework menu, 2026-10-27) ---------------------------
# Elegantné tmavšie prevedenie: stôl s mäkkým stmavením do stredu a k
# okrajom, teplé svetlo hore v strede, karty len vľavo a vpravo s tieňom,
# logo na tmavej plakete, tmavé tlačidlá so zlatohnedým rámom.

# Osvetlenie stola, farby tlačidiel a pomocné kreslenie sú spoločné pre
# všetky obrazovky mimo hry — gui/ui_style.py.

# Karty v pozadí — počet, mierka a stredová zóna, kam nesmú zasahovať
# (polovica šírky od stredu obrazovky: plaketa loga ~280 + rezerva).
BG_CARD_COUNT = 10
BG_CARD_SCALE = 0.8
BG_CARD_SAFE_HALF_W = 310
BG_CARD_MARGIN = 30
CARD_SHADOW_OFFSET = (7, 10)       # logické px — svetlo zľava hore
CARD_SHADOW_ALPHA = 140
# Jemné "zostarnutie" bielej karty do krémova a stlmenie jasu (násobenie
# farby) — karty na tmavom stole inak pôsobia príliš žiarivo.
CARD_TINT = (236, 226, 206)

# Tlačidlá
BTN_W, BTN_H, BTN_GAP = 340, 60, 16
BTN_START_Y = 430
# Úrovne tlačidiel (ui_style.BTN_TIERS): 1 = Pokračovať (bez rozohratej hry
# Nová hra), 2 = Nová hra a Tutoriál, 3 = Profil, Nastavenia, Koniec.

# Plaketa pod logom — vnútro ozdobného rámu (zlomky rozmeru chuj_logo.png
# 864×289: rám siaha od x≈12 po 852, y≈30 po 260, rohy zrezané ~24 px).
LOGO_PLATE = (14 / 864, 32 / 289, 850 / 864, 258 / 289, 26 / 864)
LOGO_PLATE_COLOR = (16, 11, 7)


class Menu:
    def __init__(self, screen: pygame.Surface, show_continue: bool = False):
        # `screen` (logický povrch) sa už nepoužíva — kreslí sa cez Canvas
        # nad oknom. Parameter ostáva kvôli volajúcim (main.py).
        self.screen = screen
        self.canvas = display.canvas()
        self.clock = pygame.time.Clock()
        self.show_continue = show_continue

        self.font_button = self.canvas.font(FONT_SIZE_LARGE)
        self.font_medium = self.canvas.font(FONT_SIZE_MEDIUM)

        self.has_bg = os.path.exists(BG_PATH)

        try:
            raw = pygame.image.load(LOGO_PATH)
            logo_h = int(LOGO_W * (raw.get_height() / raw.get_width()))
            self.logo = self.canvas.image(LOGO_PATH, (LOGO_W, logo_h))
        except (FileNotFoundError, pygame.error):
            self.logo = None

        self.bg_cards = self._generate_bg_cards()
        self._layer: StaticLayer | None = None

        btn_w, btn_h = BTN_W, BTN_H
        step = BTN_H + BTN_GAP
        center_x = SCREEN_WIDTH // 2

        buttons_data = []
        if show_continue:
            buttons_data.append(("Pokračovať", "continue", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Nová hra", "new_game", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Tutoriál", "tutorial", COLOR_BUTTON_PRIMARY))
        buttons_data.append(("Profil", "profile", COLOR_BUTTON_SECONDARY))
        buttons_data.append(("Nastavenia", "settings", COLOR_BUTTON_SECONDARY))
        buttons_data.append(("Koniec", "quit", COLOR_BUTTON_SECONDARY))

        # Blok logo + tlačidlá je zvislo na strede — pri 16:10 (logická
        # výška 1200) sa posunie o polovicu extra výšky nadol.
        start_y = BTN_START_Y + (display.logical_height() - 1080) // 2
        # Bez "Pokračovať" je tlačidiel o jedno menej — blok ostane na strede.
        start_y += (6 - len(buttons_data)) * step // 2
        # Po pribudnutí tlačidiel "Profil" a "Tutoriál" je v menu až 6
        # položiek — na nižšom rozlíšení by posledná vypadla pod okraj,
        # preto blok v takom prípade posunieme nahor. Na 1080p sa nič
        # nemení. (Od reworku rozlíšení je logická výška vždy ≥ 1080,
        # takže sa to v praxi neuplatní — poistka ostáva.)
        last_bottom = start_y + (len(buttons_data) - 1) * step + btn_h
        if last_bottom > display.logical_height() - 40:
            start_y -= last_bottom - (display.logical_height() - 40)

        self.buttons = []
        for i, (label, action, color) in enumerate(buttons_data):
            self.buttons.append({
                "label": label,
                "action": action,
                "rect": pygame.Rect(
                    center_x - btn_w // 2,
                    start_y + i * step,
                    btn_w, btn_h
                ),
                "color": color,
                "tier": 1 if i == 0 else (2 if action in ("new_game", "tutorial") else 3),
                "hover": False
            })

    def _generate_bg_cards(self) -> list[dict]:
        """Vygeneruje náhodne rozhodené karty pre pozadie.

        Mechanizmus ostáva (náhodný výber kariet, uhol, pozícia s
        opakovanými pokusmi), ale karty sa striedavo kladú do ľavej a pravej
        zóny mimo stredu s logom a tlačidlami a celé ostávajú na obrazovke.
        Čiastočné prekrytie kariet je povolené (ako na skutočnom stole)."""
        cards = []
        used_positions = []
        card_names = [
            f"{suit}-{rank}.png"
            for suit in SUITS for rank in RANKS
        ]
        selected = random.sample(card_names, BG_CARD_COUNT)
        w, h = CARD_SIZE_MEDIUM
        size = (int(w * BG_CARD_SCALE), int(h * BG_CARD_SCALE))
        width, height = SCREEN_WIDTH, display.logical_height()
        center_x = width // 2

        per_side = (BG_CARD_COUNT + 1) // 2
        for i, filename in enumerate(selected):
            try:
                angle = random.uniform(-35, 35)
                img = self.canvas.card(filename, angle=angle, lsize=size).copy()
                img.phys.fill(CARD_TINT, special_flags=pygame.BLEND_RGB_MULT)
                lw, lh = img.get_size()
                if i % 2 == 0:      # ľavá zóna
                    x_min = BG_CARD_MARGIN
                    x_max = center_x - BG_CARD_SAFE_HALF_W - lw
                else:               # pravá zóna
                    x_min = center_x + BG_CARD_SAFE_HALF_W
                    x_max = width - BG_CARD_MARGIN - lw
                y_min, y_max = BG_CARD_MARGIN, height - BG_CARD_MARGIN - lh
                # Každá karta danej strany dostane svoj zvislý pás (s
                # presahom) — karty sa rozložia po celej výške, nezhluknú sa.
                band = (y_max - y_min) / per_side
                slot = i // 2
                y_lo = max(y_min, round(y_min + (slot - 0.35) * band))
                y_hi = min(y_max, round(y_min + (slot + 1.35) * band))

                attempts = 0
                x, y = x_min, y_min
                while attempts < 20:
                    x = random.randint(x_min, max(x_min, x_max))
                    y = random.randint(y_lo, max(y_lo, y_hi))
                    too_close = any(
                        abs(x - p[0]) < 110 and abs(y - p[1]) < 170
                        for p in used_positions
                    )
                    if not too_close:
                        break
                    attempts += 1
                used_positions.append((x, y))

                cards.append({"image": img, "x": x, "y": y,
                              "shadow": self._card_shadow(img)})
            except (FileNotFoundError, pygame.error):
                continue

        return cards

    def _card_shadow(self, card) -> tuple:
        """Mäkký tieň karty: čierna silueta s alfou karty, rozmazaná
        zmenšením a zväčšením (lacné, počíta sa raz pri otvorení menu).
        Vráti (LSurf, logický posun ľavého horného rohu voči karte)."""
        c = self.canvas
        src = card.phys
        k = 8                                   # miera rozmazania
        pad = max(4, round(14 * c.s))
        pw, ph = src.get_width() + 2 * pad, src.get_height() + 2 * pad
        # Silueta sa robí rovno v zmenšenej veľkosti (pri 4K rádovo
        # rýchlejšie než maskovať plnú kartu) a potom sa zväčší = rozmaže.
        sw, sh = max(1, pw // k), max(1, ph // k)
        small = pygame.Surface((sw, sh), pygame.SRCALPHA)
        small.blit(pygame.transform.smoothscale(
            src, (max(1, src.get_width() // k), max(1, src.get_height() // k))),
            (pad // k, pad // k))
        small.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGB_MIN)
        small.fill((255, 255, 255, CARD_SHADOW_ALPHA),
                   special_flags=pygame.BLEND_RGBA_MULT)
        blurred = pygame.transform.smoothscale(small, (pw, ph))
        shadow = LSurf(blurred, round(pw / c.s), round(ph / c.s))
        off = (CARD_SHADOW_OFFSET[0] - pad / c.s,
               CARD_SHADOW_OFFSET[1] - pad / c.s)
        return shadow, off

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = display.mouse_pos()

            for event in display.get_events():
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
            display.present()

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                return btn["action"]
        return None

    def _update_hover(self, mouse_pos: tuple[int, int]):
        for btn in self.buttons:
            btn["hover"] = btn["rect"].collidepoint(mouse_pos)

    def _draw(self):
        c = self.canvas
        if self._layer is None:
            self._layer = StaticLayer(c.target.get_size())
        if self._layer.needs_redraw("static"):
            with self._layer.drawing(c, key="static"):
                self._draw_static()
        self._layer.blit_to(c.target)
        # Tlačidlá v pokojovom stave sú už vo vrstve, každú snímku sa
        # dokreslí len zvýraznenie tlačidla pod myšou.
        for btn in self.buttons:
            if btn["hover"]:
                self._draw_button_hover(btn)

    def _draw_static(self):
        """Pozadie, svetlo, karty a logo — nemenia sa medzi snímkami."""
        c = self.canvas
        if self.has_bg:
            c.target.blit(c.background(BG_PATH, c.target.get_size()), (0, 0))
        else:
            c.fill_window((45, 28, 15))

        _apply_lighting(c.target)

        for card in self.bg_cards:
            shadow, (dx, dy) = card["shadow"]
            c.blit(shadow, (card["x"] + dx, card["y"] + dy))
            c.blit(card["image"], (card["x"], card["y"]))

        # Mäkké stmavenie stredu až NAD kartami — prípadný roh karty pri
        # strede tak splynie so šerom (bez ostrých hraníc pásu).
        _apply_center_shade(c.target)

        # Jemná zlatá žiara za hlavným tlačidlom (statická — nemení sa
        # s hoverom, preto patrí do statickej vrstvy).
        main_btn = self.buttons[0]["rect"]
        _blit_soft_ellipse(c, main_btn.inflate(140, 70), (255, 190, 90), 40,
                           additive=True)

        self._draw_logo()
        for btn in self.buttons:
            self._draw_button(btn)

    def _draw_logo(self):
        c = self.canvas
        logo_bottom_padding = 48
        first_btn_y = self.buttons[0]["rect"].top

        if self.logo:
            logo_rect = self.logo.get_rect(
                centerx=SCREEN_WIDTH // 2,
                bottom=first_btn_y - logo_bottom_padding
            )
            self._draw_logo_plate(logo_rect)
            c.blit(self.logo, logo_rect)
        else:
            font_title = c.font(120)
            shadow = font_title.render("CHUJ", True, (0, 0, 0))
            title = font_title.render("CHUJ", True, COLOR_GOLD)
            rect = title.get_rect(
                centerx=SCREEN_WIDTH // 2,
                bottom=first_btn_y - logo_bottom_padding
            )
            c.blit(shadow, (rect.x + 3, rect.y + 3))
            c.blit(title, rect)

    def _draw_logo_plate(self, logo_rect: pygame.Rect):
        """Tmavá plaketa vo vnútri ozdobného rámu loga (zrezané rohy ako
        rám), pod ňou mäkký tieň a jemná teplá žiara."""
        c = self.canvas
        fx0, fy0, fx1, fy1, fcut = LOGO_PLATE
        x0 = logo_rect.x + fx0 * logo_rect.width
        y0 = logo_rect.y + fy0 * logo_rect.height
        x1 = logo_rect.x + fx1 * logo_rect.width
        y1 = logo_rect.y + fy1 * logo_rect.height
        cut = fcut * logo_rect.width
        points = [(x0 + cut, y0), (x1 - cut, y0), (x1, y0 + cut),
                  (x1, y1 - cut), (x1 - cut, y1), (x0 + cut, y1),
                  (x0, y1 - cut), (x0, y0 + cut)]

        # žiara + tieň (rozmazaný obdĺžnik okolo plakety)
        glow_rect = pygame.Rect(round(x0) - 90, round(y0) - 70,
                                round(x1 - x0) + 180, round(y1 - y0) + 140)
        _blit_soft_ellipse(c, glow_rect, (255, 196, 100), 34, additive=True)
        shadow_rect = pygame.Rect(round(x0) - 24, round(y0) - 8,
                                  round(x1 - x0) + 48, round(y1 - y0) + 40)
        _blit_soft_ellipse(c, shadow_rect, (0, 0, 0), 150, additive=False,
                           square=True)

        c.polygon(LOGO_PLATE_COLOR, points)
        # jemné presvetlenie hornej polovice plakety
        c.overlay((x0 + cut, y0 + 2, x1 - x0 - 2 * cut,
                   (y1 - y0) * 0.45), (255, 220, 160, 9))

    def _draw_button(self, btn: dict):
        """Tlačidlo v pokojovom stave (kreslí sa do statickej vrstvy)."""
        c = self.canvas
        rect = btn["rect"]
        fill, highlight, border, text_color = BTN_TIERS[btn["tier"]]

        # tieň pod tlačidlom
        c.overlay(rect.move(0, 4), (0, 0, 0, 110), border_radius=BTN_RADIUS)
        c.overlay(rect, fill, border_radius=BTN_RADIUS)
        # vnútorné presvetlenie hornej polovice (najvýraznejšie pri úrovni 1)
        top = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, rect.height // 2 - 2)
        c.overlay(top, (255, 214, 140, highlight), border_radius=BTN_RADIUS - 2)
        c.rect(border, rect, width=2, border_radius=BTN_RADIUS)
        self._draw_button_label(btn, text_color)

    def _draw_button_hover(self, btn: dict):
        """Zvýraznenie pod myšou — kreslí sa každú snímku NAD pokojové
        tlačidlo z vrstvy: presvetlenie, zlatý rám a zlatý text."""
        c = self.canvas
        rect = btn["rect"]
        c.overlay(rect, (255, 214, 140, 24), border_radius=BTN_RADIUS)
        c.rect(BTN_BORDER_HOVER, rect, width=2, border_radius=BTN_RADIUS)
        self._draw_button_label(btn, BTN_TEXT_HOVER)

    def _draw_button_label(self, btn: dict, color):
        text_surf = self.font_button.render(btn["label"], True, color)
        self.canvas.blit(text_surf, text_surf.get_rect(center=btn["rect"].center))

    def __repr__(self) -> str:
        return "Menu()"
