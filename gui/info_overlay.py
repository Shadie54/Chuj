# gui/info_overlay.py

import pygame
import os
from gui import display, ui_style
from gui.rules_demo import TrickRulesDemo
from config import (
    SCREEN_WIDTH,
    COLOR_WHITE, COLOR_GOLD, SUIT_ICONS_PATH,
)

# Vizuál panelov (pozadie/rámik/zaoblenie) zjednotený so zvyškom hry —
# gui/settings_screen.py::_draw_panel, gui/lesson_panel.py,
# gui/round_status.py všetky používajú COLOR_PANEL_BG s vysokou krytosťou
# a celý zaoblený zlatý rámik, nie len tenký pásik pri okraji.
_PANEL_BG_ALPHA = 210
_PANEL_BORDER_RADIUS = 14

# Grafický rework 2026-10-28 (koncept "Pravidlá a bodovanie"): rám okna,
# nadpis, záložky, krížik a celá záložka Bodovanie sú v štýle
# gui/ui_style.py. Záložka Pravidlá zatiaľ ostáva pôvodná (grafika k nej
# sa pripravuje).
FRAME_MARGIN_X = 60
FRAME_MARGIN_Y = 18
SECTION_FILL = (27, 18, 11, 255)
SECTION_RADIUS = 12
SUBSECTION_FILL = (20, 13, 8, 255)
BADGE_FILL = (150, 34, 26)
BADGE_BORDER = (226, 92, 70)
BADGE_TEXT = (255, 238, 225)
ILLUM_COLOR = (240, 196, 92)          # údaje o vysvietení
CLOSE_R = 24


CARD_RATIO = 181 / 293                # šírka / výška karty
FAN_STEP = 0.36                       # krok vejára (podiel šírky karty)

# Obdĺžnikový výrez ikonky (zlomky šírky/výšky: x0, x1, y0, y1) — vejár
# kariet je široký,      takže na šírku sa reže menej a na výšku viac (pomer 3:2).
DECL_CROP = (0.08, 0.92, 0.22, 0.78)

# Ikonky záložky Pravidlá (assets/graphics) — prvý existujúci súbor sa
# použije. Dodané ikonky stačí uložiť pod prvým menom, kód netreba meniť.
RULES_ICON_FILES = {
    "goal": ("trophy.png", "chuj.png"),             # Cieľ hry
    "scoring": ("scoresheet.png", "chujogram.png"),  # krok Bodovanie
}


class InfoOverlay:
    def __init__(self, canvas):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.visible = False
        self.font_small = self.canvas.font(22)
        self.font_medium = self.canvas.font(30)
        self.font_large = self.canvas.font(48)

        # Odvodené od SKUTOČNEJ výšky písma (font.get_height()), nie z
        # čísla "na oko". Pevné hodnoty ladené na jednom fonte (napr. v
        # headless testovacom prostredí bez Tahomy) spôsobovali na inom
        # systéme (reálna Tahoma na Windows má citeľne vyšší riadok)
        # prekrývanie textu, deliacich čiar pod nadpismi aj farebných
        # odznakov s bodovou hodnotou.
        self._header_h = 10 + self.font_medium.get_height() + 6 + 10
        self._row_h = self.font_small.get_height() + 12       # text aj odznak
        self._medium_line_h = self.font_medium.get_height() + 8
        self._small_line_h = self.font_small.get_height() + 6

        self.font_title = self.canvas.font(46)
        self.font_section = self.canvas.font(30)
        self.font_text = self.canvas.font(24)
        self.font_badge = self.canvas.font(24)

        # Rám okna (celá obrazovka s okrajom), krížik vpravo hore
        self.frame = pygame.Rect(FRAME_MARGIN_X, FRAME_MARGIN_Y,
                                 SCREEN_WIDTH - 2 * FRAME_MARGIN_X,
                                 display.logical_height() - 2 * FRAME_MARGIN_Y)
        ccx, ccy = self.frame.right - 48, self.frame.top + 46
        self.btn_close = pygame.Rect(ccx - CLOSE_R - 4, ccy - CLOSE_R - 4,
                                     2 * CLOSE_R + 8, 2 * CLOSE_R + 8)

        self.active_tab = "bodovanie"

        # Záložky — spojené vedľa seba pod nadpisom
        tab_w, tab_h = 240, 46
        cx = SCREEN_WIDTH // 2
        self.tab_bodovanie = pygame.Rect(cx - tab_w, 100, tab_w, tab_h)
        self.tab_pravidla  = pygame.Rect(cx,         100, tab_w, tab_h)

        # Pôvodný obsah záložky Pravidlá — pod záložkami, vnútri rámu
        self.content_y = self.tab_bodovanie.bottom + 10
        # ikonky farieb
        self._suit_icons: dict[str, pygame.Surface] = {}
        self._load_suit_icons()
        # ikonky záväzkov (Pravidlá) a chuja (Bodovanie) — vysvetlenie
        # už existujúcich ikoniek z reálnej hry (phase_renderer.py,
        # round_status.py), nie nová grafika.
        self._load_declaration_icons()
        self._load_chuj_icon()
        # Animovaná ukážka pravidiel štichov (záložka Pravidlá)
        self.rules_demo = TrickRulesDemo(self.canvas)
    # ------------------------------------------------------------------
    # Viditeľnosť
    # ------------------------------------------------------------------

    def show(self):
        self.visible = True
        self.rules_demo.reset()          # ukážka štichov vždy od scény 1

    def hide(self):
        self.visible = False

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

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
                if self.active_tab != "pravidla":
                    self.rules_demo.reset()
                self.active_tab = "pravidla"
                return True
            if self.active_tab == "pravidla":
                self.rules_demo.handle_click(event.pos)
            return True
        return False

    # ------------------------------------------------------------------
    # Hlavné kreslenie
    # ------------------------------------------------------------------

    def draw(self):
        if not self.visible:
            return
        c = self.canvas

        # Stmavenie hry cez celé okno (aj pásma pri 21:9) a nepriehľadný
        # rám okna so zlatohnedým okrajom
        c.overlay_window((0, 0, 0, 200))
        c.overlay(self.frame, (17, 11, 7, 255), border_radius=ui_style.PANEL_RADIUS)
        ui_style.draw_panel(c, self.frame)

        ui_style.draw_screen_title(c, "PRAVIDLÁ A BODOVANIE", self.font_title,
                                   (SCREEN_WIDTH // 2, self.frame.top + 36),
                                   line_half_w=300, line_gap=32)
        self._draw_close(self.btn_close.collidepoint(display.mouse_pos()))
        self._draw_tabs()

        if self.active_tab == "bodovanie":
            self._draw_scoring()
        else:
            self._draw_rules()

    def _draw_close(self, hover: bool):
        c = self.canvas
        cx, cy = self.btn_close.center
        c.circle((24, 16, 10), (cx, cy), CLOSE_R)
        c.circle(ui_style.BTN_BORDER_HOVER if hover else ui_style.GOLD_SOFT,
                 (cx, cy), CLOSE_R, width=2)
        color = ui_style.BTN_TEXT_HOVER if hover else ui_style.GOLD
        d = 9
        c.line(color, (cx - d, cy - d), (cx + d, cy + d), width=3)
        c.line(color, (cx - d, cy + d), (cx + d, cy - d), width=3)

    # ------------------------------------------------------------------
    # Záložky
    # ------------------------------------------------------------------

    def _draw_tabs(self):
        mouse = display.mouse_pos()
        for tab, label, key in (
            (self.tab_bodovanie, "Bodovanie", "bodovanie"),
            (self.tab_pravidla,  "Pravidlá",  "pravidla"),
        ):
            active = self.active_tab == key
            ui_style.draw_button(self.canvas, tab, label, self.font_text,
                                 1 if active else 3,
                                 hover=not active and tab.collidepoint(mouse),
                                 shadow=False)

    # ------------------------------------------------------------------
    # Záložka: BODOVANIE
    # ------------------------------------------------------------------

    def _draw_scoring(self):
        """Záložka Bodovanie (koncept 2026-10-28, 2. verzia): hore trestné
        karty (vejár srdcí + horníci) a vysvietenie horníkov, dole
        aktuálny chuj / bonusy / zvláštne pravidlá bodovania."""
        f = self.frame
        x0, x1 = f.left + 30, f.right - 30
        top = self.tab_bodovanie.bottom + 26
        bottom = f.bottom - 26
        gap = 18
        # Pomer horný : dolný rad ako v koncepte (≈ 62 : 38)
        h1 = round((bottom - top - gap) * 0.62)
        h3 = bottom - top - gap - h1

        # ── Rad 1: TRESTNÉ KARTY | VYSVIETENIE HORNÍKOV ─────────────────
        w_left = round((x1 - x0 - gap) * 0.55)
        r_pen = pygame.Rect(x0, top, w_left, h1)
        r_ill = pygame.Rect(r_pen.right + gap, top, x1 - r_pen.right - gap, h1)
        self._section(r_pen, "TRESTNÉ KARTY",
                      "Tieto karty prinášajú trestné body.")
        self._draw_penalty_cards(r_pen)
        self._section(r_ill, "VYSVIETENIE HORNÍKOV")
        self._draw_illumination(r_ill)

        # ── Rad 2: AKTUÁLNY CHUJ | BONUSY | ZVLÁŠTNE PRAVIDLÁ ───────────
        y3 = r_pen.bottom + gap
        w3 = (x1 - x0 - 2 * gap) // 3
        r_chuj = pygame.Rect(x0, y3, w3, h3)
        r_bon = pygame.Rect(r_chuj.right + gap, y3, w3, h3)
        r_spec = pygame.Rect(r_bon.right + gap, y3, x1 - r_bon.right - gap, h3)
        self._section(r_chuj, "AKTUÁLNY CHUJ")
        self._draw_current_chuj(r_chuj)
        self._section(r_bon, "BONUSY")
        self._draw_badge_rows(r_bon, [
            ("−10 b", (70, 140, 60), "Zobral si všetky trestné", "karty v kole."),
            ("−10 b", (70, 140, 60), "Séria — 5 kôl za sebou", "bez trestného bodu."),
        ])
        self._section(r_spec, "ZVLÁŠTNE PRAVIDLÁ BODOVANIA")
        self._draw_badge_rows(r_spec, [
            ("100 b", None, "Presne 100 bodov", "→ skóre klesne na 90."),
            ("90 b+", None, "Horníci sa nad 90 bodov", "nepočítajú (0 b)."),
        ])

    # --- sekcie Bodovania ---------------------------------------------

    def _section(self, rect: pygame.Rect, title: str, subtitle: str | None = None):
        """Sekcia: o odtieň svetlejší podklad, zlatohnedý rám, zlatý nadpis
        a pod ním jemná deliaca čiara (prípadne podnadpis)."""
        c = self.canvas
        c.overlay(rect, SECTION_FILL, border_radius=SECTION_RADIUS)
        c.overlay((rect.x + 3, rect.y + 3, rect.width - 6, 40),
                  (255, 214, 140, 8), border_radius=SECTION_RADIUS - 3)
        c.rect(ui_style.GOLD_SOFT, rect, width=2, border_radius=SECTION_RADIUS)
        t = self.font_section.render(title, True, ui_style.GOLD)
        c.blit(t, (rect.x + 22, rect.y + 14))
        line_y = rect.y + 14 + t.get_height() + 6
        c.line((70, 54, 34), (rect.x + 20, line_y), (rect.right - 20, line_y), 1)
        if subtitle:
            # podnadpis vedľa nadpisu (šetrí výšku pre karty)
            s = self.font_text.render(subtitle, True, ui_style.TEXT_DIM)
            c.blit(s, s.get_rect(left=rect.x + 22 + t.get_width() + 20,
                                 bottom=rect.y + 14 + t.get_height() - 3))

    def _content_top(self, rect: pygame.Rect, subtitle: bool = False) -> int:
        y = rect.y + 14 + self.font_section.get_height() + 6 + 14
        if subtitle:
            y += self.font_text.get_height() + 8
        return round(y)

    def _badge(self, text: str, center: tuple[int, int], color=None):
        """Červený odznak s bodovou hodnotou (alebo v danej farbe)."""
        c = self.canvas
        surf = self.font_badge.render(text, True, BADGE_TEXT)
        w = surf.get_width() + 28
        h = surf.get_height() + 10
        r = pygame.Rect(0, 0, w, h)
        r.center = center
        fill = color or BADGE_FILL
        border = tuple(min(255, ch + 70) for ch in fill) if color else BADGE_BORDER
        c.overlay(r.move(0, 3), (0, 0, 0, 110), border_radius=h // 2)
        c.rect(fill, r, border_radius=h // 2)
        c.rect(border, r, width=2, border_radius=h // 2)
        c.blit(surf, surf.get_rect(center=r.center))
        return r

    def _card(self, suit: str, rank: str, pos, size, shadow: bool = True,
              border: tuple | None = None):
        c = self.canvas
        img = self._load_card(suit, rank, size)
        if not img:
            return
        if shadow:
            c.overlay((pos[0] + 4, pos[1] + 6, size[0], size[1]), (0, 0, 0, 110),
                      border_radius=8)
        c.blit(img, pos)
        if border:
            c.rect(border, (pos[0], pos[1], size[0], size[1]), width=2,
                   border_radius=8)

    def _centered_lines(self, lines: list[tuple[str, tuple]], cx: int, y: int):
        for text, color in lines:
            s = self.font_text.render(text, True, color)
            self.canvas.blit(s, s.get_rect(centerx=cx, top=y))
            y += self.font_text.get_height() + 2

    def _heart_fan(self, cx: int, cy: int, card_h: int, n: int = 6,
                   spread: float = 30.0) -> pygame.Rect:
        """Vejár n srdcových kariet (mierne natočených) so stredom (cx, cy).
        Vráti logický obdĺžnik, ktorý vejár zaberá."""
        card_w = round(card_h * CARD_RATIO)
        ranks = ("seven", "eight", "nine", "ten", "king", "ace")[-n:]
        step = card_w * FAN_STEP
        area = None
        for i, rank in enumerate(ranks):
            t = i / (n - 1) - 0.5                       # -0.5 … 0.5
            angle = -spread * t                         # vľavo nakloniť doľava
            img = self._load_card_rot("heart", rank, (card_w, card_h), round(angle))
            if not img:
                continue
            pos = (round(cx + t * (n - 1) * step), round(cy + abs(t) * card_h * 0.12))
            r = img.get_rect(center=pos)
            self.canvas.blit(img, r)
            area = r if area is None else area.union(r)
        return area or pygame.Rect(cx, cy, 0, 0)

    def _load_card_rot(self, suit: str, rank: str, size, angle: int):
        try:
            return self.canvas.card(f"{suit}-{rank}.png", angle=angle, lsize=size)
        except (FileNotFoundError, pygame.error):
            return None

    def _medallion(self, center: tuple[int, int], r: int, number: str, unit: str):
        """Okrúhly bordový medailón so zlatým lemom: veľké číslo + jednotka."""
        c = self.canvas
        cx, cy = center
        c.circle((0, 0, 0), (cx + 2, cy + 5), r)
        c.circle((176, 128, 44), (cx, cy), r)               # zlatý lem
        c.circle((112, 20, 16), (cx, cy), r - 5)
        c.circle((150, 34, 26), (cx, cy - r // 6), r - 12)  # svetlejší stred
        c.circle((112, 20, 16), (cx, cy + r // 3), r - 18)
        c.circle((236, 190, 96), (cx, cy), r - 5, width=1)
        big = self.canvas.font(round(r * 0.9)).render(number, True, (255, 236, 200))
        small = self.canvas.font(round(r * 0.42)).render(unit, True, (255, 228, 180))
        c.blit(big, big.get_rect(centerx=cx, bottom=cy + r * 0.22))
        c.blit(small, small.get_rect(centerx=cx, top=cy + r * 0.18))

    def _value_box(self, rect: pygame.Rect, text: str):
        """Hodnota horníka: tmavý rámček so zlatohnedým okrajom, červený text."""
        c = self.canvas
        c.rect((24, 15, 9), rect, border_radius=8)
        c.rect(ui_style.GOLD_SOFT, rect, width=2, border_radius=8)
        s = self.font_section.render(text, True, (232, 92, 70))
        c.blit(s, s.get_rect(center=rect.center))

    @staticmethod
    def _fan_height_for_width(width: float, n: int) -> int:
        """Najväčšia výška karty, pri ktorej sa vejár n kariet zmestí do
        šírky (krok 0,42 šírky karty + rezerva na natočenie)."""
        return int(width / (CARD_RATIO * (1 + FAN_STEP * (n - 1)) + 0.45))

    def _draw_penalty_cards(self, rect: pygame.Rect):
        """Vľavo vejár srdcí s medailónom 1 bod, vpravo podsekcia HORNÍCI."""
        c = self.canvas
        top = self._content_top(rect)
        bottom = rect.bottom - 18
        split = rect.x + round(rect.width * 0.47)

        # --- srdcia (blok vejár + text zvislo na strede) ---
        text = ["Každá srdcová karta", "bez ohľadu na hodnotu."]
        line_h = self.font_text.get_height() + 2
        text_h = len(text) * line_h
        card_h = min(230, bottom - top - text_h - 50,
                     self._fan_height_for_width(split - rect.x - 50, 6))
        block_h = card_h + 30 + text_h
        by = top + (bottom - top - block_h) // 2
        fan_cx = (rect.x + split) // 2
        fan = self._heart_fan(fan_cx, by + card_h // 2, card_h)
        r = max(30, round(card_h * 0.25))
        self._medallion((fan.right - r, fan.bottom - r + 6), r, "1", "bod")
        ty = by + card_h + 30
        for line in text:
            s = self.font_text.render(line, True, ui_style.TEXT)
            c.blit(s, s.get_rect(centerx=fan_cx, top=ty))
            ty += line_h

        # --- HORNÍCI ---
        sub = pygame.Rect(split, top, rect.right - 20 - split, bottom - top)
        c.overlay(sub, SUBSECTION_FILL, border_radius=10)
        c.rect((70, 54, 34), sub, width=1, border_radius=10)
        t = self.font_section.render("HORNÍCI", True, ui_style.GOLD)
        c.blit(t, t.get_rect(centerx=sub.centerx, top=sub.y + 12))
        inner_top = sub.y + 12 + t.get_height() + 10
        box_h = self.font_section.get_height() + 12
        name_h = self.font_text.get_height() + 12
        half = sub.width // 2
        card_h = min(250, sub.bottom - 16 - box_h - name_h - inner_top,
                     int((half - 30) / CARD_RATIO))
        card_w = round(card_h * CARD_RATIO)
        y = inner_top + (sub.bottom - 16 - inner_top - (card_h + name_h + box_h)) // 2
        for i, (suit, name, pts) in enumerate((("leaf", "Zelený horník", "8 bodov"),
                                                ("acorn", "Žaluďový horník", "4 body"))):
            cx = sub.x + half // 2 + i * half
            self._card(suit, "over", (cx - card_w // 2, y), (card_w, card_h))
            s = self.font_text.render(name, True, ui_style.TEXT)
            c.blit(s, s.get_rect(centerx=cx, top=y + card_h + 8))
            box = pygame.Rect(0, 0, min(half - 24, 170), box_h)
            box.midtop = (cx, y + card_h + name_h)
            self._value_box(box, pts)

    def _draw_illumination(self, rect: pygame.Rect):
        """Najprv hodnota každého vysvieteného horníka, potom srdcia za
        2 body pri oboch (poradie zámerne — aby nevznikol dojem, že horníci
        sa zdvojnásobia len pri vysvietení oboch). Pod horníkmi ich hodnota
        pri vysvietení, šípka k vejáru srdcí s medailónom 2 body."""
        c = self.canvas
        top = self._content_top(rect)
        bottom = rect.bottom - 18
        line_h = self.font_text.get_height() + 4
        horn_line = "Každý vysvietený horník zdvojnásobí svoju bodovú hodnotu."
        heart_lines = ["Ak sú vysvietení obaja horníci, majú všetky",
                       "srdcové karty hodnotu 2 body (namiesto 1 bodu)."]
        text_h = line_h + 10 + len(heart_lines) * line_h
        box_h = self.font_section.get_height() + 10

        # Šírka radu: 2 karty + "+" + šípka + vejár 5 kariet
        plus = self.font_title.render("+", True, ui_style.GOLD)
        aw = 40
        fixed = 12 + plus.get_width() + 12 + 22 + aw + 24
        avail_w = rect.width - 60 - fixed
        k = 2 * CARD_RATIO + 0.92 * (CARD_RATIO * (1 + FAN_STEP * 4) + 0.45)
        card_h = min(210, int(avail_w / k), bottom - top - text_h - 26 - box_h - 8)
        card_w = round(card_h * CARD_RATIO)
        block_h = text_h + 26 + card_h + 8 + box_h
        y = top + (bottom - top - block_h) // 2

        s = self.font_text.render(horn_line, True, ILLUM_COLOR)
        c.blit(s, s.get_rect(centerx=rect.centerx, top=y))
        y += line_h + 10
        for line in heart_lines:
            s = self.font_text.render(line, True, ui_style.TEXT)
            c.blit(s, s.get_rect(centerx=rect.centerx, top=y))
            y += line_h
        y += 26

        fan_h = round(card_h * 0.92)
        fan_w = round(fan_h * (CARD_RATIO * (1 + FAN_STEP * 4) + 0.45))
        row_w = 2 * card_w + fixed + fan_w
        x = rect.centerx - row_w // 2
        mid = y + card_h // 2
        for suit, pts in (("leaf", "16 bodov"), ("acorn", "8 bodov")):
            self._card(suit, "over", (x, y), (card_w, card_h), border=ILLUM_COLOR)
            box = pygame.Rect(0, 0, card_w + 34, box_h)
            box.midtop = (x + card_w // 2, y + card_h + 8)
            self._value_box(box, pts)
            x += card_w
            if suit == "leaf":
                x += 12
                c.blit(plus, plus.get_rect(midleft=(x, mid)))
                x += plus.get_width() + 12
        x += 22
        c.polygon(ui_style.GOLD, [(x, mid - 7), (x + aw - 16, mid - 7),
                                  (x + aw - 16, mid - 16), (x + aw, mid),
                                  (x + aw - 16, mid + 16), (x + aw - 16, mid + 7),
                                  (x, mid + 7)])
        x += aw + 24
        fan = self._heart_fan(x + fan_w // 2, mid, fan_h, n=5, spread=26)
        r = max(30, round(fan_h * 0.27))
        self._medallion((fan.right - r, fan.bottom - r + 6), r, "2", "body")

    def _draw_current_chuj(self, rect: pygame.Rect):
        c = self.canvas
        top = self._content_top(rect)
        icon = self._chuj_icon
        lines = ["Hráč s touto ikonkou má", "momentálne najviac bodov",
                 "a prehrá, ak prekročí 100."]
        line_h = self.font_text.get_height() + 4
        text_h = len(lines) * line_h
        area_h = rect.bottom - 14 - top
        if icon:
            c.blit(icon, icon.get_rect(midleft=(rect.x + 24, top + area_h // 2)))
        tx = rect.x + 24 + (icon.get_width() + 20 if icon else 0)
        ty = top + (area_h - text_h) // 2
        for line in lines:
            s = self.font_text.render(line, True, ui_style.TEXT)
            c.blit(s, (tx, ty))
            ty += line_h

    def _draw_badge_rows(self, rect: pygame.Rect, rows: list):
        """Riadky: odznak (farebný alebo zlatý rámik) + dvojriadkový text."""
        c = self.canvas
        top = self._content_top(rect)
        area_h = rect.bottom - 14 - top
        row_h = area_h // len(rows)
        line_h = self.font_text.get_height() + 2
        for i, (badge, color, l1, l2) in enumerate(rows):
            cy = top + i * row_h + row_h // 2
            surf = self.font_badge.render(badge, True,
                                          BADGE_TEXT if color else ui_style.GOLD)
            bw, bh = 96, surf.get_height() + 14
            br = pygame.Rect(rect.x + 22, cy - bh // 2, bw, bh)
            if color:
                c.rect(color, br, border_radius=10)
                c.rect(tuple(min(255, ch + 70) for ch in color), br, width=2,
                       border_radius=10)
            else:
                c.rect((40, 27, 14), br, border_radius=10)
                c.rect(ui_style.GOLD_SOFT, br, width=2, border_radius=10)
            c.blit(surf, surf.get_rect(center=br.center))
            tx = br.right + 18
            for j, text in enumerate((l1, l2)):
                s = self.font_text.render(text, True, ui_style.TEXT)
                c.blit(s, (tx, cy - line_h + j * line_h))

    # ------------------------------------------------------------------
    # Záložka: PRAVIDLÁ
    # ------------------------------------------------------------------

    def _draw_rules(self):
        """Záložka Pravidlá (finálny koncept 2026-10-28): Cieľ hry (nízky
        pás), Priebeh kola v 5 krokoch, dole animovaná ukážka pravidiel
        štichov (gui/rules_demo.py) a vpravo Vysvietenie a Záväzky."""
        f = self.frame
        x0, x1 = f.left + 30, f.right - 30
        top = self.tab_bodovanie.bottom + 26
        bottom = f.bottom - 26
        gap = 16
        h_goal, h_flow = 80, 232

        r_goal = pygame.Rect(x0, top, x1 - x0, h_goal)
        self._draw_rules_goal(r_goal)

        r_flow = pygame.Rect(x0, r_goal.bottom + gap, x1 - x0, h_flow)
        self._section(r_flow, "PRIEBEH KOLA")
        self._draw_rules_flow(r_flow)

        y = r_flow.bottom + gap
        h = bottom - y
        w_demo = round((x1 - x0 - gap) * 0.638)
        r_demo = pygame.Rect(x0, y, w_demo, h)
        self._panel_bg(r_demo)
        self.rules_demo.layout(r_demo)
        self.rules_demo.draw(display.mouse_pos())

        rx = r_demo.right + gap
        hr = (h - gap) // 2
        r_ill = pygame.Rect(rx, y, x1 - rx, hr)
        r_decl = pygame.Rect(rx, y + hr + gap, x1 - rx, h - hr - gap)
        self._section(r_ill, "VYSVIETENIE HORNÍKOV")
        self._draw_rules_illumination(r_ill)
        self._section(r_decl, "ZÁVÄZKY")
        self._draw_rules_declarations(r_decl)

    def _panel_bg(self, rect: pygame.Rect):
        c = self.canvas
        c.overlay(rect, SECTION_FILL, border_radius=SECTION_RADIUS)
        c.overlay((rect.x + 3, rect.y + 3, rect.width - 6, 40),
                  (255, 214, 140, 8), border_radius=SECTION_RADIUS - 3)
        c.rect(ui_style.GOLD_SOFT, rect, width=2, border_radius=SECTION_RADIUS)

    # --- pomocné kreslenie Pravidiel ------------------------------------

    def _wrap_plain(self, text: str, font, width: float) -> list[str]:
        words, lines, line = text.split(), [], ""
        for word in words:
            test = f"{line} {word}".strip()
            if line and font.size(test)[0] > width:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines

    def _rules_icon(self, key: str, size: int):
        """Ikonka z RULES_ICON_FILES (dodaná grafika), inak záložná."""
        for name in RULES_ICON_FILES[key]:
            path = os.path.join("assets", "graphics", name)
            if os.path.exists(path):
                try:
                    raw = pygame.image.load(path)
                    w = round(size * raw.get_width() / raw.get_height())
                    return self.canvas.image(path, (w, size))
                except pygame.error:
                    continue
        return None

    def _small_card(self, name: str, pos, h: int, border=None):
        """Karta podľa mena súboru ("bell-nine") vo výške h."""
        suit, rank = name.split("-")
        self._card(suit, rank, pos, (round(h * CARD_RATIO), h), shadow=False,
                   border=border)

    def _arrow(self, x: int, y: int, length: int = 22, color=None):
        """Malá zlatá šípka doprava, ľavý koniec v (x, y)."""
        color = color or ui_style.GOLD
        t = max(4, length // 5)
        hd = max(8, length // 2)
        self.canvas.polygon(color, [(x, y - t // 2), (x + length - hd, y - t // 2),
                                    (x + length - hd, y - hd // 2 - 2), (x + length, y),
                                    (x + length - hd, y + hd // 2 + 2),
                                    (x + length - hd, y + t // 2), (x, y + t // 2)])

    def _number_circle(self, center, r: int, number: str):
        c = self.canvas
        c.circle((0, 0, 0), (center[0] + 1, center[1] + 3), r)
        c.circle(ui_style.GOLD, center, r)
        c.circle((150, 104, 30), center, r, width=2)
        s = self.canvas.font(round(r * 1.25)).render(number, True, (40, 24, 8))
        c.blit(s, s.get_rect(center=center))

    # --- sekcie Pravidiel -------------------------------------------------

    def _draw_rules_goal(self, rect: pygame.Rect):
        """Nízky pás: trofej, nadpis CIEĽ HRY a jedna veta."""
        c = self.canvas
        self._panel_bg(rect)
        icon = self._rules_icon("goal", rect.height - 18)
        x = rect.x + 24
        if icon:
            c.blit(icon, icon.get_rect(midleft=(x, rect.centery)))
            x += icon.get_width() + 22
        t = self.font_section.render("CIEĽ HRY", True, ui_style.GOLD)
        c.blit(t, t.get_rect(midleft=(x, rect.centery)))
        x += t.get_width() + 28
        s = self.font_text.render(
            "Zbieraj čo najmenej trestných bodov. Kto ako prvý prekročí "
            "100 bodov, prehráva a stáva sa Chujom.", True, ui_style.TEXT)
        c.blit(s, s.get_rect(midleft=(x, rect.centery)))

    def _draw_rules_flow(self, rect: pygame.Rect):
        """Päť krokov kola: číslo + názov, ilustrácia, krátky popis."""
        c = self.canvas
        top = self._content_top(rect) - 6
        bottom = rect.bottom - 12
        steps = (
            ("Rozdanie", "Každý dostane 8 kariet."),
            ("Vysvietenie", "Môžeš priznať horníka."),
            ("Záväzok", "Môžeš sa zaviazať."),
            ("8 štichov", "Hráči zahrajú všetky karty."),
            ("Bodovanie", "Spočítajú sa trestné body."),
        )
        n = len(steps)
        x_start, x_end = rect.x + 16, rect.right - 16
        col_w = (x_end - x_start) / n
        head_h = 36
        desc_font = self.canvas.font(21)
        desc_h = desc_font.get_height()
        ill_top = top + head_h + 4
        ill_h = bottom - desc_h - 8 - ill_top
        for i, (title, desc) in enumerate(steps):
            cx0 = round(x_start + i * col_w)
            cw = round(col_w)
            mid = cx0 + cw // 2
            if i > 0:
                c.line((70, 54, 34), (cx0, top + 4), (cx0, bottom - 4), 1)
            t = self.font_section.render(title, True, ui_style.GOLD)
            r = 17
            total = 2 * r + 12 + t.get_width()
            hx = mid - total // 2
            self._number_circle((hx + r, top + head_h // 2), r, str(i + 1))
            c.blit(t, t.get_rect(midleft=(hx + 2 * r + 12, top + head_h // 2)))
            area = pygame.Rect(cx0 + 22, ill_top, cw - 44, ill_h)
            self._flow_illustration(i, area)
            if i < n - 1:
                self._arrow(cx0 + cw - 12, area.centery, 24)
            s = desc_font.render(desc, True, ui_style.TEXT)
            c.blit(s, s.get_rect(centerx=mid, bottom=bottom))

    def _flow_illustration(self, step: int, area: pygame.Rect):
        c = self.canvas
        cx, cy = area.center
        h = min(area.height - 4, 116)
        w = round(h * CARD_RATIO)
        if step == 0:          # rozdanie — vejár rubov
            n, stp = 5, w * 0.34
            for i in range(n):
                t = i / (n - 1) - 0.5
                img = self._load_card_rot_name("card-back.png", (w, h), round(-22 * t))
                if img:
                    c.blit(img, img.get_rect(center=(round(cx + t * (n - 1) * stp),
                                                     round(cy + abs(t) * h * 0.08))))
        elif step == 1:        # vysvietenie — oba horníci
            g = 12
            self._small_card("leaf-over", (cx - w - g // 2, cy - h // 2), h)
            self._small_card("acorn-over", (cx + g // 2, cy - h // 2), h)
        elif step == 2:        # záväzok — oba záväzky (bez štítkov)
            box_w = (area.width - 20) // 2
            for j, key in enumerate(("all", "none")):
                bx = cx + (j - 0.5) * (box_w + 20)
                self._decl_visual(key, (round(bx), cy), (box_w, area.height - 2))
        elif step == 3:        # 8 štichov — tri zahrané karty
            h2 = min(h, 100)
            w2 = round(h2 * CARD_RATIO)
            for k, (name, dx, ang) in enumerate((("heart-nine", -w2 * 0.8, 10),
                                                  ("heart-under", 0, 0),
                                                  ("leaf-over", w2 * 0.8, -10))):
                img = self._load_card_rot_name(f"{name}.png", (w2, h2), ang)
                if img:
                    c.blit(img, img.get_rect(center=(round(cx + dx), cy + (6 if k != 1 else -4))))
        else:                  # bodovanie — zápisník
            icon = self._rules_icon("scoring", min(h, 112))
            if icon:
                c.blit(icon, icon.get_rect(center=(cx, cy)))

    def _decl_visual(self, key: str, center, size) -> int:
        """Obrázok záväzku: obdĺžnikový výrez ikonky z hry (DECL_CROP, bez
        lúčov) v zaoblenom rámiku — zlatom pre Beriem všetko, zelenom pre
        Nechytím nič. Zmestí sa do obdĺžnika `size` so stredom `center`;
        vráti použitú šírku."""
        c = self.canvas
        w, h = size
        x0, x1, y0, y1 = DECL_CROP
        aspect = (x1 - x0) / (y1 - y0)
        cw = min(w, round(h * aspect))
        ch = round(cw / aspect)
        img = self._decl_crop(os.path.join("assets", "graphics", f"{key}.png"), (cw, ch))
        if img:
            r = img.get_rect(center=center)
            c.blit(img, r)
            col = ui_style.GOLD if key == "all" else (96, 190, 80)
            c.rect(col, r, width=2, border_radius=12)
        return cw

    def _decl_crop(self, path: str, size: tuple[int, int]):
        """Obdĺžnikový výrez ikonky (DECL_CROP) so zaoblenými rohmi — vo
        fyzickom rozlíšení, cachované."""
        key = (path, size)
        cache = self.__dict__.setdefault("_decl_crop_cache", {})
        if key in cache:
            return cache[key]
        from gui.canvas import LSurf
        try:
            raw = pygame.image.load(path).convert_alpha()
        except (FileNotFoundError, pygame.error):
            cache[key] = None
            return None
        n_w, n_h = raw.get_size()
        x0, x1, y0, y1 = DECL_CROP
        crop = raw.subsurface((round(x0 * n_w), round(y0 * n_h),
                               round((x1 - x0) * n_w), round((y1 - y0) * n_h)))
        pw = max(1, round(size[0] * self.canvas.s))
        ph = max(1, round(size[1] * self.canvas.s))
        img = pygame.transform.smoothscale(crop, (pw, ph))
        tile = pygame.Surface((pw, ph), pygame.SRCALPHA)
        tile.fill((24, 15, 9, 255))
        tile.blit(img, (0, 0))
        mask = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_radius=round(12 * self.canvas.s))
        tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        cache[key] = LSurf(tile, *size)
        return cache[key]

    def _load_card_rot_name(self, name: str, size, angle: int):
        try:
            return self.canvas.card(name, angle=angle, lsize=size)
        except (FileNotFoundError, pygame.error):
            return None

    def _draw_rules_illumination(self, rect: pygame.Rect):
        """Oba horníci vľavo, princíp vysvietenia vpravo (bez bodov)."""
        c = self.canvas
        top = self._content_top(rect)
        bottom = rect.bottom - 16
        card_h = min(160, bottom - top)
        card_w = round(card_h * CARD_RATIO)
        y = top + (bottom - top - card_h) // 2
        x = rect.x + 24
        self._card("leaf", "over", (x, y), (card_w, card_h))
        self._card("acorn", "over", (x + card_w + 12, y), (card_w, card_h))
        tx = x + 2 * card_w + 12 + 24
        font = self.canvas.font(21)
        line_h = font.get_height() + 3
        paras = ["Pred prvým štichom môžeš priznať zeleného horníka, "
                 "žaluďového horníka alebo oboch.",
                 "Vysvieteného horníka vidia všetci súperi."]
        lines = []
        for p in paras:
            lines += self._wrap_plain(p, font, rect.right - 20 - tx) + [""]
        lines = lines[:-1]
        text_h = sum(line_h if ln else 10 for ln in lines)
        ty = y + card_h // 2 - text_h // 2
        for ln in lines:
            if ln:
                c.blit(font.render(ln, True, ui_style.TEXT), (tx, ty))
                ty += line_h
            else:
                ty += 10

    def _draw_rules_declarations(self, rect: pygame.Rect):
        """Dva riadky: ikonka záväzku z hry, štítok a jedna veta (bez bodov)."""
        c = self.canvas
        top = self._content_top(rect)
        bottom = rect.bottom - 12
        row_h = (bottom - top) // 2
        font = self.canvas.font(21)
        line_h = font.get_height() + 3
        green = (96, 190, 80)
        rows = (("all", "Beriem všetko", ui_style.GOLD,
                 "Zaväzuješ sa vyhrať všetkých 8 štichov."),
                ("none", "Nechytím nič", green,
                 "Zaväzuješ sa nezobrať ani jeden štich."))
        pill_w = max(self.font_text.size(r[1])[0] for r in rows) + 30
        for i, (key, label, col, text) in enumerate(rows):
            cy = top + i * row_h + row_h // 2
            if i > 0:
                c.line((52, 40, 26), (rect.x + 20, top + i * row_h),
                       (rect.right - 20, top + i * row_h), 1)
            vis_w = 150
            x = rect.x + 22
            used = self._decl_visual(key, (x + vis_w // 2, cy), (vis_w, row_h - 6))
            x += max(used, vis_w) + 16
            pr = pygame.Rect(x, cy - 20, pill_w, 40)
            c.rect((24, 15, 9), pr, border_radius=10)
            c.rect(col, pr, width=2, border_radius=10)
            s = self.font_text.render(label, True, col)
            c.blit(s, s.get_rect(center=pr.center))
            tx = pr.right + 16
            lines = self._wrap_plain(text, font, rect.right - 18 - tx)
            ty = cy - len(lines) * line_h // 2
            for ln in lines:
                c.blit(font.render(ln, True, ui_style.TEXT), (tx, ty))
                ty += line_h

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _section_title(self, text: str, x: int, y: int,
                        center: bool = False):
        surf = self.font_medium.render(text, True, COLOR_GOLD)
        rx = x if not center else surf.get_rect(centerx=x).x
        self.canvas.blit(surf, (rx, y))
        line_y = y + surf.get_height() + 2
        line_w = surf.get_width() if not center else SCREEN_WIDTH - 160
        lx = rx if not center else 80
        self.canvas.line(COLOR_GOLD,
                         (lx, line_y), (lx + line_w, line_y), 1)

    def _text_block(self, x: int, y: int, max_w: int,
                    lines: list[str]) -> int:
        """Vypíše blok textu, vráti y po poslednom riadku."""
        for line in lines:
            if not line:
                y += 10
                continue
            surf = self._render_with_icons(line, self.font_small, COLOR_WHITE)
            self.canvas.blit(surf, (x, y))
            y += 24
        return y

    def _draw_badge_line(self, x: int, y: int, badge: str,
                          text: str, color: tuple):
        """Nakreslí riadok s farebným odznakom a textom."""
        # Odznak
        badge_surf = self.font_small.render(badge, True, color)
        bw = badge_surf.get_width() + 16
        bh = badge_surf.get_height() + 6
        self.canvas.overlay(pygame.Rect((x, y - 3), (bw, bh)), (0, 0, 0, 120))
        self.canvas.rect(color,
                         (x, y - 3, bw, bh), width=1, border_radius=4)
        self.canvas.blit(badge_surf, (x + 8, y))

        # Text
        txt = self.font_small.render(text, True, COLOR_WHITE)
        self.canvas.blit(txt, (x + bw + 10, y))

    def _load_card(self, suit: str, rank: str, size: tuple[int, int]):
        """Karta v logickej veľkosti (Canvas — ostrá aj na 4K; predtým
        medium + transform.scale každú snímku)."""
        try:
            return self.canvas.card(f"{suit}-{rank}.png", lsize=size)
        except (FileNotFoundError, pygame.error):
            return None

    def _load_suit_icons(self):
        """Načíta malé suit ikony a škáluje ich na výšku textu."""
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
                # Zachovaj pomer strán, výška = icon_h
                w, h = pygame.image.load(path).get_size()
                new_w = int(w * icon_h / h)
                self._suit_icons[symbol] = self.canvas.image(path, (new_w, icon_h))
            except (FileNotFoundError, pygame.error):
                self._suit_icons[symbol] = None

    def _load_declaration_icons(self):
        """Ikonky záväzkov (all/none) pre sekciu ZÁVÄZOK v záložke
        Pravidlá — rovnaké obrázky ako badge v round_status.py/
        phase_renderer.py. Výška = 3 textové riadky (popis + splnené +
        nesplnené), nech sú dobre čitateľné, nie vtesnané do jedného
        riadku."""
        self._declaration_icons: dict = {}
        icon_side = int(self._row_h * 3 - 8)
        for key in ("all", "none"):
            path = os.path.join("assets", "graphics", f"{key}.png")
            try:
                self._declaration_icons[key] = self.canvas.image(
                    path, (icon_side, icon_side))
            except (FileNotFoundError, pygame.error):
                self._declaration_icons[key] = None

    def _load_chuj_icon(self):
        """Ikonka chuja (hráč s momentálne najviac bodmi) pre vysvetlenie
        v záložke Bodovanie — rovnaký obrázok aj rovnaká veľkosť ako na
        stole (phase_renderer.py::_chuj_icon, 100x100)."""
        path = os.path.join("assets", "graphics", "chuj.png")
        try:
            self._chuj_icon = self.canvas.image(path, (100, 100))
        except (FileNotFoundError, pygame.error):
            self._chuj_icon = None

    def _render_with_icons(self, text: str, font, color: tuple):
        """
        Vykreslí text, kde sú suit symboly nahradené ikonkami. Vracia
        LSurf (fyzické pixely, logické rozmery — gui/canvas.py).
        """
        import re
        # Rozdeľ text na časti — text a symboly
        parts = re.split(r'([♠♣♥●])', text)

        surfaces = []
        for part in parts:
            if part in self._suit_icons and self._suit_icons[part]:
                surfaces.append(self._suit_icons[part])
            elif part:
                surfaces.append(font.render(part, True, color))

        if not surfaces:
            return font.render(text, True, color)

        # Vertikálne centrovanie na výšku riadku (aspoň výška písma)
        s = self.canvas.s
        total_w = sum(p.phys.get_width() for p in surfaces)
        max_h = max([round(font.get_height() * s)]
                    + [p.phys.get_height() for p in surfaces])
        result = pygame.Surface((max(1, total_w), max(1, max_h)), pygame.SRCALPHA)
        x = 0
        for surf in surfaces:
            result.blit(surf.phys, (x, (max_h - surf.phys.get_height()) // 2))
            x += surf.phys.get_width()
        from gui.canvas import LSurf
        return LSurf(result, round(total_w / s), round(max_h / s))

    def __repr__(self) -> str:
        return f"InfoOverlay(visible={self.visible})"