# gui/rules_demo.py
#
# Animovaná ukážka pravidiel štichov — panel "PRAVIDLÁ ŠTICHOV" v okne
# Pravidlá a bodovanie (gui/info_overlay.py, koncept 2026-10-28).
#
# Šesť pevných scén (nie náhodné rozdanie), každá trvá SCENE_LEN sekúnd:
#   0–1 s  príprava (karty na stole, názov),
#   1–3 s  animácia (pohyb kariet),
#   3–6 s  výsledok so zvýraznením a poznámkou,
#   6–7 s  plynulý prechod do ďalšej scény.
# Animujú sa len karty, text sa nemení. Ukážka nesiaha na herný stav —
# kreslí vlastné karty podľa mien súborov.
#
# Správnosť príkladov (farba, poradie, víťaz, povolené karty) overuje
# verify_scenes() skutočnými triedami hry Trick a Hand —
# tester/regression_rules_demo.py.
#
# Ovládanie: Predchádzajúce / Ďalšie / bodky (ručný výber = scéna sa prehrá
# raz a ostane stáť na výsledku), Pozastaviť / Prehrať. Pri otvorení okna
# reset() — začína sa scénou 1.

import math
import os

import pygame

from gui import ui_style
from gui.canvas import TABLE_BG_PATH

SCENE_LEN = 7.0
HOLD_AT = 5.9                  # ručne zvolená scéna zastane na výsledku
CARD_RATIO = 181 / 293

GREEN = (96, 200, 80)
RED = (220, 60, 45)
NAME_DIM = (150, 132, 108)

SEATS = ("Hráč", "Počítač 1", "Počítač 2", "Počítač 3")   # index = hráč v hre

# Scény: názov, veta, poznámka (2 riadky)
SCENES = (
    ("Hráč určí farbu", "Hráč, ktorý začína štich, určuje jeho farbu.",
     ("Počítač 1 vyniesol zeleň —", "hraná farba štichu je zelená.")),
    ("Musíš priznať farbu", "Ak máš kartu hranej farby, musíš ju zahrať.",
     ("Máš zeleného dolníka —", "musíš zahrať zeleň.")),
    ("Nemáš farbu", "Ak nemáš hranú farbu, môžeš zahrať ľubovoľnú kartu.",
     ("Zeleň nemáš — môžeš zahrať", "ktorúkoľvek kartu.")),
    ("Najvyššia karta vyhráva", "Štich berie najvyššia karta hranej farby.",
     ("Žaluďové eso je vyššie, ale nie je", "v hranej farbe — štich nezoberie.")),
    ("Víťaz začína ďalší štich", "Víťaz štichu začína nasledujúci štich.",
     ("Počítač 2 zobral štich —", "teraz vynáša on.")),
    ("Prvý štich bez červene",
     "V prvom štichu sa nesmie viesť červeň. Neplatí pri aktívnom záväzku.",
     ("Neplatí pri aktívnom záväzku", "(Beriem všetko / Nechytím nič).")),
)

# Karty jednotlivých scén — jediný zdroj pre kreslenie aj verify_scenes()
S2_LEAD = (3, "leaf-nine")
S2_HAND = ("heart-ace", "bell-king", "leaf-under", "acorn-ten")
S2_PLAY = "leaf-under"
S3_LEAD = (3, "leaf-nine")
S3_HAND = ("heart-seven", "bell-ace", "acorn-king")
S3_PLAY = "bell-ace"
S4_TRICK = ((1, "leaf-nine"), (2, "leaf-king"), (3, "acorn-ace"), (0, "leaf-under"))
S4_WINNER = 2
S5_NEXT = "bell-ace"
S6_HAND = ("heart-ace", "bell-ten", "leaf-seven", "acorn-eight")
S6_FORBIDDEN = "heart-ace"
S6_PLAY = "bell-ten"


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _lerp(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def _arc(a, b, k, bend=0.18):
    """Pohyb po jemnom oblúku (karta "letí"), nie po priamke."""
    x, y = _lerp(a, b, k)
    dx, dy = b[0] - a[0], b[1] - a[1]
    lift = math.sin(math.pi * k) * bend
    return (x - dy * lift, y + dx * lift)


def verify_scenes() -> list[str]:
    """Overí príklady skutočnou logikou hry. Vráti zoznam chýb."""
    from game.card import Card
    from game.hand import Hand
    from game.trick import Trick

    def card(name):
        suit, rank = name.split("-")
        return Card(suit, rank)

    def hand(names):
        h = Hand()
        h.add_cards([card(n) for n in names])
        return h

    errors = []
    lead_suit = card(S2_LEAD[1]).suit
    playable = {c.image_name for c in hand(S2_HAND).get_playable_cards(lead_suit, 1)}
    if playable != {S2_PLAY + ".png"}:
        errors.append(f"scéna 2: povolené {playable}, čakané len {S2_PLAY}")
    playable = {c.image_name for c in hand(S3_HAND).get_playable_cards(lead_suit, 1)}
    if playable != {n + ".png" for n in S3_HAND}:
        errors.append(f"scéna 3: povolené {playable}, čakané všetky")
    trick = Trick([None] * 4, S4_TRICK[0][0])
    for idx, name in S4_TRICK:
        trick.play_card(idx, card(name))
    if trick.get_winner_index() != S4_WINNER:
        errors.append(f"scéna 4: víťaz {trick.get_winner_index()}, čakaný {S4_WINNER}")
    order = [idx for idx, _ in S4_TRICK]
    if order != [(order[0] + i) % 4 for i in range(4)]:
        errors.append(f"scéna 4: poradie hráčov {order} nie je proti smeru hodín")
    playable = {c.image_name for c in hand(S6_HAND).get_playable_cards(None, 0, False)}
    if S6_FORBIDDEN + ".png" in playable or S6_PLAY + ".png" not in playable:
        errors.append(f"scéna 6: povolené {playable}")
    allowed_decl = {c.image_name for c in hand(S6_HAND).get_playable_cards(None, 0, True)}
    if S6_FORBIDDEN + ".png" not in allowed_decl:
        errors.append("scéna 6: pri záväzku by červeň mala byť povolená")
    return errors


class TrickRulesDemo:
    def __init__(self, canvas):
        self.canvas = canvas
        self.font_head = canvas.font(30)
        self.font_title = canvas.font(32)
        self.font_text = canvas.font(24)
        self.font_note = canvas.font(19)
        self.font_seat = canvas.font(18)
        self.font_btn = canvas.font(21)
        self.rect = pygame.Rect(0, 0, 1100, 516)
        self._stage_cache = None
        self.reset()

    # --- stav -------------------------------------------------------------

    def reset(self):
        self.scene = 0
        self.playing = True
        self.hold_at: float | None = None
        self._t0 = pygame.time.get_ticks()

    def _elapsed(self) -> float:
        t = (pygame.time.get_ticks() - self._t0) / 1000.0
        if self.playing:
            while t >= SCENE_LEN:
                t -= SCENE_LEN
                self.scene = (self.scene + 1) % len(SCENES)
                self._t0 += int(SCENE_LEN * 1000)
            return t
        return min(t, self.hold_at if self.hold_at is not None else HOLD_AT)

    def select(self, index: int):
        """Ručný výber scény — prehrá sa raz a zastane na výsledku."""
        self.scene = index % len(SCENES)
        self.playing = False
        self.hold_at = HOLD_AT
        self._t0 = pygame.time.get_ticks()

    def toggle_play(self):
        t = self._elapsed()
        if self.playing:
            self.playing = False
            self.hold_at = t
        else:
            self.playing = True
            self.hold_at = None
            if t >= HOLD_AT:          # zo zastaveného výsledku plynulo ďalej
                t = HOLD_AT
        self._t0 = pygame.time.get_ticks() - int(t * 1000)

    # --- rozloženie -------------------------------------------------------

    def layout(self, rect: pygame.Rect):
        self.rect = pygame.Rect(rect)
        r = self.rect
        self.stage = pygame.Rect(r.x + 20, r.y + 66, r.width - 40, r.height - 66 - 74)
        by = r.bottom - 62
        self.btn_prev = pygame.Rect(r.x + 22, by, 220, 44)
        self.btn_next = pygame.Rect(r.right - 22 - 250 - 16 - 170, by, 170, 44)
        self.btn_play = pygame.Rect(r.right - 22 - 250, by, 250, 44)
        dots_x = (self.btn_prev.right + self.btn_next.left) // 2 - 75
        self.dots = [pygame.Rect(dots_x + i * 30 - 10, by + 12, 20, 20)
                     for i in range(len(SCENES))]
        # stôl: stred, rozostupy a veľkosť kariet podľa výšky javiska
        st = self.stage
        k = st.height / 370
        self.k = k
        self.cw = round(86 * k)
        cx, cy = st.x + round(st.width * 340 / 1060), st.centery
        self.center = (cx, cy)
        dy, dx = round(82 * k), round(112 * k)
        self.spot = {0: (cx, cy + dy), 1: (cx + dx, cy), 2: (cx, cy - dy), 3: (cx - dx, cy)}
        ldy, ldx = round(168 * k), round(225 * k)
        self.label = {0: (cx, cy + ldy), 1: (cx + ldx, cy), 2: (cx, cy - ldy), 3: (cx - ldx, cy)}
        sdy, sdx = round(260 * k), round(330 * k)
        self.seat = {0: (cx, cy + sdy), 1: (cx + sdx, cy), 2: (cx, cy - sdy), 3: (cx - sdx, cy)}
        self.text_x = st.x + round(st.width * 0.64)
        self.hand_y = st.bottom - round(90 * k)

    def hand_pos(self, i: int, n: int) -> tuple[int, int]:
        step = round(70 * self.k)
        x0 = self.text_x + round(40 * self.k)
        return (x0 + i * step, self.hand_y)

    # --- udalosti ---------------------------------------------------------

    def handle_click(self, pos) -> bool:
        if self.btn_prev.collidepoint(pos):
            self.select(self.scene - 1)
            return True
        if self.btn_next.collidepoint(pos):
            self.select(self.scene + 1)
            return True
        if self.btn_play.collidepoint(pos):
            self.toggle_play()
            return True
        for i, d in enumerate(self.dots):
            if d.inflate(10, 10).collidepoint(pos):
                self.select(i)
                return True
        return False

    # --- kreslenie --------------------------------------------------------

    def draw(self, mouse_pos):
        c = self.canvas
        t = self._elapsed()
        r = self.rect
        # hlavička
        title = self.font_head.render("PRAVIDLÁ ŠTICHOV", True, ui_style.GOLD)
        c.blit(title, (r.x + 22, r.y + 14))
        num = self.font_head.render(f"{self.scene + 1} / {len(SCENES)}", True, ui_style.GOLD)
        c.blit(num, num.get_rect(right=r.right - 24, top=r.y + 14))
        c.line((70, 54, 34), (r.x + 20, r.y + 56), (r.right - 20, r.y + 56), 1)

        self._draw_stage()
        fade = 1.0
        if self.playing and t > SCENE_LEN - 1:
            fade = 1 - _ease(t - (SCENE_LEN - 1))      # prechod do ďalšej scény
        if t < 0.4:
            fade = min(fade, _ease(t / 0.4))
        self._draw_labels(self._glow_seat(t))
        getattr(self, f"_scene{self.scene + 1}")(t, fade)
        self._draw_text(fade)
        self._draw_controls(mouse_pos)

    def _draw_stage(self):
        """Tmavý výrez dreveného stola so zaoblenými rohmi (cachované)."""
        c = self.canvas
        pr = c.prect(self.stage)
        key = (pr.size, c.target.get_size())
        if self._stage_cache is None or self._stage_cache[0] != key:
            surf = pygame.Surface(pr.size, pygame.SRCALPHA)
            if os.path.exists(TABLE_BG_PATH):
                bg = c.background(TABLE_BG_PATH, c.target.get_size())
                src = pygame.Rect(pr.topleft, pr.size).clip(bg.get_rect())
                surf.blit(bg, (0, 0), src)
            else:
                surf.fill((45, 28, 15))
            dark = pygame.Surface(pr.size, pygame.SRCALPHA)
            dark.fill((0, 0, 0, 125))
            surf.blit(dark, (0, 0))
            mask = pygame.Surface(pr.size, pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                             border_radius=round(10 * c.s))
            surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            self._stage_cache = (key, surf)
        c.target.blit(self._stage_cache[1], pr.topleft)
        c.rect((70, 54, 34), self.stage, width=1, border_radius=10)

    def _glow_seat(self, t) -> int | None:
        s = self.scene
        if s == 0:
            return 1
        if s in (1, 2, 5):
            return 0
        if s in (3, 4):
            return 2 if t >= 3.0 else None
        return None

    def _draw_labels(self, glow: int | None):
        c = self.canvas
        for idx, pos in self.label.items():
            g = idx == glow
            t = self.font_seat.render(SEATS[idx], True, ui_style.GOLD if g else NAME_DIM)
            r = t.get_rect(center=pos).inflate(14, 6)
            c.rect((15, 10, 6), r, border_radius=6)
            c.rect(ui_style.GOLD if g else (70, 54, 34), r, width=2 if g else 1,
                   border_radius=6)
            c.blit(t, t.get_rect(center=pos))

    def _draw_text(self, fade: float):
        """Názov pravidla a vysvetlenie na tmavom podklade (čitateľnosť
        nad kresbou dreva)."""
        c = self.canvas
        title, line, _note = SCENES[self.scene]
        x = self.text_x
        w = self.stage.right - 18 - x
        lines = _wrap(line, self.font_text, w - 36)
        line_h = self.font_text.get_height() + 4
        box_h = 20 + self.font_title.get_height() + 12 + len(lines) * line_h + 18
        box = pygame.Rect(x, self.stage.y + 18, w, box_h)
        c.overlay(box, (12, 8, 5, 215), border_radius=10)
        c.rect(ui_style.GOLD_SOFT, box, width=1, border_radius=10)
        c.rect(ui_style.GOLD, (box.x + 1, box.y + 14, 4, box_h - 28))   # zlatý akcent vľavo
        y = box.y + 20
        sh = self.font_title.render(title, True, (0, 0, 0))
        s = self.font_title.render(title, True, ui_style.GOLD)
        c.blit(sh, (box.x + 20 + 2, y + 2))
        c.blit(s, (box.x + 20, y))
        y += s.get_height() + 12
        for ln in lines:
            s = self.font_text.render(ln, True, ui_style.TEXT)
            c.blit(s, (box.x + 20, y))
            y += line_h

    def _draw_controls(self, mouse):
        c = self.canvas
        ui_style.draw_button(c, self.btn_prev, "‹  Predchádzajúce", self.font_btn, 3,
                             self.btn_prev.collidepoint(mouse), shadow=False)
        ui_style.draw_button(c, self.btn_next, "Ďalšie  ›", self.font_btn, 3,
                             self.btn_next.collidepoint(mouse), shadow=False)
        ui_style.draw_button(c, self.btn_play, "", self.font_btn, 3,
                             self.btn_play.collidepoint(mouse), shadow=False)
        # ikonka pauzy / prehrávania + text
        b = self.btn_play
        ix, iy = b.x + 34, b.centery
        col = ui_style.GOLD
        if self.playing:
            c.rect(col, (ix - 8, iy - 9, 6, 18))
            c.rect(col, (ix + 2, iy - 9, 6, 18))
            label = "Pozastaviť"
        else:
            c.polygon(col, [(ix - 7, iy - 10), (ix + 10, iy), (ix - 7, iy + 10)])
            label = "Prehrať"
        s = self.font_btn.render(label, True, ui_style.TEXT)
        c.blit(s, s.get_rect(midleft=(ix + 26, iy)))
        for i, d in enumerate(self.dots):
            active = i == self.scene
            c.circle(ui_style.GOLD if active else (90, 70, 44), d.center, 7 if active else 5)

    # --- karty --------------------------------------------------------------

    def _card(self, name: str, center, scale: float = 1.0, alpha: float = 1.0,
              outline=None, mark: str | None = None, shadow: bool = True):
        c = self.canvas
        w = round(self.cw * scale)
        h = round(w / CARD_RATIO)
        try:
            img = c.card(f"{name}.png", lsize=(w, h))
        except (FileNotFoundError, pygame.error):
            return
        rect = img.get_rect(center=(round(center[0]), round(center[1])))
        a = int(255 * max(0.0, min(1.0, alpha)))
        if a <= 0:
            return
        if shadow and a > 200:
            c.overlay(rect.move(4, 6), (0, 0, 0, 100), border_radius=8)
        if a < 255:
            img = img.copy()
            img.set_alpha(a)
        c.blit(img, rect)
        if outline and a > 40:
            col = outline
            c.rect(col, rect.inflate(6, 6), width=4, border_radius=10)
        if mark and a > 40:
            ic = self._icon(mark, round(40 * self.k))
            if ic:
                c.blit(ic, ic.get_rect(center=(rect.right - 4, rect.top + 4)))
        return rect

    def _icon(self, name: str, size: int):
        path = os.path.join("assets", "graphics", f"{name}.png")
        try:
            return self.canvas.image(path, (size, size))
        except (FileNotFoundError, pygame.error):
            return None

    def _hand(self, names, fade, moved=None, moved_k=0.0, dimmed=(), outlines=None,
              marks=None):
        """Ruka hráča vpravo dole; zahraná karta ostane ako priesvitný tieň."""
        for i, n in enumerate(names):
            pos = self.hand_pos(i, len(names))
            if n == moved:
                self._card(n, pos, 0.77, alpha=fade * (1 - 0.75 * moved_k), shadow=False)
            else:
                a = fade * (0.45 if n in dimmed else 1.0)
                self._card(n, pos, 0.77, alpha=a,
                           outline=(outlines or {}).get(n),
                           mark=(marks or {}).get(n))

    # --- scény (t = čas v scéne, fade = priehľadnosť obsahu) ---------------

    def _scene1(self, t, fade):
        k = _ease((t - 1.0) / 2.0)
        pos = _arc(self.seat[1], self.spot[1], k)
        self._card("leaf-nine", pos, alpha=fade * min(1.0, 0.3 + k),
                   outline=ui_style.GOLD if t >= 3.0 else None)
        if t >= 3.0:
            a = _ease((t - 3.0) / 0.6) * fade
            c = self.canvas
            cx, cy = self.center
            r = round(38 * self.k)
            c.circle((20, 13, 8), (cx, cy), r)
            c.circle(ui_style.GOLD, (cx, cy), r, width=3)
            path = os.path.join("assets", "suit-icons", "leaf-icon@large.png")
            try:
                ic = c.image(path, (round(r * 1.05), round(r * 1.25))).copy()
                ic.set_alpha(int(255 * a))
                c.blit(ic, ic.get_rect(center=(cx, cy)))
            except (FileNotFoundError, pygame.error):
                pass

    def _respond(self, t, fade, lead, hand, play, dimmed=(), outlines=None,
                 marks=None, result_mark="ok"):
        self._card(lead[1], self.spot[lead[0]], alpha=fade)
        k = _ease((t - 1.0) / 2.0)
        idx = hand.index(play)
        start = self.hand_pos(idx, len(hand))
        self._hand(hand, fade, moved=play, moved_k=k, dimmed=dimmed,
                   outlines=outlines if t >= 0.6 else None,
                   marks=marks if t >= 0.6 else None)
        pos = _arc(start, self.spot[0], k, bend=0.15)
        scale = 0.77 + 0.23 * k
        done = t >= 3.0
        self._card(play, pos, scale, alpha=fade,
                   outline=GREEN if (t >= 0.6) else None,
                   mark=result_mark if done else None)

    def _scene2(self, t, fade):
        self._respond(t, fade, S2_LEAD, S2_HAND, S2_PLAY,
                      dimmed=tuple(n for n in S2_HAND if n != S2_PLAY))

    def _scene3(self, t, fade):
        self._respond(t, fade, S3_LEAD, S3_HAND, S3_PLAY,
                      outlines={n: GREEN for n in S3_HAND})

    def _scene4(self, t, fade):
        for i, (idx, name) in enumerate(S4_TRICK):
            k = _ease((t - 1.0 - i * 0.45) / 0.5)
            if k <= 0:
                continue
            pos = _arc(self.seat[idx], self.spot[idx], k)
            res = t >= 3.0
            off_suit = name.split("-")[0] != S4_TRICK[0][1].split("-")[0]
            outline = ui_style.GOLD if (res and idx == S4_WINNER) else None
            mark = ("circlex" if off_suit else "ok" if idx == S4_WINNER else None) if res else None
            self._card(name, pos, alpha=fade * min(1.0, 0.3 + k), outline=outline, mark=mark)

    def _scene5(self, t, fade):
        # 0–1 s štich leží, 1–2 s karty odletia k víťazovi, 2–3 s víťaz vynesie
        pile = (self.label[S4_WINNER][0] + round(110 * self.k),
                self.label[S4_WINNER][1] + round(40 * self.k))
        k = _ease((t - 1.0) / 1.0)
        for i, (idx, name) in enumerate(S4_TRICK):
            pos = _lerp(self.spot[idx], (pile[0] + i * 5, pile[1] + i * 3), k)
            self._card(name, pos, 1.0 - 0.35 * k, alpha=fade,
                       outline=ui_style.GOLD if (idx == S4_WINNER and k < 0.05) else None,
                       shadow=k < 0.95)
        k2 = _ease((t - 2.0) / 1.0)
        if k2 > 0:
            pos = _arc(self.seat[S4_WINNER], self.spot[S4_WINNER], k2)
            self._card(S5_NEXT, pos, alpha=fade * min(1.0, 0.3 + k2),
                       outline=ui_style.GOLD if t >= 3.0 else None)

    def _scene6(self, t, fade):
        k = _ease((t - 1.0) / 2.0)
        idx = S6_HAND.index(S6_PLAY)
        show_marks = t >= 0.6
        self._hand(S6_HAND, fade, moved=S6_PLAY, moved_k=k,
                   outlines={S6_FORBIDDEN: RED} if show_marks else None,
                   marks={S6_FORBIDDEN: "circlex"} if show_marks else None)
        pos = _arc(self.hand_pos(idx, len(S6_HAND)), self.spot[0], k, bend=0.15)
        self._card(S6_PLAY, pos, 0.77 + 0.23 * k, alpha=fade,
                   outline=GREEN if t >= 3.0 else None,
                   mark="ok" if t >= 3.0 else None)


def _wrap(text: str, font, width: float) -> list[str]:
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
