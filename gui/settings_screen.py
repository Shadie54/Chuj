# gui/settings_screen.py

import math
import os
import re
import pygame
import sys
from gui import display
from gui.canvas import StaticLayer
from gui import ui_style
from config import (
    SCREEN_WIDTH,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_DARK_GRAY, COLOR_BLACK,
    COLOR_GREEN, COLOR_YELLOW, COLOR_RED,
    FONT_SIZE_LARGE, FONT_SIZE_MEDIUM, FONT_SIZE_SMALL,
    BUTTON_RADIUS,
    ANIMATION_SPEED_MIN, ANIMATION_SPEED_MAX, ANIMATION_SPEED_DEFAULT
)

# Pozadia stola sa nehardkódujú — prečítajú sa priamo z assets/graphics/
# podľa vzoru "table.jpg", "table1.jpg", "table2.jpg", ... Pridanie
# ďalšieho súboru (napr. table7.jpg) sa tak v Nastaveniach objaví
# automaticky, bez zásahu do kódu.
_BG_PATTERN = re.compile(r"^table(\d*)\.jpg$")
_BG_DIR = "assets/graphics"


def _discover_table_backgrounds(graphics_dir: str = _BG_DIR) -> list[str]:
    """Vráti zoznam pozadí stola z disku, zoradený table.jpg, table1.jpg, ...

    Pri chybe (chýbajúci priečinok a pod.) vráti aspoň ["table.jpg"], aby
    Nastavenia nespadli na prázdnom zozname.
    """
    try:
        names = os.listdir(graphics_dir)
    except OSError:
        return ["table.jpg"]

    matches = []
    for name in names:
        m = _BG_PATTERN.match(name)
        if m:
            number = int(m.group(1)) if m.group(1) else 0
            matches.append((number, name))
    matches.sort(key=lambda pair: pair[0])

    found = [name for _, name in matches]
    return found if found else ["table.jpg"]


def _bg_label(fname: str) -> str:
    """Odvodí popisok z názvu súboru — "table.jpg" -> "Stôl", "table3.jpg" ->
    "Stôl 3". Žiadne ručne zadávané výnimky (napr. staré "Makita" pre
    table5.jpg) — jednotné pre všetky, aj budúce, pozadia."""
    m = _BG_PATTERN.match(fname)
    if not m or not m.group(1):
        return "Stôl"
    return f"Stôl {int(m.group(1))}"


# Záložky (rozhodnutie usera 2026-10-24): "Hra" = všetko, čo tu bolo
# doteraz, "Zobrazenie" = režim a veľkosť okna (rework rozlíšení, krok 7).
# Posledná otvorená záložka sa pamätá počas jedného spustenia hry.
TABS = (("hra", "Hra"), ("zobrazenie", "Zobrazenie"))
_last_tab = "hra"

# O koľko sa obsah záložky "Hra" posunul nadol kvôli pásu záložiek.
TAB_BAR_TOP = 152
TAB_H = 46
TAB_W = 240
TAB_SHIFT = 50

# Po prepnutí zobrazenia sa hra o toľko ms sama vráti k pôvodnému, ak
# hráč zmenu nepotvrdí (napr. okno sa mu zobrazilo mimo monitora).
CONFIRM_MS = 15000


class SettingsScreen:
    def __init__(self, screen: pygame.Surface, settings: dict):
        # `screen` (logický povrch) sa nepoužíva — kreslí sa cez Canvas
        # (rework rozlíšení, krok 4).
        self.screen = screen
        self.canvas = display.canvas()
        self._layer: StaticLayer | None = None
        self.active_tab = _last_tab
        self.clock = pygame.time.Clock()
        self.settings = settings.copy()
        if "animation_speed" not in self.settings:
            self.settings["animation_speed"] = ANIMATION_SPEED_DEFAULT

        self.font_title   = self.canvas.font(64)
        self.font_large   = self.canvas.font(FONT_SIZE_LARGE)
        self.font_medium  = self.canvas.font(FONT_SIZE_MEDIUM)
        self.font_small   = self.canvas.font(FONT_SIZE_SMALL)

        self.difficulties = ["easy", "medium", "hard"]
        self.difficulty_labels = {
            "easy":   "Ľahká",
            "medium": "Stredná",
            "hard":   "Ťažká"
        }
        self.difficulty_colors = {
            "easy":   COLOR_GREEN,
            "medium": COLOR_YELLOW,
            "hard":   COLOR_RED
        }

        center_x = SCREEN_WIDTH // 2
        self.center_x = center_x
        self.panel_width = min(1000, SCREEN_WIDTH - 120)
        panel_x = center_x - self.panel_width // 2

        gap = 26
        content_top = 180 + TAB_SHIFT

        # Pás záložiek pod nadpisom
        tabs_total_w = len(TABS) * TAB_W + (len(TABS) - 1) * 16
        tabs_x = center_x - tabs_total_w // 2
        self.tab_rects = {
            key: pygame.Rect(tabs_x + i * (TAB_W + 16), TAB_BAR_TOP, TAB_W, TAB_H)
            for i, (key, _label) in enumerate(TABS)
        }
        self.tab_hover: str | None = None

        # ------------------------------------------------------------
        # Panel 1 — AI obtiažnosť (popis a tlačidlá vodorovne v riadku)
        # ------------------------------------------------------------
        btn_w, btn_h = 150, 52
        btn_gap = 18
        row_side_pad = 40
        ai_top_pad = 65
        ai_row_h = 80
        ai_bottom_pad = 20
        ai_panel_h = ai_top_pad + 3 * ai_row_h + ai_bottom_pad

        self.panel_ai = pygame.Rect(panel_x, content_top, self.panel_width, ai_panel_h)

        buttons_total_w = 3 * btn_w + 2 * btn_gap
        buttons_start_x = self.panel_ai.right - row_side_pad - buttons_total_w

        self.ai_buttons = {}
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys  = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        for ai_idx, (name, key) in enumerate(zip(ai_names, ai_keys)):
            row_top = self.panel_ai.top + ai_top_pad + ai_idx * ai_row_h
            row_y = row_top + (ai_row_h - btn_h) // 2
            buttons = []
            for i, diff in enumerate(self.difficulties):
                x = buttons_start_x + i * (btn_w + btn_gap)
                buttons.append({
                    "difficulty": diff,
                    "rect": pygame.Rect(x, row_y, btn_w, btn_h),
                    "hover": False,
                    "key":   key
                })
            self.ai_buttons[name] = buttons

        self.ai_label_x = self.panel_ai.left + row_side_pad

        # ------------------------------------------------------------
        # Panel 2 — Animácie (rýchlosť, slider)
        # ------------------------------------------------------------
        anim_panel_h = 165
        self.panel_anim = pygame.Rect(
            panel_x, self.panel_ai.bottom + gap, self.panel_width, anim_panel_h
        )

        slider_pad = 80
        self.slider_rect = pygame.Rect(
            self.panel_anim.left + slider_pad,
            self.panel_anim.top + 105,
            self.panel_anim.width - slider_pad * 2,
            6
        )
        self.slider_handle_radius = 13
        self.slider_dragging = False

        # ------------------------------------------------------------
        # Panel 3 — Pozadie
        # ------------------------------------------------------------
        # Zoznam sa čerpá z disku (pozri _discover_table_backgrounds vyššie)
        # — môže byť dlhší, než sa zmestí naraz na obrazovku. Zobrazuje sa
        # preto len "okno" self.bg_visible_count miniatúr, posúvateľné
        # šípkami vľavo/vpravo (self.bg_scroll = index prvej viditeľnej).
        # Rozmery miniatúr, medzery aj šírka panela ostávajú rovnaké ako
        # pri pôvodnom pevnom zozname 6 pozadí — nič sa nezväčšuje ani
        # nezmenšuje, len sa časť zoznamu pri väčšom počte skryje.
        self.bg_options = _discover_table_backgrounds()
        self.bg_labels  = [_bg_label(f) for f in self.bg_options]
        self.bg_thumbnails = {}

        thumb_w, thumb_h = 150, 88
        thumb_gap = 16
        self._load_thumbnails(thumb_w, thumb_h)

        self.bg_visible_count = min(5, len(self.bg_options))
        self.bg_max_scroll = max(0, len(self.bg_options) - self.bg_visible_count)

        bg_top_pad = 62
        bg_label_h = 30
        bg_bottom_pad = 14
        bg_panel_h = bg_top_pad + thumb_h + bg_label_h + bg_bottom_pad

        self.panel_bg = pygame.Rect(
            panel_x, self.panel_anim.bottom + gap, self.panel_width, bg_panel_h
        )

        total_w = self.bg_visible_count * (thumb_w + thumb_gap) - thumb_gap
        thumb_start = center_x - total_w // 2
        thumb_y = self.panel_bg.top + bg_top_pad

        self.bg_rects = []
        for i in range(self.bg_visible_count):
            x = thumb_start + i * (thumb_w + thumb_gap)
            self.bg_rects.append(pygame.Rect(x, thumb_y, thumb_w, thumb_h))

        # Šípky — vo voľnom mieste medzi panelom a oknom miniatúr (zámerne
        # tam, nie mimo panela, aby sa nezmenila celková šírka/proporcie
        # panela "POZADIE STOLA"). Pri málo pozadiach (okno pokryje celý
        # zoznam, bg_max_scroll == 0) sa jednoducho nikdy nedajú stlačiť.
        arrow_cy = thumb_y + thumb_h // 2
        thumb_end = thumb_start + total_w
        left_cx  = (panel_x + thumb_start) // 2
        right_cx = (thumb_end + panel_x + self.panel_width) // 2

        self.bg_arrow_left = {
            "rect": pygame.Rect(left_cx - 18, arrow_cy - 28, 36, 56),
            "center": (left_cx, arrow_cy),
            "hover": False,
        }
        self.bg_arrow_right = {
            "rect": pygame.Rect(right_cx - 18, arrow_cy - 28, 36, 56),
            "center": (right_cx, arrow_cy),
            "hover": False,
        }

        # Okno sa pri otvorení Nastavení posunie tak, aby bolo hneď vidno
        # aktuálne vybrané pozadie, aj keby bolo mimo prvých N miniatúr.
        current_bg = settings.get("table_bg", "table.jpg")
        self.bg_scroll = 0
        if current_bg in self.bg_options:
            current_idx = self.bg_options.index(current_bg)
            if current_idx >= self.bg_visible_count:
                self.bg_scroll = min(
                    current_idx - (self.bg_visible_count - 1),
                    self.bg_max_scroll,
                )

        # Tlačidlo späť
        self.back_button = {
            "rect":  pygame.Rect(center_x - 150, display.logical_height() - 70, 300, 50),
            "hover": False
        }

        self._init_display_tab(panel_x)

    # ------------------------------------------------------------------
    # Záložka Zobrazenie — rozloženie a stav výberu
    # ------------------------------------------------------------------

    def _init_display_tab(self, panel_x: int):
        mode = display.current_mode()
        self.window_sizes = display.window_sizes()
        top = 180 + TAB_SHIFT

        # Panel 1 — režim (Celá obrazovka / Okno)
        self.panel_mode = pygame.Rect(panel_x, top, self.panel_width, 230)
        bw, bh, bgap = 320, 56, 30
        x0 = self.center_x - (2 * bw + bgap) // 2
        by = self.panel_mode.top + 75
        self.mode_buttons = [
            {"windowed": False, "label": "Celá obrazovka",
             "rect": pygame.Rect(x0, by, bw, bh), "hover": False},
            {"windowed": True, "label": "Okno",
             "rect": pygame.Rect(x0 + bw + bgap, by, bw, bh), "hover": False},
        ]

        # Panel 2 — veľkosť okna, mriežka po 4 (len v režime Okno)
        cols, sw, sh, sgap, row_h = 4, 200, 52, 18, 70
        rows = max(1, math.ceil(len(self.window_sizes) / cols))
        self.panel_size = pygame.Rect(panel_x, self.panel_mode.bottom + 26,
                                      self.panel_width, 65 + rows * row_h + 20)
        self.size_buttons = []
        for i, size in enumerate(self.window_sizes):
            r, c = divmod(i, cols)
            in_row = min(cols, len(self.window_sizes) - r * cols)
            row_w = in_row * sw + (in_row - 1) * sgap
            x = self.center_x - row_w // 2 + c * (sw + sgap)
            y = self.panel_size.top + 65 + r * row_h + (row_h - sh) // 2
            self.size_buttons.append(
                {"size": size, "rect": pygame.Rect(x, y, sw, sh), "hover": False})

        # "Použiť" — pod posledným viditeľným panelom
        self._apply_rect_full = pygame.Rect(
            self.center_x - 150, self.panel_mode.bottom + 30, 300, 56)
        self._apply_rect_window = pygame.Rect(
            self.center_x - 150, self.panel_size.bottom + 30, 300, 56)
        self.apply_hover = False

        # Výber čakajúci na "Použiť"
        self.pending_windowed = mode.windowed and bool(self.window_sizes)
        self.pending_size = self._initial_window_size(mode)

        # Potvrdzovací dialóg po prepnutí: {"old": DisplayMode, "deadline": ms}
        self.confirm: dict | None = None
        cy = display.logical_height() // 2
        self.confirm_panel = pygame.Rect(self.center_x - 380, cy - 150, 760, 300)
        self.confirm_keep = pygame.Rect(self.center_x - 250, cy + 50, 230, 56)
        self.confirm_revert = pygame.Rect(self.center_x + 20, cy + 50, 230, 56)
        self.confirm_hover: str | None = None

    def _initial_window_size(self, mode) -> tuple[int, int] | None:
        """Veľkosť okna predvolená v mriežke: aktuálne okno, inak
        zapamätaná veľkosť zo settings.json, inak najväčšia, čo sa zmestí."""
        if mode.windowed:
            return (mode.width, mode.height)
        saved = self.settings.get("display")
        if isinstance(saved, dict):
            try:
                size = (int(saved["width"]), int(saved["height"]))
            except (KeyError, TypeError, ValueError):
                size = None
            if size in self.window_sizes:
                return size
        return self.window_sizes[-1] if self.window_sizes else None

    def _apply_rect(self) -> pygame.Rect:
        return self._apply_rect_window if self.pending_windowed \
            else self._apply_rect_full

    def _display_changed(self) -> bool:
        """Líši sa výber od aktuálneho zobrazenia? (inak je Použiť sivé)"""
        mode = display.current_mode()
        if self.pending_windowed != mode.windowed:
            return True
        if self.pending_windowed:
            return self.pending_size != (mode.width, mode.height)
        return (mode.width, mode.height) != display.desktop_size()

    # ------------------------------------------------------------------
    # Prepnutie zobrazenia za behu + potvrdenie
    # ------------------------------------------------------------------

    def _rebuild(self):
        """Po zmene okna: nový Canvas (mierka), fonty, miniatúry aj
        rozloženie podľa novej logickej výšky — stav výberu ostáva."""
        keep = (self.settings, self.active_tab, self.pending_windowed,
                self.pending_size, self.bg_scroll)
        self.__init__(display.get_surface(), self.settings)
        (self.settings, self.active_tab, self.pending_windowed,
         self.pending_size, self.bg_scroll) = keep

    def _apply_display(self):
        old = display.current_mode()
        if self.pending_windowed and self.pending_size:
            w, h = self.pending_size
            new = display.DisplayMode(w, h, True, "settings")
        else:
            new = display.fullscreen_mode()
        display.apply_mode(new)
        self._rebuild()
        self.confirm = {"old": old,
                        "deadline": pygame.time.get_ticks() + CONFIRM_MS}

    def _confirm_keep(self):
        """Ponechať — až teraz sa voľba zapíše (main.py uloží settings)."""
        entry = {"mode": "window" if self.pending_windowed else "borderless"}
        if self.pending_size:
            # Veľkosť okna sa pamätá aj pri celej obrazovke (rozhodnutie
            # usera) — po návrate do režimu Okno je predvolená.
            entry["width"], entry["height"] = self.pending_size
        self.settings["display"] = entry
        self.confirm = None

    def _confirm_revert(self):
        old = self.confirm["old"]
        display.apply_mode(old)
        self._rebuild()
        mode = display.current_mode()
        self.pending_windowed = mode.windowed and bool(self.window_sizes)
        self.pending_size = self._initial_window_size(mode)
        self.confirm = None

    def _confirm_seconds_left(self) -> int:
        left = self.confirm["deadline"] - pygame.time.get_ticks()
        return max(0, math.ceil(left / 1000))

    # ------------------------------------------------------------------
    # Načítanie miniatúr
    # ------------------------------------------------------------------

    def _load_thumbnails(self, thumb_w: int, thumb_h: int):
        for fname in self.bg_options:
            try:
                self.bg_thumbnails[fname] = self.canvas.image(
                    f"assets/graphics/{fname}", (thumb_w, thumb_h))
            except (FileNotFoundError, pygame.error):
                self.bg_thumbnails[fname] = None

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> dict:
        while True:
            self.clock.tick(60)
            mouse_pos = display.mouse_pos()

            if self.confirm is not None:
                self._run_confirm_events()
                if (self.confirm is not None
                        and self._confirm_seconds_left() == 0):
                    self._confirm_revert()
                self._update_hover(display.mouse_pos())
                self._draw()
                display.present()
                continue

            for event in display.get_events():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return self.settings

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if (self.active_tab == "hra"
                                and self._slider_hit(event.pos)):
                            self.slider_dragging = True
                            self._update_slider_from_pos(event.pos[0])
                        else:
                            result = self._handle_click(event.pos)
                            if result == "back":
                                return self.settings

                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.slider_dragging = False

                if event.type == pygame.MOUSEMOTION:
                    if self.slider_dragging:
                        self._update_slider_from_pos(event.pos[0])

            self._update_hover(mouse_pos)
            self._draw()
            display.present()

    def _run_confirm_events(self):
        """Udalosti počas dialógu "Ponechať toto zobrazenie?" — Enter =
        ponechať, Esc = vrátiť; ostatné klikanie je zablokované."""
        for event in display.get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._confirm_keep()
                    return
                if event.key == pygame.K_ESCAPE:
                    self._confirm_revert()
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.confirm_keep.collidepoint(event.pos):
                    self._confirm_keep()
                    return
                if self.confirm_revert.collidepoint(event.pos):
                    self._confirm_revert()
                    return

    # ------------------------------------------------------------------
    # Slider — rýchlosť animácií
    # ------------------------------------------------------------------

    def _slider_hit(self, pos: tuple[int, int]) -> bool:
        """Rozšírená hit-oblasť okolo trati slidera (ľahšie sa trafí)."""
        hit_rect = self.slider_rect.inflate(20, self.slider_handle_radius * 3)
        return hit_rect.collidepoint(pos)

    def _update_slider_from_pos(self, mouse_x: int):
        frac = (mouse_x - self.slider_rect.left) / self.slider_rect.width
        frac = max(0.0, min(1.0, frac))
        value = ANIMATION_SPEED_MIN + frac * (ANIMATION_SPEED_MAX - ANIMATION_SPEED_MIN)
        self.settings["animation_speed"] = round(value, 2)

    def _slider_handle_pos(self) -> tuple[int, int]:
        value = self.settings.get("animation_speed", ANIMATION_SPEED_DEFAULT)
        frac = (value - ANIMATION_SPEED_MIN) / (ANIMATION_SPEED_MAX - ANIMATION_SPEED_MIN)
        frac = max(0.0, min(1.0, frac))
        x = self.slider_rect.left + int(frac * self.slider_rect.width)
        y = self.slider_rect.centery
        return x, y

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]) -> str | None:
        global _last_tab
        for key, rect in self.tab_rects.items():
            if rect.collidepoint(pos):
                self.active_tab = _last_tab = key
                return None

        if self.back_button["rect"].collidepoint(pos):
            return "back"

        if self.active_tab == "zobrazenie":
            return self._handle_display_click(pos)

        if self.active_tab != "hra":
            return None

        for name, buttons in self.ai_buttons.items():
            for btn in buttons:
                if btn["rect"].collidepoint(pos):
                    self.settings[btn["key"]] = btn["difficulty"]
                    return None

        if self.bg_arrow_left["rect"].collidepoint(pos):
            if self.bg_scroll > 0:
                self.bg_scroll -= 1
            return None

        if self.bg_arrow_right["rect"].collidepoint(pos):
            if self.bg_scroll < self.bg_max_scroll:
                self.bg_scroll += 1
            return None

        for i, rect in enumerate(self.bg_rects):
            idx = self.bg_scroll + i
            if idx >= len(self.bg_options):
                continue
            if rect.collidepoint(pos):
                self.settings["table_bg"] = self.bg_options[idx]
                return None

        return None

    def _handle_display_click(self, pos: tuple[int, int]) -> None:
        for btn in self.mode_buttons:
            if btn["rect"].collidepoint(pos):
                if btn["windowed"] and not self.window_sizes:
                    return None          # okno sa na tento monitor nezmestí
                self.pending_windowed = btn["windowed"]
                return None
        if self.pending_windowed:
            for btn in self.size_buttons:
                if btn["rect"].collidepoint(pos):
                    self.pending_size = btn["size"]
                    return None
        if self._apply_rect().collidepoint(pos) and self._display_changed():
            self._apply_display()
        return None

    def _update_hover(self, mouse_pos: tuple[int, int]):
        for btn in self.mode_buttons + self.size_buttons:
            btn["hover"] = btn["rect"].collidepoint(mouse_pos)
        self.apply_hover = self._apply_rect().collidepoint(mouse_pos)
        self.confirm_hover = (
            "keep" if self.confirm_keep.collidepoint(mouse_pos) else
            "revert" if self.confirm_revert.collidepoint(mouse_pos) else None)
        self.tab_hover = next(
            (key for key, rect in self.tab_rects.items()
             if rect.collidepoint(mouse_pos)), None)
        for buttons in self.ai_buttons.values():
            for btn in buttons:
                btn["hover"] = btn["rect"].collidepoint(mouse_pos)
        self.back_button["hover"] = self.back_button["rect"].collidepoint(
            mouse_pos
        )
        self.bg_arrow_left["hover"] = self.bg_arrow_left["rect"].collidepoint(mouse_pos)
        self.bg_arrow_right["hover"] = self.bg_arrow_right["rect"].collidepoint(mouse_pos)

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        c = self.canvas
        if self._layer is None:
            self._layer = StaticLayer(c.target.get_size())
        if self._layer.needs_redraw("static"):
            with self._layer.drawing(c, key="static"):
                # Vzhľad: gui/ui_style.py (grafický rework 2026-10-27).
                ui_style.draw_backdrop(c)
                self._draw_title()
        self._layer.blit_to(c.target)

        self._draw_tabs()
        if self.active_tab == "zobrazenie":
            self._draw_display_tab()
        else:
            self._draw_game_tab()

        self._draw_back_button()

        if self.confirm is not None:
            self._draw_confirm()

    def _draw_tabs(self):
        for key, label in TABS:
            active = key == self.active_tab
            hover = key == self.tab_hover and not active
            ui_style.draw_button(self.canvas, self.tab_rects[key], label,
                                 self.font_medium, 1 if active else 3, hover)

    def _draw_display_tab(self):
        mode = display.current_mode()
        vp = display.viewport()
        c = self.canvas

        # Panel 1 — režim
        self._draw_panel(self.panel_mode, "REŽIM ZOBRAZENIA")
        for btn in self.mode_buttons:
            enabled = not btn["windowed"] or bool(self.window_sizes)
            self._draw_choice(btn["rect"], btn["label"],
                              selected=btn["windowed"] == self.pending_windowed,
                              hover=btn["hover"], enabled=enabled)
        dw, dh = display.desktop_size()
        if not self.window_sizes:
            hint = "Okno sa na tento monitor nezmestí (je menší než 1366 × 768)."
        elif self.pending_windowed:
            hint = "Okno s rámom — veľkosť zvoľte nižšie."
        else:
            hint = f"Natívne rozlíšenie monitora: {dw} × {dh}"
        surf = self.font_small.render(hint, True, COLOR_GRAY)
        c.blit(surf, surf.get_rect(centerx=self.center_x,
                                   centery=self.panel_mode.top + 158))
        current = (f"Aktuálne: {mode.width} × {mode.height}, "
                   + ("okno" if mode.windowed else "celá obrazovka")
                   + f", mierka obrazu {round(vp.scale * 100)} %")
        surf = self.font_small.render(current, True, COLOR_WHITE)
        c.blit(surf, surf.get_rect(centerx=self.center_x,
                                   centery=self.panel_mode.top + 196))

        # Panel 2 — veľkosť okna
        if self.pending_windowed:
            self._draw_panel(self.panel_size, "VEĽKOSŤ OKNA")
            for btn in self.size_buttons:
                w, h = btn["size"]
                self._draw_choice(btn["rect"], f"{w} × {h}",
                                  selected=btn["size"] == self.pending_size,
                                  hover=btn["hover"], enabled=True)

        # Použiť
        rect = self._apply_rect()
        enabled = self._display_changed() and self.confirm is None
        ui_style.draw_button(c, rect, "Použiť", self.font_large, 1,
                             self.apply_hover, enabled=enabled)

        if mode.source in ("cli", "safe"):
            note = self.font_small.render(
                "Hra je spustená s parametrom príkazového riadka — pri štarte "
                "má prednosť pred uloženým nastavením.", True, COLOR_GRAY)
            c.blit(note, note.get_rect(centerx=self.center_x, top=rect.bottom + 18))

    def _draw_choice(self, rect: pygame.Rect, label: str, selected: bool,
                     hover: bool, enabled: bool):
        """Prepínacie tlačidlo (režim, veľkosť okna): zvolené = úroveň 1."""
        ui_style.draw_button(self.canvas, rect, label, self.font_medium,
                             1 if selected else 3, hover and not selected,
                             enabled=enabled, shadow=False)

    def _draw_confirm(self):
        """Dialóg "Ponechať toto zobrazenie?" s odpočtom návratu."""
        c = self.canvas
        c.overlay_window((0, 0, 0, 170))
        panel = self.confirm_panel
        ui_style.draw_panel(c, panel)
        title = self.font_large.render("Ponechať toto zobrazenie?", True, ui_style.GOLD)
        c.blit(title, title.get_rect(centerx=panel.centerx, top=panel.top + 40))
        secs = self._confirm_seconds_left()
        text = self.font_medium.render(
            f"Návrat k predchádzajúcemu zobrazeniu o {secs} s", True, ui_style.TEXT)
        c.blit(text, text.get_rect(centerx=panel.centerx, top=panel.top + 110))
        for key, rect, label, tier in (
                ("keep", self.confirm_keep, "Ponechať", 1),
                ("revert", self.confirm_revert, "Vrátiť", 3)):
            ui_style.draw_button(c, rect, label, self.font_large, tier,
                                 self.confirm_hover == key)

    def _draw_game_tab(self):
        self._draw_panel(self.panel_ai, "OBTIAŽNOSŤ POČÍTAČOV")
        self._draw_ai_sections()

        self._draw_panel(self.panel_anim, "RÝCHLOSŤ ANIMÁCIÍ")
        self._draw_speed_slider()

        self._draw_panel(self.panel_bg, "POZADIE STOLA")
        self._draw_bg_section()
        self._draw_bg_arrows()

    def _draw_title(self):
        ui_style.draw_screen_title(self.canvas, "NASTAVENIA", self.font_title,
                                   (SCREEN_WIDTH // 2, 88), line_gap=42)

    def _draw_panel(self, rect: pygame.Rect, title: str):
        """Panel so zlatohnedým rámom a nadpisom (gui/ui_style.py)."""
        ui_style.draw_panel(self.canvas, rect, title, self.font_medium)

    def _draw_ai_sections(self):
        ai_names = ["Počítač 1", "Počítač 2", "Počítač 3"]
        ai_keys  = ["ai1_difficulty", "ai2_difficulty", "ai3_difficulty"]

        for row_idx, (name, key) in enumerate(zip(ai_names, ai_keys)):
            buttons = self.ai_buttons[name]
            row_centery = buttons[0]["rect"].centery

            label_surf = self.font_medium.render(name, True, COLOR_WHITE)
            label_rect = label_surf.get_rect(midleft=(self.ai_label_x, row_centery))
            self.canvas.blit(label_surf, label_rect)

            if row_idx > 0:
                divider_y = buttons[0]["rect"].top - 14
                self.canvas.line(COLOR_DARK_GRAY,
                    (self.panel_ai.left + 24, divider_y),
                    (self.panel_ai.right - 24, divider_y),
                    width=1
                )

            current = self.settings[key]
            for btn in buttons:
                diff        = btn["difficulty"]
                is_selected = (diff == current)
                base_color  = self.difficulty_colors[diff]

                # Farba obtiažnosti ostáva (zelená/žltá/červená nesú
                # význam), ale stlmená do tmavého štýlu menu (ui_style):
                # zvolená = farebná výplň so silným rámom, ostatné tmavé.
                r = BUTTON_RADIUS
                if is_selected:
                    self.canvas.overlay(btn["rect"], (*base_color, 165),
                                        border_radius=r)
                    self.canvas.overlay(btn["rect"], (0, 0, 0, 60),
                                        border_radius=r)
                elif btn["hover"]:
                    self.canvas.overlay(btn["rect"], (*base_color, 70),
                                        border_radius=r)
                else:
                    self.canvas.overlay(btn["rect"], (27, 19, 12, 230),
                                        border_radius=r)

                border_color = base_color if is_selected or btn["hover"] \
                    else (98, 76, 46)
                border_width = 2
                self.canvas.rect(border_color,
                    btn["rect"], width=border_width,
                    border_radius=r
                )

                text_color = (255, 246, 228) if is_selected else ui_style.TEXT
                text = self.font_medium.render(
                    self.difficulty_labels[diff], True, text_color
                )
                text_rect = text.get_rect(center=btn["rect"].center)
                self.canvas.blit(text, text_rect)

    def _draw_speed_slider(self):
        track = self.slider_rect

        # Popisky nad traťou
        lbl_slow = self.font_small.render("Pomalšie", True, COLOR_GRAY)
        lbl_fast = self.font_small.render("Rýchlejšie", True, COLOR_GRAY)
        self.canvas.blit(lbl_slow, (track.left, track.top - 28))
        lbl_fast_rect = lbl_fast.get_rect(topright=(track.right, track.top - 28))
        self.canvas.blit(lbl_fast, lbl_fast_rect)

        # Trať (nevyplnená)
        self.canvas.line(COLOR_DARK_GRAY,
            (track.left, track.centery), (track.right, track.centery),
            width=6
        )

        handle_x, handle_y = self._slider_handle_pos()

        # Trať (vyplnená časť po handle)
        self.canvas.line(COLOR_GOLD,
            (track.left, track.centery), (handle_x, handle_y),
            width=6
        )

        handle_color = COLOR_YELLOW if self.slider_dragging else COLOR_GOLD
        self.canvas.circle(handle_color, (handle_x, handle_y), self.slider_handle_radius)
        self.canvas.circle(COLOR_BLACK, (handle_x, handle_y), self.slider_handle_radius, width=2)

        value = self.settings.get("animation_speed", ANIMATION_SPEED_DEFAULT)
        value_text = self.font_medium.render(f"{value:.1f}×", True, COLOR_WHITE)
        value_rect = value_text.get_rect(midtop=(self.center_x, track.bottom + 16))
        self.canvas.blit(value_text, value_rect)

    def _draw_bg_section(self):
        current = self.settings.get("table_bg", "table.jpg")

        for i, rect in enumerate(self.bg_rects):
            idx = self.bg_scroll + i
            if idx >= len(self.bg_options):
                continue
            fname = self.bg_options[idx]

            is_selected = (fname == current)
            is_hover    = rect.collidepoint(display.mouse_pos())

            thumb = self.bg_thumbnails.get(fname)
            if thumb:
                self.canvas.blit(thumb, rect)
            else:
                self.canvas.rect((40, 25, 10), rect)

            border_color = COLOR_GOLD if is_selected else (
                COLOR_WHITE if is_hover else COLOR_GRAY
            )
            border_width = 3 if is_selected else 1
            self.canvas.rect(border_color, rect,
                width=border_width, border_radius=6
            )

            lbl      = self.font_small.render(
                self.bg_labels[idx], True,
                COLOR_GOLD if is_selected else COLOR_WHITE
            )
            lbl_rect = lbl.get_rect(
                centerx=rect.centerx, top=rect.bottom + 6
            )
            self.canvas.blit(lbl, lbl_rect)

    def _draw_bg_arrows(self):
        """Malé trojuholníkové šípky — posúvajú okno viditeľných miniatúr
        pozadí. Stlmené (a nereagujú na klik — pozri _handle_click), keď sa
        už nedá posunúť ďalším smerom."""
        self._draw_bg_arrow(self.bg_arrow_left, "left", self.bg_scroll > 0)
        self._draw_bg_arrow(
            self.bg_arrow_right, "right", self.bg_scroll < self.bg_max_scroll
        )

    def _draw_bg_arrow(self, arrow: dict, direction: str, enabled: bool):
        cx, cy = arrow["center"]
        if not enabled:
            color = COLOR_DARK_GRAY
        elif arrow["hover"]:
            color = COLOR_YELLOW
        else:
            color = COLOR_GOLD

        half_w, half_h = 10, 16
        if direction == "left":
            points = [
                (cx + half_w, cy - half_h),
                (cx + half_w, cy + half_h),
                (cx - half_w, cy),
            ]
        else:
            points = [
                (cx - half_w, cy - half_h),
                (cx - half_w, cy + half_h),
                (cx + half_w, cy),
            ]
        self.canvas.polygon(color, points)

    def _draw_back_button(self):
        ui_style.draw_button(self.canvas, self.back_button["rect"], "← Späť",
                             self.font_large, 3, self.back_button["hover"])

    def __repr__(self) -> str:
        return "SettingsScreen()"
