# gui/tip_panel.py
#
# Panel s tipom od AI — ľavý dolný roh. Tento priestor je voľný pri
# akomkoľvek rozlíšení: ruka Počítača 3 je vľavo hore (končí nad ním) a
# ruka hráča začína až napravo od neho (pozri hand_configs v gui/layout.py).
#
# Vizuál zámerne kopíruje panel KOLO (gui/round_status.py) — tmavé
# priehľadné pozadie, zlatý rám, zlatý nadpis — aby pôsobili ako jedna
# rodina prvkov.
#
# Obsah: obrázok odporúčanej karty (small) vľavo, dôvod od AI vpravo.
# Alternatívy Tip už nesie (Tip.alternatives), ale zatiaľ sa zámerne
# nevykresľujú — pridanie bude zmena výlučne v tomto súbore.

import pygame

from gui import layout, ui_style
from config import (
    CARD_SIZE_SMALL,
)


class TipPanel:
    def __init__(self, canvas):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.font_title = self.canvas.font(24)
        self.font_head = self.canvas.font(26)
        self.font_body = self.canvas.font(20)

        # Vľavo dole, ukotvený k spodnému okraju (gui/layout.py)
        self.x, self.y, self.w, self.h = layout.game().tip_panel_rect()


    # ------------------------------------------------------------------

    def draw(self, tip, x_offset: int = 0):
        """
        Vykreslí tip. `x_offset` posunie panel doprava — používa sa, keď
        je vysunutý Chujogram (ten zaberá ľavý pás obrazovky), aby ho
        panel neprekrýval.

        Panel je ukotvený spodnou hranou (ľavý dolný roh) a rastie nahor
        podľa obsahu — krátky tip nezaberá zbytočné miesto a tip o
        vysvietení s dvomi horníkmi sa zmestí celý.
        """
        if tip is None or tip.is_empty:
            return

        x = self.x + x_offset
        cards = [c for c in (tip.cards or []) if c is not None]

        # Pri jednej karte je text vedľa nej, pri viacerých pod nimi
        # (vedľa dvoch kariet by ostal na text príliš úzky pruh) — a
        # karty vtedy zmenšíme, nech na text ostane dosť výšky.
        side_by_side = len(cards) <= 1
        if side_by_side:
            card_w, card_h = CARD_SIZE_SMALL
        else:
            card_w = int(CARD_SIZE_SMALL[0] * 0.75)
            card_h = int(CARD_SIZE_SMALL[1] * 0.75)

        images = [
            img for img in (self._card_image(c, (card_w, card_h)) for c in cards)
            if img
        ]

        if side_by_side and images:
            text_x_rel = 14 + card_w + 12
        else:
            text_x_rel = 14
        text_w = max(60, self.w - 12 - text_x_rel)

        head_lines = self._wrap(tip.headline, self.font_head, text_w) \
            if tip.headline else []
        body_lines = self._wrap(tip.detail, self.font_body, text_w) \
            if tip.detail else []

        text_h = len(head_lines) * 28 + (4 if head_lines and body_lines else 0) \
            + len(body_lines) * 22
        if side_by_side:
            content_h = max(card_h if images else 0, text_h)
        else:
            content_h = (card_h + 10 if images else 0) + text_h

        h = min(self.h, 52 + content_h + 12)
        # Spodná hrana ostáva na mieste, panel rastie nahor.
        y = self.y + self.h - h

        self._draw_bg(x, y, h)

        title = self.font_title.render("TIP", True, ui_style.GOLD)
        self.canvas.blit(title, (x + 14, y + 10))
        self.canvas.line((70, 54, 34),
            (x + 10, y + 40), (x + self.w - 10, y + 40), width=1
        )

        cy = y + 52
        for i, img in enumerate(images):
            self.canvas.blit(img, (x + 14 + i * (card_w + 8), cy))

        ty = cy if side_by_side else cy + (card_h + 10 if images else 0)
        text_x = x + text_x_rel
        max_y = y + h - 8

        for line in head_lines:
            if ty + 28 > max_y:
                break
            self.canvas.blit(
                self.font_head.render(line, True, ui_style.GOLD), (text_x, ty)
            )
            ty += 28
        if head_lines and body_lines:
            ty += 4
        for line in body_lines:
            if ty + 22 > max_y:
                break
            self.canvas.blit(
                self.font_body.render(line, True, ui_style.TEXT), (text_x, ty)
            )
            ty += 22

    # ------------------------------------------------------------------

    def _draw_bg(self, x: int, y: int, h: int):
        # Spoločný štýl panelov (gui/ui_style.py, rework 2026-10-28)
        ui_style.draw_panel(self.canvas, (x, y, self.w, h))

    def _card_image(self, card, size: tuple[int, int] | None = None):
        """Karta v logickej veľkosti — Canvas vyberie najmenší dostatočne
        veľký asset (pri 4K medium/large namiesto zväčšenej small)."""
        size = size or CARD_SIZE_SMALL
        try:
            return self.canvas.card(f"{card.suit}-{card.rank}.png", lsize=size)
        except (FileNotFoundError, pygame.error):
            return None

    @staticmethod
    def _wrap(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split(" ")
        lines, current = [], ""
        for word in words:
            test = f"{current} {word}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
