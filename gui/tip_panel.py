# gui/tip_panel.py
#
# Panel s tipom od AI — ľavý dolný roh. Tento priestor je voľný pri
# akomkoľvek rozlíšení: ruka Počítača 3 je vľavo hore (končí nad ním) a
# ruka hráča začína až napravo od neho (pozri HAND_CONFIGS v config.py).
#
# Vizuál zámerne kopíruje panel KOLO (gui/round_status.py) — tmavé
# priehľadné pozadie, zlatý rám, zlatý nadpis — aby pôsobili ako jedna
# rodina prvkov.
#
# Obsah: obrázok odporúčanej karty (small) vľavo, dôvod od AI vpravo.
# Alternatívy Tip už nesie (Tip.alternatives), ale zatiaľ sa zámerne
# nevykresľujú — pridanie bude zmena výlučne v tomto súbore.

import pygame

from config import (
    COLOR_GOLD, COLOR_WHITE, COLOR_GRAY,
    CARD_SIZE_SMALL, CARDS_SMALL_PATH,
    TIP_PANEL_X, TIP_PANEL_Y, TIP_PANEL_W, TIP_PANEL_H,
    get_font,
)


class TipPanel:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_title = get_font(24)
        self.font_head = get_font(26)
        self.font_body = get_font(20)

        self.x = TIP_PANEL_X
        self.y = TIP_PANEL_Y
        self.w = TIP_PANEL_W
        self.h = TIP_PANEL_H

        self._card_cache: dict[str, pygame.Surface] = {}

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

        title = self.font_title.render("TIP", True, COLOR_GOLD)
        self.screen.blit(title, (x + 14, y + 10))
        pygame.draw.line(
            self.screen, COLOR_GOLD,
            (x + 10, y + 40), (x + self.w - 10, y + 40), width=1
        )

        cy = y + 52
        for i, img in enumerate(images):
            self.screen.blit(img, (x + 14 + i * (card_w + 8), cy))

        ty = cy if side_by_side else cy + (card_h + 10 if images else 0)
        text_x = x + text_x_rel
        max_y = y + h - 8

        for line in head_lines:
            if ty + 28 > max_y:
                break
            self.screen.blit(
                self.font_head.render(line, True, COLOR_GOLD), (text_x, ty)
            )
            ty += 28
        if head_lines and body_lines:
            ty += 4
        for line in body_lines:
            if ty + 22 > max_y:
                break
            self.screen.blit(
                self.font_body.render(line, True, COLOR_WHITE), (text_x, ty)
            )
            ty += 22

    # ------------------------------------------------------------------

    def _draw_bg(self, x: int, y: int, h: int):
        overlay = pygame.Surface((self.w, h), pygame.SRCALPHA)
        overlay.fill((20, 12, 5, 210))
        self.screen.blit(overlay, (x, y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD, (x, y, self.w, h),
            width=2, border_radius=10
        )

    def _card_image(self, card, size: tuple[int, int] | None = None):
        size = size or CARD_SIZE_SMALL
        name = f"{card.suit}-{card.rank}"
        key = f"{name}@{size[0]}x{size[1]}"
        if key not in self._card_cache:
            try:
                img = pygame.image.load(
                    f"{CARDS_SMALL_PATH}/{name}.png"
                ).convert_alpha()
                self._card_cache[key] = pygame.transform.scale(img, size)
            except (FileNotFoundError, pygame.error):
                self._card_cache[key] = None
        return self._card_cache[key]

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
