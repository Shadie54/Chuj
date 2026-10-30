# gui/stats_screen.py
#
# Profil hráča a jeho štatistiky (rework 2026-10-29 podľa návrhu usera):
#   hore  — meno + Premenovať a súhrn (odohraté hry / kolá / nedohraté),
#   stred — 6 dlaždíc-záložiek, každá s hlavným číslom,
#   dole  — podrobnosti zvolenej dlaždice (prstence, pruhy, mini-dlaždice).
#
# Všetky čísla pochádzajú z game/profile.py (compute_stats) — tu sa nič
# nepočíta, len formátuje a vykresľuje. Pozadie, dlaždice a podrobnosti sú
# statická vrstva (prekreslí sa len pri zmene záložky / mena); každú snímku
# sa kreslí len hover, pole s menom a tlačidlá.

import math
import os
import sys

import pygame

from game.profile import Stats, load_profiles, save_profiles
from gui import display
from gui.canvas import StaticLayer
from gui import ui_style
from config import (
    DECLARATION_ALL_BONUS, DECLARATION_ALL_PENALTY, DECLARATION_FAIL_PENALTY,
    DECLARATION_NONE_BONUS, NO_PENALTY_BONUS, NO_PENALTY_STREAK, RESET_SCORE,
    SCREEN_WIDTH, SHOOT_MOON_BONUS, SUIT_ICONS_PATH, WINNING_SCORE,
)

# Menovka hráča sa na dvoch miestach skracuje na 10 znakov (panel KOLO v
# gui/round_status.py a hlavička Chujogramu) — stĺpec Chujogramu je na
# viac aj priúzky. Obmedzenie držíme na rovnakej hodnote, nech platí, že
# čo si napíšeš, to aj všade uvidíš.
MAX_NAME_LEN = 10

GRAPHICS = os.path.join("assets", "graphics")

# Farby (tlmené, v duchu ui_style)
GOOD = (130, 184, 98)
BAD = (214, 104, 82)
TRACK = (52, 38, 24)               # podklad prstencov a pruhov
TILE_FILL = (17, 11, 7, 226)
TILE_ACTIVE_FILL = (58, 38, 16, 236)
DIVIDER = (70, 54, 34)
MINI_FILL = (30, 20, 12, 220)

# (kľúč, nadpis) — poradie dlaždíc
TABS = (
    ("balance", "BILANCIA"),
    ("clean", "ČISTÉ KOLÁ"),
    ("points", "TRESTNÉ BODY"),
    ("illum", "VYSVIETENIA"),
    ("special", "ŠPECIALITY"),
    ("records", "REKORDY"),
)

# Rozloženie (logické px, šírka 1920)
CONTENT_W = 1700
TOP_Y = 136
HEADER_H = 92
TILES_GAP = 18
TILE_H = 150
TILE_GAP = 16
DETAIL_GAP = 22


# ----------------------------------------------------------------------
# Formátovanie (slovenská desatinná čiarka)
# ----------------------------------------------------------------------

def fmt_num(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def fmt_pct(v: float, d: int = 0) -> str:
    return f"{fmt_num(v, d)} %"


def share(part: float, whole: float) -> float:
    return part / whole * 100 if whole else 0.0


def plural(n: int, one: str, few: str, many: str) -> str:
    """1 hra / 2–4 hry / 5 hier."""
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


class StatsScreen:
    def __init__(self, screen: pygame.Surface):
        # `screen` (logický povrch) sa nepoužíva — kreslí sa cez Canvas.
        self.screen = screen
        self.canvas = display.canvas()
        self._layer: StaticLayer | None = None
        self._rings: dict = {}
        self.clock = pygame.time.Clock()

        c = self.canvas
        self.font_title = c.font(60)
        self.font_tile_title = c.font(20)
        self.font_tile_value = c.font(50)
        self.font_tile_caption = c.font(19)
        self.font_head = c.font(24)
        self.font_label = c.font(21)
        self.font_value = c.font(30)
        self.font_big = c.font(44)
        self.font_button = c.font(24)
        self.font_small = c.font(18)

        self.profiles, self.active = load_profiles()
        self.profile = self.profiles[self.active]
        self.stats: Stats = self.profile.stats()

        self.active_tab = "balance"
        self.per_game = False          # Trestné body: Za kolo / Za hru

        # Premenovanie profilu — kliknutím na pole alebo Premenovať.
        # Esc zruší, Enter potvrdí.
        self.editing_name = False
        self.name_buffer = ""
        self._caret_timer = 0

        self._build_layout()

    def set_profile(self, profile):
        """Zobrazí iný profil (galéria / testy s falošnými dátami)."""
        self.profile = profile
        self.stats = profile.stats()
        if self._layer:
            self._layer.invalidate()

    # ------------------------------------------------------------------
    # Rozloženie
    # ------------------------------------------------------------------

    def _build_layout(self):
        cx = SCREEN_WIDTH // 2
        left = cx - CONTENT_W // 2
        self.content_left = left

        self.header_rect = pygame.Rect(left, TOP_Y, CONTENT_W, HEADER_H)
        self.name_field = pygame.Rect(left + 140, TOP_Y + 22, 300, 48)
        self.rename_button = {
            "rect": pygame.Rect(self.name_field.right + 18, TOP_Y + 22, 190, 48),
            "hover": False,
        }

        tiles_top = self.header_rect.bottom + TILES_GAP
        tile_w = (CONTENT_W - TILE_GAP * (len(TABS) - 1)) // len(TABS)
        self.tile_rects = {
            key: pygame.Rect(left + i * (tile_w + TILE_GAP), tiles_top,
                             tile_w, TILE_H)
            for i, (key, _title) in enumerate(TABS)
        }
        self.tile_hover: str | None = None

        l_h = display.logical_height()
        self.back_button = {
            "rect": pygame.Rect(cx - 150, l_h - 74, 300, 50),
            "hover": False,
        }
        detail_top = tiles_top + TILE_H + DETAIL_GAP
        self.detail_rect = pygame.Rect(
            left, detail_top, CONTENT_W,
            self.back_button["rect"].top - 20 - detail_top)

        # Prepínač Za kolo / Za hru (len záložka Trestné body)
        r = self.detail_rect
        self.per_buttons = {
            False: {"rect": pygame.Rect(r.right - 32 - 2 * 150 - 10, r.top + 14,
                                        150, 40), "hover": False},
            True: {"rect": pygame.Rect(r.right - 32 - 150, r.top + 14,
                                       150, 40), "hover": False},
        }

    # ------------------------------------------------------------------
    # Slučka
    # ------------------------------------------------------------------

    def run(self) -> str:
        while True:
            self.clock.tick(60)
            mouse_pos = display.mouse_pos()

            for event in display.get_events():
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
                    if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        self._step_tab(-1 if event.key == pygame.K_LEFT else 1)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self._handle_click(event.pos) == "back":
                        return "menu"

            self._update_hover(mouse_pos)
            self._draw()
            display.present()

    def _update_hover(self, pos):
        self.back_button["hover"] = self.back_button["rect"].collidepoint(pos)
        self.rename_button["hover"] = self.rename_button["rect"].collidepoint(pos)
        self.tile_hover = next((k for k, r in self.tile_rects.items()
                                if r.collidepoint(pos)), None)
        for btn in self.per_buttons.values():
            btn["hover"] = (self.active_tab == "points"
                            and btn["rect"].collidepoint(pos))

    def _step_tab(self, step: int):
        keys = [k for k, _t in TABS]
        i = keys.index(self.active_tab)
        self.active_tab = keys[(i + step) % len(keys)]

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

        for key, rect in self.tile_rects.items():
            if rect.collidepoint(pos):
                self.active_tab = key
                return None
        if self.active_tab == "points":
            for per_game, btn in self.per_buttons.items():
                if btn["rect"].collidepoint(pos):
                    self.per_game = per_game
                    return None
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
    # Kreslenie — rámec
    # ------------------------------------------------------------------

    def _draw(self):
        c = self.canvas
        if self._layer is None:
            self._layer = StaticLayer(c.target.get_size())
        key = ("static", self.active_tab, self.per_game, self.stats.games)
        if self._layer.needs_redraw(key):
            with self._layer.drawing(c, key=key):
                ui_style.draw_backdrop(c)
                ui_style.draw_screen_title(c, "PROFIL HRÁČA", self.font_title,
                                           (SCREEN_WIDTH // 2, 62),
                                           line_half_w=240, line_gap=40)
                self._draw_header_static()
                for k, title in TABS:
                    self._draw_tile(k, title)
                ui_style.draw_panel(c, self.detail_rect)
                self._draw_detail()
        self._layer.blit_to(c.target)

        # Dynamické: hover dlaždice, meno, tlačidlá
        if self.tile_hover and self.tile_hover != self.active_tab:
            c.rect(ui_style.BTN_BORDER_HOVER, self.tile_rects[self.tile_hover],
                   width=2, border_radius=ui_style.PANEL_RADIUS)
        self._draw_name_field()
        ui_style.draw_button(c, self.rename_button["rect"],
                             "Hotovo" if self.editing_name else "Premenovať",
                             self.font_button, 1 if self.editing_name else 2,
                             self.rename_button["hover"])
        if self.active_tab == "points":
            for per_game, label in ((False, "Za kolo"), (True, "Za hru")):
                btn = self.per_buttons[per_game]
                ui_style.draw_button(c, btn["rect"], label, self.font_label,
                                     1 if self.per_game == per_game else 3,
                                     btn["hover"], shadow=False)
        ui_style.draw_button(c, self.back_button["rect"], "Späť do menu",
                             self.font_button, 3, self.back_button["hover"])

    # --- hlavička ------------------------------------------------------

    def _draw_header_static(self):
        c = self.canvas
        r = self.header_rect
        ui_style.draw_panel(c, r)
        label = self.font_head.render("MENO", True, ui_style.GOLD)
        c.blit(label, label.get_rect(midleft=(r.left + 32, r.centery)))

        s = self.stats
        items = [("Odohraté hry", str(s.games)),
                 ("Odohrané kolá", str(s.rounds))]
        if s.abandoned:
            items.append(("Nedohraté hry", str(s.abandoned)))
        x = r.right - 36
        for i, (text, value) in enumerate(reversed(items)):
            v = self.font_value.render(value, True, ui_style.TEXT)
            t = self.font_label.render(text, True, ui_style.TEXT_DIM)
            v_rect = v.get_rect(midright=(x, r.centery))
            c.blit(v, v_rect)
            t_rect = t.get_rect(midright=(v_rect.left - 14, r.centery))
            c.blit(t, t_rect)
            x = t_rect.left - 30
            if i < len(items) - 1:
                c.line(DIVIDER, (x + 15, r.top + 22), (x + 15, r.bottom - 22))
        # oddeľovač medzi menom a súhrnom
        sep_x = self.rename_button["rect"].right + 30
        c.line(DIVIDER, (sep_x, r.top + 18), (sep_x, r.bottom - 18))

    def _draw_name_field(self):
        c = self.canvas
        active = self.editing_name
        c.rect((10, 7, 4), self.name_field, border_radius=8)
        c.rect(ui_style.GOLD if active else ui_style.GOLD_SOFT,
               self.name_field, width=2, border_radius=8)
        text = self.name_buffer if active else self.profile.name
        surf = self.font_value.render(text, True, ui_style.TEXT)
        c.blit(surf, surf.get_rect(midleft=(self.name_field.left + 14,
                                            self.name_field.centery)))
        if active:
            self._caret_timer = (self._caret_timer + 1) % 60
            if self._caret_timer < 30:
                x = self.name_field.left + 16 + surf.get_width() + 2
                c.line(ui_style.TEXT, (x, self.name_field.top + 10),
                       (x, self.name_field.bottom - 10), width=2)

    # --- dlaždice ------------------------------------------------------

    def _tile_headline(self, key: str) -> tuple[str, str, tuple]:
        """(hlavné číslo, popis pod ním, farba čísla)."""
        s = self.stats
        if not s.games:
            return "—", "zatiaľ bez hier", ui_style.TEXT_DIM
        if key == "balance":
            return fmt_pct(s.win_rate, 1), "neprehraté hry", ui_style.GOLD
        if key == "clean":
            return fmt_pct(s.clean_rate, 1), "kôl bez trestného bodu", GOOD
        if key == "points":
            return (fmt_num(s.card_points / s.rounds if s.rounds else 0, 2),
                    "bodov za kolo (za karty)", ui_style.TEXT)
        if key == "illum":
            if not s.illuminated:
                return "—", "zatiaľ nevysvietené", ui_style.TEXT_DIM
            return fmt_pct(s.illumination_success), "úspešnosť vysvietení", GOOD
        if key == "special":
            return str(s.special_ok), "úspešných akcií", ui_style.GOLD
        return (str(s.longest_clean_streak), "najdlhšia čistá séria (kolá)",
                ui_style.GOLD)

    def _tile_icon(self, key: str, size: int):
        c = self.canvas
        try:
            if key == "points":
                return c.image(os.path.join(SUIT_ICONS_PATH,
                                            "heart-icon@small.png"), (size, size))
            if key == "illum":
                h = size + 8
                return c.card("leaf-over.png", lsize=(round(h * 0.62), h))
            name = {"balance": "trophy.png", "clean": "ok.png",
                    "special": "all.png", "records": "scoresheet.png"}[key]
            return c.image(os.path.join(GRAPHICS, name), (size, size))
        except (pygame.error, FileNotFoundError, KeyError):
            return None

    def _draw_tile(self, key: str, title: str):
        c = self.canvas
        r = self.tile_rects[key]
        active = key == self.active_tab
        c.overlay(r.move(0, 4), (0, 0, 0, 90), border_radius=ui_style.PANEL_RADIUS)
        c.overlay(r, TILE_ACTIVE_FILL if active else TILE_FILL,
                  border_radius=ui_style.PANEL_RADIUS)
        c.overlay((r.x + 3, r.y + 3, r.width - 6, 40), (255, 214, 140, 8),
                  border_radius=ui_style.PANEL_RADIUS - 3)
        c.rect(ui_style.GOLD if active else ui_style.GOLD_SOFT, r,
               width=3 if active else 2, border_radius=ui_style.PANEL_RADIUS)

        icon = self._tile_icon(key, 30)
        t = self.font_tile_title.render(
            title, True, ui_style.GOLD if active else ui_style.TEXT_DIM)
        total_w = t.get_width() + (icon.get_width() + 10 if icon else 0)
        x = r.centerx - total_w // 2
        if icon:
            c.blit(icon, icon.get_rect(midleft=(x, r.top + 30)))
            x += icon.get_width() + 10
        c.blit(t, t.get_rect(midleft=(x, r.top + 30)))

        value, caption, color = self._tile_headline(key)
        v = self.font_tile_value.render(value, True, color)
        c.blit(v, v.get_rect(center=(r.centerx, r.top + 84)))
        cap = self.font_tile_caption.render(caption, True, ui_style.TEXT_DIM)
        c.blit(cap, cap.get_rect(center=(r.centerx, r.bottom - 22)))

        if active:
            # šípka smerom k panelu podrobností
            y = r.bottom + 4
            c.polygon(ui_style.GOLD, [(r.centerx - 12, y), (r.centerx + 12, y),
                                      (r.centerx, y + 12)])

    # ------------------------------------------------------------------
    # Kreslenie — podrobnosti
    # ------------------------------------------------------------------

    def _draw_detail(self):
        s = self.stats
        r = self.detail_rect
        title = dict(TABS)[self.active_tab]
        t = self.font_head.render(title, True, ui_style.GOLD)
        self.canvas.blit(t, t.get_rect(midleft=(r.left + 32, r.top + 34)))
        self.canvas.line(DIVIDER, (r.left + 24, r.top + 66),
                         (r.right - 24, r.top + 66))
        body = pygame.Rect(r.left + 32, r.top + 86, r.width - 64,
                           r.height - 86 - 26)
        if not s.games:
            msg = self.font_value.render(
                "Odohraj prvú hru a štatistiky sa tu objavia.", True,
                ui_style.TEXT_DIM)
            self.canvas.blit(msg, msg.get_rect(center=body.center))
            return
        getattr(self, f"_detail_{self.active_tab}")(body)

    # --- stavebné prvky -----------------------------------------------

    def _ring_surface(self, radius: int, width: int, pct: float, color):
        """Prstenec (podklad + výsek pct %) — kreslený vo vyššom rozlíšení
        a zmenšený, aby bol hladký. Cache podľa parametrov."""
        key = (radius, width, round(pct, 1), color)
        cached = self._rings.get(key)
        if cached is not None:
            return cached
        lsurf = self.canvas.new_surface((2 * radius + 2, 2 * radius + 2))
        pw, ph = lsurf.phys.get_size()
        ss = 3
        big = pygame.Surface((pw * ss, ph * ss), pygame.SRCALPHA)
        k = pw * ss / (2 * radius + 2)
        cx = cy = (radius + 1) * k
        ro, ri = radius * k, (radius - width) * k

        def sector(frac, col):
            if frac <= 0:
                return
            if frac >= 0.999:
                pygame.draw.circle(big, col, (cx, cy), ro)
                pygame.draw.circle(big, (0, 0, 0, 0), (cx, cy), ri)
                return
            n = max(8, int(180 * frac))
            outer, inner = [], []
            for i in range(n + 1):
                a = -math.pi / 2 + 2 * math.pi * frac * i / n
                outer.append((cx + ro * math.cos(a), cy + ro * math.sin(a)))
                inner.append((cx + ri * math.cos(a), cy + ri * math.sin(a)))
            pygame.draw.polygon(big, col, outer + inner[::-1])

        sector(1.0, TRACK)
        sector(max(0.0, min(pct, 100.0)) / 100, color)
        lsurf.phys.blit(pygame.transform.smoothscale(big, (pw, ph)), (0, 0))
        self._rings[key] = lsurf
        return lsurf

    def _ring(self, center, radius: int, pct: float, color, value: str,
              caption: str, width: int = 20):
        c = self.canvas
        ring = self._ring_surface(radius, width, pct, color)
        c.blit(ring, ring.get_rect(center=center))
        v = self.font_big.render(value, True, ui_style.TEXT)
        c.blit(v, v.get_rect(center=(center[0], center[1] - 8)))
        cap = self.font_small.render(caption, True, ui_style.TEXT_DIM)
        c.blit(cap, cap.get_rect(center=(center[0], center[1] + 28)))

    @staticmethod
    def _ring_y(col: pygame.Rect, extra: int, radius: int = 118) -> int:
        """Stred prstenca tak, aby prstenec + `extra` px textu pod ním
        boli zvisle vycentrované v stĺpci."""
        block = 2 * radius + extra
        return col.top + max(0, (col.height - block) // 2) + radius

    def _section_title(self, text: str, x: int, y: int):
        t = self.font_label.render(text, True, ui_style.GOLD)
        self.canvas.blit(t, (x, y))

    def _bar(self, rect: pygame.Rect, pct: float, color):
        c = self.canvas
        c.rect(TRACK, rect, border_radius=rect.height // 2)
        w = round(rect.width * max(0.0, min(pct, 100.0)) / 100)
        if w > 0:
            c.rect(color, (rect.x, rect.y, max(w, rect.height), rect.height),
                   border_radius=rect.height // 2)

    def _bar_rows(self, rect: pygame.Rect, rows, value_w: int = 150,
                  label_w: int = 200, row_h: int = 56):
        """Riadky: popis | pruh | hodnota. rows = [(popis, pct, hodnota,
        farba)]."""
        c = self.canvas
        y = rect.top
        for label, pct, value, color in rows:
            cy = y + row_h // 2
            t = self.font_label.render(label, True, ui_style.TEXT)
            c.blit(t, t.get_rect(midleft=(rect.left, cy)))
            bar = pygame.Rect(rect.left + label_w, cy - 8,
                              rect.width - label_w - value_w - 16, 16)
            self._bar(bar, pct, color)
            v = self.font_label.render(value, True, ui_style.TEXT)
            c.blit(v, v.get_rect(midright=(rect.right, cy)))
            y += row_h

    def _mini_tile(self, rect: pygame.Rect, label: str, value: str,
                   color=None, note: str = ""):
        c = self.canvas
        c.overlay(rect, MINI_FILL, border_radius=10)
        c.rect(DIVIDER, rect, width=1, border_radius=10)
        t = self.font_small.render(label, True, ui_style.TEXT_DIM)
        c.blit(t, t.get_rect(midtop=(rect.centerx, rect.top + 14)))
        v = self.font_value.render(value, True, color or ui_style.TEXT)
        c.blit(v, v.get_rect(center=(rect.centerx, rect.centery + 4)))
        if note:
            n = self.font_small.render(note, True, ui_style.TEXT_DIM)
            c.blit(n, n.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))

    def _mini_grid(self, rect: pygame.Rect, items, cols: int,
                   gap: int = 16, max_h: int = 150, center: bool = True):
        """Mriežka mini-dlaždíc. items = [(popis, hodnota, farba, pozn.)].
        Pri center=True je mriežka zvisle vycentrovaná v `rect`."""
        rows = math.ceil(len(items) / cols)
        w = (rect.width - gap * (cols - 1)) // cols
        h = min(max_h, (rect.height - gap * (rows - 1)) // rows)
        top = rect.top
        if center:
            top += (rect.height - (rows * h + (rows - 1) * gap)) // 2
        for i, item in enumerate(items):
            col, row = i % cols, i // cols
            tile = pygame.Rect(rect.left + col * (w + gap),
                               top + row * (h + gap), w, h)
            self._mini_tile(tile, *item)

    def _columns(self, body: pygame.Rect, widths: list[float],
                 gap: int = 48) -> list[pygame.Rect]:
        """Rozdelí telo na stĺpce v pomere widths a medzi ne dá čiaru."""
        total = body.width - gap * (len(widths) - 1)
        rects, x = [], body.left
        for i, w in enumerate(widths):
            cw = round(total * w / sum(widths))
            rects.append(pygame.Rect(x, body.top, cw, body.height))
            x += cw + gap
            if i < len(widths) - 1:
                lx = x - gap // 2
                self.canvas.line(DIVIDER, (lx, body.top + 4),
                                 (lx, body.bottom - 4))
        return rects

    # --- záložky ------------------------------------------------------

    def _detail_balance(self, body: pygame.Rect):
        s = self.stats
        left, mid, right = self._columns(body, [0.8, 1.25, 1.25])

        ry = self._ring_y(left, extra=110)
        self._ring((left.centerx, ry), 118, s.win_rate,
                   ui_style.GOLD, fmt_pct(s.win_rate, 1), "neprehraté hry")
        y = ry + 150
        for label, value, color in (("Neprehraté hry", s.wins, GOOD),
                                    ("Prehry (Chuj)", s.losses, BAD)):
            t = self.font_label.render(label, True, ui_style.TEXT_DIM)
            v = self.font_value.render(str(value), True, color)
            self.canvas.blit(t, t.get_rect(midleft=(left.left + 10, y)))
            self.canvas.blit(v, v.get_rect(midright=(left.right - 10, y)))
            y += 46

        # pruhy zarovnané s vrchom prstenca
        mid = pygame.Rect(mid.left, ry - 118, mid.width, mid.height)
        self._section_title("UMIESTNENIE V HRÁCH", mid.left, mid.top)
        p = s.placements
        rows = [
            ("1. miesto", share(p[0], s.games), f"{p[0]}  ({fmt_pct(share(p[0], s.games))})", ui_style.GOLD),
            ("2. miesto", share(p[1], s.games), f"{p[1]}  ({fmt_pct(share(p[1], s.games))})", ui_style.GOLD_SOFT),
            ("3. miesto", share(p[2], s.games), f"{p[2]}  ({fmt_pct(share(p[2], s.games))})", ui_style.GOLD_SOFT),
            ("Chuj (prehra)", share(p[3], s.games), f"{p[3]}  ({fmt_pct(share(p[3], s.games))})", BAD),
        ]
        self._bar_rows(pygame.Rect(mid.left, mid.top + 44, mid.width, 260),
                       rows, value_w=130, label_w=170, row_h=62)
        self._mini_grid(right, [
            ("Priemerné umiestnenie", fmt_num(s.avg_placement, 2), None,
             "miesto"),
            ("Priemerné skóre", fmt_num(s.avg_score, 1), None, "bodov na konci"),
            ("Delené prehry", str(s.shared_losses),
             BAD if s.shared_losses else None, "Chuj spolu s iným"),
            ("Priemerná dĺžka hry", fmt_num(s.avg_game_rounds, 1), None, "kôl"),
            ("Najkratšia hra", str(s.shortest_game), None,
             plural(s.shortest_game, "kolo", "kolá", "kôl")),
            ("Najdlhšia hra", str(s.longest_game), None,
             plural(s.longest_game, "kolo", "kolá", "kôl")),
        ], cols=2, max_h=128)

    def _detail_clean(self, body: pygame.Rect):
        s = self.stats
        left, right = self._columns(body, [0.8, 2.5])
        ry = self._ring_y(left, extra=60)
        self._ring((left.centerx, ry), 118, s.clean_rate, GOOD,
                   fmt_pct(s.clean_rate, 1), "čisté kolá")
        t = self.font_label.render(
            f"{s.clean_rounds} z {s.rounds} kôl bez bodu", True, ui_style.TEXT_DIM)
        self.canvas.blit(t, t.get_rect(center=(left.centerx, ry + 160)))

        per_game = s.clean_rounds / s.games
        self._mini_grid(right, [
            ("Čisté kolá spolu", str(s.clean_rounds), GOOD, ""),
            ("Priemer na hru", fmt_num(per_game, 1), None, "čistých kôl"),
            ("Najdlhšia čistá séria", str(s.longest_clean_streak),
             ui_style.GOLD, "kôl za sebou"),
            (f"Bonus za {NO_PENALTY_STREAK} čistých kôl", str(s.streak_bonus),
             GOOD, f"krát ({NO_PENALTY_BONUS} b)".replace("-", "−")),
            ("Reset zo 100 na 90", str(s.reset_100), None, "krát"),
            ("Najviac čistých v hre", str(s.max_clean_rounds_game), None,
             "kôl"),
        ], cols=3, max_h=160)

    def _point_balance(self) -> list[tuple[str, int]]:
        """Rozklad konečného skóre podľa zdroja (súčet = súčet skóre
        všetkých hier). Body za záväzky, „tichého“, bonus a reset majú
        pevnú hodnotu, takže stačia počty z profilu."""
        s = self.stats
        decl = (DECLARATION_NONE_BONUS * s.declared_none_ok
                + DECLARATION_FAIL_PENALTY * (s.declared_none - s.declared_none_ok)
                + DECLARATION_ALL_BONUS * s.declared_all_ok
                + DECLARATION_ALL_PENALTY * (s.declared_all - s.declared_all_ok))
        return [
            ("Za karty", s.card_points),
            ("Záväzky", decl),
            ("Tichý", SHOOT_MOON_BONUS * s.sweeps),
            ("Bonus za sériu", NO_PENALTY_BONUS * s.streak_bonus),
            ("Reset 100 → 90", (RESET_SCORE - WINNING_SCORE) * s.reset_100),
        ]

    def _detail_points(self, body: pygame.Rect):
        s = self.stats
        c = self.canvas
        div = s.games if self.per_game else s.rounds
        unit = "za hru" if self.per_game else "za kolo"
        left, right = self._columns(body, [1.55, 1.0])

        # --- trestné body za karty podľa zdroja ---
        total = s.card_points
        self._section_title(f"TRESTNÉ BODY ZA KARTY {unit.upper()}",
                            left.left, left.top)
        rows = []
        for label, pts, color in (("Srdcia", s.hearts_points, (196, 86, 70)),
                                  ("Zelený horník", s.leaf_points, (110, 160, 84)),
                                  ("Žaluďový horník", s.acorn_points,
                                   (190, 140, 70))):
            rows.append((label, share(pts, total),
                         f"{fmt_num(pts / div, 2)} b  ({fmt_pct(share(pts, total))})",
                         color))
        self._bar_rows(pygame.Rect(left.left, left.top + 40, left.width, 168),
                       rows, value_w=190, label_w=200, row_h=56)

        # --- chytené karty ---
        grid_top = left.top + 40 + 3 * 56 + 30
        self._section_title("CHYTENÉ KARTY", left.left, grid_top)
        self._mini_grid(pygame.Rect(left.left, grid_top + 40, left.width,
                                    left.bottom - grid_top - 40), [
            ("Srdcia " + unit, fmt_num(s.hearts_caught / div, 2), None,
             f"spolu {s.hearts_caught}"),
            ("Zelený horník " + unit, fmt_num(s.leaf_over_caught / div, 2),
             None, f"spolu {s.leaf_over_caught}"),
            ("Žaluďový horník " + unit, fmt_num(s.acorn_over_caught / div, 2),
             None, f"spolu {s.acorn_over_caught}"),
            ("Najhoršie kolo", f"{s.worst_round} b", BAD, ""),
        ], cols=4, max_h=118, center=False)

        # --- bilancia bodov (všetky zdroje skóre) ---
        self._section_title(f"PRIEMERNÁ BILANCIA BODOV {unit.upper()}", right.left,
                            right.top)
        y = right.top + 40
        row_h = 46
        balance = self._point_balance()
        for i, (label, pts) in enumerate(balance):
            if i % 2 == 1:
                c.overlay((right.left - 8, y, right.width + 16, row_h),
                          (255, 214, 140, 7), border_radius=6)
            cy = y + row_h // 2
            t = self.font_label.render(label, True, ui_style.TEXT)
            c.blit(t, t.get_rect(midleft=(right.left, cy)))
            v = self.font_label.render(self._signed(pts / div), True,
                                       self._sign_color(pts))
            c.blit(v, v.get_rect(midright=(right.right, cy)))
            y += row_h
        y += 10
        c.line(ui_style.GOLD_SOFT, (right.left, y), (right.right, y))
        total_all = sum(p for _l, p in balance)
        t = self.font_head.render("Spolu", True, ui_style.GOLD)
        v = self.font_value.render(self._signed(total_all / div), True,
                                   self._sign_color(total_all))
        c.blit(t, t.get_rect(midleft=(right.left, y + 32)))
        c.blit(v, v.get_rect(midright=(right.right, y + 32)))
        note = ("= priemerné skóre na konci hry" if self.per_game
                else "priemerná zmena skóre za kolo")
        n = self.font_small.render(note, True, ui_style.TEXT_DIM)
        c.blit(n, n.get_rect(topright=(right.right, y + 58)))

    @staticmethod
    def _signed(v: float) -> str:
        if round(v, 2) == 0:
            return "0,00"
        return ("+" if v > 0 else "−") + fmt_num(abs(v), 2)

    @staticmethod
    def _sign_color(v: float):
        if round(v, 6) == 0:
            return ui_style.TEXT_DIM
        return BAD if v > 0 else GOOD

    def _detail_illum(self, body: pygame.Rect):
        s = self.stats
        left, right = self._columns(body, [0.8, 2.5])
        ry = self._ring_y(left, extra=60)
        if s.illuminated:
            self._ring((left.centerx, ry), 118,
                       s.illumination_success, GOOD,
                       fmt_pct(s.illumination_success), "úspešnosť")
        else:
            self._ring((left.centerx, ry), 118, 0, GOOD, "—",
                       "zatiaľ nevysvietené")
        t = self.font_label.render(
            "Úspech = vysvietený horník ťa minul", True, ui_style.TEXT_DIM)
        self.canvas.blit(t, t.get_rect(center=(left.centerx, ry + 160)))

        # Tabuľka podľa horníka
        c = self.canvas
        cols = (("", 0.34), ("Vysvietené", 0.22), ("Schytal vlastného", 0.24),
                ("Úspešnosť", 0.20))
        xs, x = [], right.left
        for _h, w in cols:
            xs.append((x, round(right.width * w)))
            x += round(right.width * w)
        y = right.top
        for (hx, hw), (head, _w) in zip(xs, cols):
            if head:
                h = self.font_small.render(head, True, ui_style.TEXT_DIM)
                c.blit(h, h.get_rect(midright=(hx + hw - 10, y + 14)))
        y += 34
        c.line(DIVIDER, (right.left, y), (right.right, y))
        rows = (("Zelený horník", "leaf-over.png", s.illuminated_leaf,
                 s.illuminated_leaf_caught),
                ("Žaluďový horník", "acorn-over.png", s.illuminated_acorn,
                 s.illuminated_acorn_caught),
                ("Spolu", None, s.illuminated, s.illuminated_caught_own))
        row_h = 70
        for i, (label, card, done, caught) in enumerate(rows):
            cy = y + row_h // 2 + 4
            if i % 2 == 1:
                c.overlay((right.left, y + 4, right.width, row_h),
                          (255, 214, 140, 7))
            tx = xs[0][0] + 10
            if card:
                img = c.card(card, lsize=(34, 55))
                c.blit(img, img.get_rect(midleft=(tx, cy)))
                tx += 50
            f = self.font_label
            lab = f.render(label, True, ui_style.GOLD if card is None else ui_style.TEXT)
            c.blit(lab, lab.get_rect(midleft=(tx, cy)))
            success = share(done - caught, done)
            values = (str(done), str(caught),
                      fmt_pct(success) if done else "—")
            colors = (ui_style.TEXT, BAD if caught else ui_style.TEXT,
                      GOOD if done and success >= 50 else
                      (BAD if done else ui_style.TEXT_DIM))
            for (hx, hw), val, col in zip(xs[1:], values, colors):
                v = self.font_value.render(val, True, col)
                c.blit(v, v.get_rect(midright=(hx + hw - 10, cy)))
            y += row_h
        c.line(DIVIDER, (right.left, y + 6), (right.right, y + 6))

        self._mini_grid(pygame.Rect(right.left, y + 26, right.width,
                                    right.bottom - y - 26), center=False,
                        max_h=120, items=[
            ("Priemer na hru", fmt_num(s.avg_illuminations_per_game, 2), None, ""),
            ("Najviac v jednej hre", str(s.max_illuminations_game), None, ""),
            ("Hry bez vysvietenia", str(s.games_without_illumination), None,
             f"z {s.games}"),
        ], cols=3)

    def _detail_special(self, body: pygame.Rect):
        s = self.stats
        cards = self._columns(body, [1, 1, 1])
        rate_none = s.declared_none_rate if s.declared_none else 0
        rate_all = s.declared_all_rate if s.declared_all else 0
        blocks = (
            ("TICHÝ", None, "Zobral všetky trestné karty bez záväzku",
             s.sweep_rate, GOOD, fmt_pct(s.sweep_rate, 1), "kôl",
             [("Spolu", str(s.sweeps)),
              ("Najviac v jednej hre", str(s.max_sweeps_game))]),
            ("NECHYTÍM NIČ", "none.png", "Záväzok: nezobrať žiadny štich",
             rate_none, GOOD,
             fmt_pct(rate_none) if s.declared_none else "—", "splnené",
             [("Vyhlásené", str(s.declared_none)),
              ("Splnené", str(s.declared_none_ok))]),
            ("BERIEM VŠETKO", "all.png", "Záväzok: zobrať všetky štichy",
             rate_all, GOOD,
             fmt_pct(rate_all) if s.declared_all else "—", "splnené",
             [("Vyhlásené", str(s.declared_all)),
              ("Splnené", str(s.declared_all_ok))]),
        )
        c = self.canvas
        for rect, (title, icon, desc, pct, color, value, cap, rows) in zip(cards, blocks):
            img = None
            if icon:
                try:
                    img = c.image(os.path.join(GRAPHICS, icon), (34, 34))
                except (pygame.error, FileNotFoundError):
                    pass
            t = self.font_head.render(title, True, ui_style.GOLD)
            w = t.get_width() + (44 if img else 0)
            x = rect.centerx - w // 2
            if img:
                c.blit(img, img.get_rect(midleft=(x, rect.top + 16)))
                x += 44
            c.blit(t, t.get_rect(midleft=(x, rect.top + 16)))
            d = self.font_small.render(desc, True, ui_style.TEXT_DIM)
            c.blit(d, d.get_rect(center=(rect.centerx, rect.top + 50)))
            self._ring((rect.centerx, rect.top + 170), 96, pct, color, value,
                       cap, width=16)
            y = rect.top + 296
            for label, val in rows:
                lt = self.font_label.render(label, True, ui_style.TEXT_DIM)
                vt = self.font_value.render(val, True, ui_style.TEXT)
                c.blit(lt, lt.get_rect(midleft=(rect.left + 30, y)))
                c.blit(vt, vt.get_rect(midright=(rect.right - 30, y)))
                y += 42
        # súhrn záväzkov pod kartami
        if s.declared:
            msg = (f"Záväzky spolu: {s.declared_ok} z {s.declared} splnených "
                   f"({fmt_pct(s.declared_rate)})")
        else:
            msg = "Záväzky spolu: zatiaľ žiadne"
        m = self.font_label.render(msg, True, ui_style.TEXT)
        c.blit(m, m.get_rect(midbottom=(body.centerx, body.bottom)))

    def _detail_records(self, body: pygame.Rect):
        s = self.stats
        n_cur = s.current_streak
        self._mini_grid(body, [
            ("Najdlhšia čistá séria", str(s.longest_clean_streak), ui_style.GOLD,
             plural(s.longest_clean_streak, "kolo", "kolá", "kôl")),
            ("Najdlhšia séria bez prehry", str(s.best_streak), ui_style.GOLD,
             plural(s.best_streak, "hra", "hry", "hier")),
            ("Aktuálna séria bez prehry", str(n_cur), None,
             plural(n_cur, "hra", "hry", "hier")),
            ("Najlepšia hra", str(s.best_game), GOOD, "bodov na konci"),
            ("Najhoršia hra", str(s.worst_game), BAD, "bodov na konci"),
            ("Najhoršie kolo", str(s.worst_round), BAD, "bodov v jednom kole"),
            ("Najviac čistých kôl", str(s.max_clean_rounds_game), None,
             "v jednej hre"),
            ("Najviac vysvietení", str(s.max_illuminations_game), None,
             "v jednej hre"),
            ("Najviac splnených záväzkov", str(s.max_declared_ok_game), None,
             "v jednej hre"),
            ("Najviac „tichých“", str(s.max_sweeps_game), None,
             "v jednej hre"),
        ], cols=5, gap=18, max_h=170)
