# gui/last_trick_overlay.py
#
# Okno "Posledný štich" (tlačidlo v stĺpci vpravo dole). Grafický rework
# 2026-10-27 podľa návrhu C (minimalistický): tmavý panel v štýle menu
# (gui/ui_style.py), karty v poradí, v akom boli zahrané, šípky medzi
# nimi, víťazná karta zdvihnutá so zlatým rámom a žiarou, menovky pod
# kartami a dole riadok "Štich berie: … · N b".
#
# Rozmery: všetko je navrhnuté v "základnej" veľkosti (BASE_*) a násobí sa
# mierkou k. Tá je SCALE (kompaktné okno), no zmenší sa ešte viac, ak by
# sa okno nezmestilo nad stĺpec tlačidiel a panel KOLO vpravo dole
# (gui/layout.py) — okno ich tak neprekrýva pri žiadnej logickej výške.
#
# Celý obsah okna sa vykreslí raz do priehľadnej vrstvy veľkosti okna
# (žiara sa počíta pomaly) a každú snímku sa len blitne; navrch sa kreslí
# iba zvýraznenie krížika pod myšou. Vrstva sa prepočíta, keď pribudne
# štich alebo sa zmení veľkosť okna.

import os

import pygame

from gui import display, layout, ui_style
from config import SCREEN_WIDTH, CARD_SIZE_MEDIUM, SUIT_ICONS_PATH

SCALE = 0.82                   # kompaktné okno (≈ o 18 % menšie)
TOP_MARGIN = 40                # minimálny odstup okna od horného okraja
BOTTOM_GAP = 20                # odstup nad stĺpcom tlačidiel / panelom KOLO

# Základné rozmery (pri k = 1)
BASE_PAD_X = 67
CARD_GAP = 74                  # medzera medzi kartami (je v nej šípka)
TITLE_CY = 44                  # stred nadpisu od vrchu panela
TITLE_SIZE = 44
TITLE_LINE_GAP = 32
CARDS_TOP = 108                # vrch kariet od vrchu panela
WINNER_LIFT = 12               # o koľko je víťazná karta vyššie
NAME_GAP = 12                  # medzera karta → menovka
NAME_H = 38
NAME_SIZE = 24
FOOTER_GAP = 34                # menovka → stred pätičky
FOOTER_SIZE = 28
BOTTOM_PAD = 30
CLOSE_R = 24                   # polomer krížika vpravo hore
CLOSE_INSET = 40

PENALTY_COLOR = (232, 112, 84)


class LastTrickOverlay:
    def __init__(self, canvas, card_renderer):
        self.canvas = canvas
        self.card_renderer = card_renderer
        self._layer: pygame.Surface | None = None
        self._key = None
        self.close_hover = False

    # --- rozloženie -------------------------------------------------------

    @staticmethod
    def _base_size(n_cards: int = 4) -> tuple[int, int]:
        card_w, card_h = CARD_SIZE_MEDIUM
        w = 2 * BASE_PAD_X + n_cards * card_w + (n_cards - 1) * CARD_GAP
        h = (CARDS_TOP + card_h + NAME_GAP + NAME_H + FOOTER_GAP
             + FOOTER_SIZE // 2 + BOTTOM_PAD)
        return w, h

    def _geometry(self) -> tuple[float, pygame.Rect]:
        """Mierka k a obdĺžnik panela podľa voľného miesta: medzi horným
        okrajom a stĺpcom tlačidiel / panelom KOLO vpravo dole."""
        lay = layout.game()
        bottom = min(lay.column_rect(0).top, lay.round_status_rect().top) - BOTTOM_GAP
        avail_h = bottom - TOP_MARGIN
        base_w, base_h = self._base_size()
        k = min(SCALE, avail_h / base_h)
        w, h = round(base_w * k), round(base_h * k)
        top = TOP_MARGIN + (avail_h - h) // 2
        return k, pygame.Rect(SCREEN_WIDTH // 2 - w // 2, top, w, h)

    def panel_rect(self) -> pygame.Rect:
        return self._geometry()[1]

    def close_center(self) -> tuple[int, int]:
        k, p = self._geometry()
        return (round(p.right - CLOSE_INSET * k), round(p.top + CLOSE_INSET * k))

    def close_hit(self, pos) -> bool:
        k = self._geometry()[0]
        cx, cy = self.close_center()
        r = CLOSE_R * k + 6
        return (pos[0] - cx) ** 2 + (pos[1] - cy) ** 2 <= r * r

    def update_hover(self, pos):
        self.close_hover = self.close_hit(pos)

    # --- kreslenie --------------------------------------------------------

    def draw(self, trick, players):
        """`trick` = posledný dohraný štich, `players` = hráči hry."""
        c = self.canvas
        key = (id(trick), len(trick.played_cards), c.target.get_size(),
               display.logical_height())
        if key != self._key or self._layer is None:
            self._layer = self._render(trick, players)
            self._key = key
        c.target.blit(self._layer, (0, 0))
        self._draw_close(self.close_hover)

    def _render(self, trick, players) -> pygame.Surface:
        c = self.canvas
        size = c.target.get_size()
        layer = pygame.Surface(size, pygame.SRCALPHA)
        prev, c.target = c.target, layer
        try:
            layer.fill((0, 0, 0, 175))
            self._render_content(trick, players)
        finally:
            c.target = prev
        return layer

    def _render_content(self, trick, players):
        c = self.canvas
        k, panel = self._geometry()

        def s(v: float) -> int:
            return round(v * k)

        # Plne nepriehľadný podklad — hra pod oknom nesmie presvitať.
        c.overlay(panel, (17, 11, 7, 255), border_radius=ui_style.PANEL_RADIUS)
        ui_style.draw_panel(c, panel)

        # Nadpis s ozdobnou linkou
        ui_style.draw_screen_title(c, "POSLEDNÝ ŠTICH", c.font(s(TITLE_SIZE)),
                                   (panel.centerx, panel.top + s(TITLE_CY)),
                                   line_half_w=s(210), line_gap=s(TITLE_LINE_GAP))
        self._draw_close(False)

        played = trick.played_cards
        winner_index = trick.get_winner_index()
        card_w, card_h = s(CARD_SIZE_MEDIUM[0]), s(CARD_SIZE_MEDIUM[1])
        gap = s(CARD_GAP)
        n = len(played)
        total_w = n * card_w + (n - 1) * gap
        x0 = panel.centerx - total_w // 2
        y0 = panel.top + s(CARDS_TOP)
        name_font = c.font(s(NAME_SIZE))
        name_top = y0 + card_h + s(NAME_GAP)

        for i, (player_idx, card) in enumerate(played):
            x = x0 + i * (card_w + gap)
            is_winner = player_idx == winner_index
            y = y0 - s(WINNER_LIFT) if is_winner else y0

            if is_winner:
                glow = pygame.Rect(x - s(60), y - s(50), card_w + s(120),
                                   card_h + s(100))
                ui_style.blit_soft_ellipse(c, glow, (255, 186, 80), 120,
                                           additive=True)
            # tieň karty
            c.overlay((x + s(5), y + s(8), card_w, card_h), (0, 0, 0, 120),
                      border_radius=s(10))
            c.blit(c.card(card.image_name, lsize=(card_w, card_h)), (x, y))
            if is_winner:
                c.rect(ui_style.GOLD, (x - 2, y - 2, card_w + 4, card_h + 4),
                       width=3, border_radius=s(10))

            # šípka k ďalšej karte (poradie zahrania)
            if i < n - 1:
                ax = x + card_w + gap // 2
                ay = y0 + card_h // 2
                c.polygon(ui_style.GOLD_SOFT, [(ax - s(8), ay - s(12)),
                                               (ax + s(10), ay),
                                               (ax - s(8), ay + s(12))])

            # menovka pod kartou (víťaz na zlatej plakete)
            name = players[player_idx].name
            label_rect = pygame.Rect(0, 0, s(150), s(NAME_H))
            label_rect.midtop = (x + card_w // 2, name_top)
            if is_winner:
                ui_style.draw_button(c, label_rect, name, name_font, 1)
            else:
                surf = name_font.render(name, True, ui_style.TEXT)
                c.blit(surf, surf.get_rect(center=label_rect.center))

        self._draw_footer(trick, players, winner_index, panel,
                          name_top + s(NAME_H) + s(FOOTER_GAP), k)

    def _draw_footer(self, trick, players, winner_index, panel, cy, k):
        """Ikonka farby víťaznej karty + "Štich berie: meno · N b"."""
        c = self.canvas
        font = c.font(round(FOOTER_SIZE * k))
        win_card = next(card for p, card in trick.played_cards
                        if p == winner_index)
        # Trestné body štichu — s vysvietením rovnako ako pri bodovaní kola
        # (vysvietený horník platí dvojnásobne, nech ho vysvietil ktokoľvek).
        points = trick.total_points(
            any(p.illuminated_leaf for p in players),
            any(p.illuminated_acorn for p in players))
        parts = [
            font.render("Štich berie: ", True, ui_style.TEXT),
            font.render(players[winner_index].name, True, ui_style.GOLD),
            font.render(f"  ·  {points} b", True,
                        PENALTY_COLOR if points > 0 else ui_style.TEXT_DIM),
        ]
        icon = self._suit_icon(win_card.suit, round(30 * k))
        icon_w = icon.get_width() + round(12 * k) if icon else 0
        x = panel.centerx - (icon_w + sum(p.get_width() for p in parts)) // 2
        if icon:
            c.blit(icon, icon.get_rect(midleft=(x, cy)))
        x += icon_w
        for part in parts:
            c.blit(part, part.get_rect(midleft=(x, cy)))
            x += part.get_width()

    def _draw_close(self, hover: bool):
        c = self.canvas
        k = self._geometry()[0]
        cx, cy = self.close_center()
        r = round(CLOSE_R * k)
        c.circle((24, 16, 10), (cx, cy), r)
        c.circle(ui_style.BTN_BORDER_HOVER if hover else ui_style.GOLD_SOFT,
                 (cx, cy), r, width=2)
        color = ui_style.BTN_TEXT_HOVER if hover else ui_style.GOLD
        d = round(9 * k)
        c.line(color, (cx - d, cy - d), (cx + d, cy + d), width=3)
        c.line(color, (cx - d, cy + d), (cx + d, cy - d), width=3)

    def _suit_icon(self, suit: str, height: int):
        path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@medium.png")
        try:
            raw = pygame.image.load(path)
        except (FileNotFoundError, pygame.error):
            return None
        w = max(1, round(height * raw.get_width() / raw.get_height()))
        return self.canvas.image(path, (w, height))
