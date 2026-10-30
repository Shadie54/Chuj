# gui/round_status.py

import pygame
import os
from gui import layout, ui_style
from game.round_points import actual_round_points
from config import (
    COLOR_GREEN,
    NO_PENALTY_STREAK, SUIT_ICONS_PATH
)


# Farby v štýle gui/ui_style.py (grafický rework 2026-10-28)
DIVIDER = (70, 54, 34)
PENALTY_COLOR = (232, 112, 84)
EMPTY_BULLET = (98, 76, 46)

# Rozloženie riadku (logické px od pravého okraja panela, panel je 350 široký)
SLASH_X = 60           # lomka "reálne / zobraté" (od pravého okraja panela)
NUM_ZONE = 128         # šírka pásma s číslami (od pravého okraja panela)
ROW_CONTENT_H = 49     # meno + guličky
BULLET_DY = 39         # stred guličiek pod vrchom riadku (od mena ~5 px)


class RoundStatus:
    def __init__(self, canvas):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.font_small = self.canvas.font(24)  # bolo 20
        self.font_medium = self.canvas.font(30)  # bolo 26
        self.font_large = self.canvas.font(38)  # bolo 32
        self.font_num = self.canvas.font(30)     # čísla bodov
        self._scores_before = None

        # Rozmery
        # Vpravo dole, ukotvený k spodnému okraju (gui/layout.py)
        self.x, self.y, self.w, self.h = layout.game().round_status_rect()

        # Gulička rozmery
        self.bullet_r = 8
        self.bullet_spacing = 20

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, players: list, current_round=None, scores_before=None):
        """Nakreslí panel so stavom kola.

        scores_before — skóre hráčov PRED týmto kolom (pravidlo 90+). Počas
        kola sa berie z players (total_score sa mení až pri uzavretí),
        po uzavretí kola ho musí dodať volajúci (z histórie skóre)."""
        self._scores_before = scores_before
        self._draw_bg()

        round_number = current_round.round_number if current_round else None
        deal_seed = current_round.deal_seed if current_round else None
        self._draw_title(round_number, deal_seed)

        self._draw_players(players, current_round)

    def _draw_bg(self):
        """Pozadie panelu — spoločný štýl (gui/ui_style.py, rework 2026-10-28)."""
        ui_style.draw_panel(self.canvas, (self.x, self.y, self.w, self.h))

    def _draw_title(self, round_number, deal_seed):
        if round_number is not None:
            round_text = f"KOLO {round_number}"
        else:
            round_text = "KOLO"

        title = self.font_medium.render(round_text, True, ui_style.GOLD)
        title_rect = title.get_rect(
            left=self.x + 30,  # bolo centerx
            top=self.y + 8
        )
        self.canvas.blit(title, title_rect)

        if deal_seed is not None:
            # Len pre zobrazenie — oddeľovač tisícok medzerou (napr. 27 856 498),
            # samotná hodnota deal_seed (v tester_main.py --seed X a pod.) sa nemení.
            seed_text = f"{deal_seed:,}".replace(",", " ")
            seed = self.font_small.render(f" ({seed_text})", True, ui_style.TEXT_DIM)  # pridaj medzeru
            seed_rect = seed.get_rect(
                right=self.x + self.w - 8,
                centery=title_rect.centery  # rovnaká výška ako KOLO
            )
            self.canvas.blit(seed, seed_rect)

        self.canvas.line(DIVIDER,
                         (self.x + 10, self.y + 43),
                         (self.x + self.w - 10, self.y + 43), width=1)

    def _draw_players(self, players: list, current_round=None):
        """Nakreslí riadok pre každého hráča."""
        # Riadky rovnomerne rozložené od čiary pod nadpisom po spodok panela
        # (riadok = meno + guličky, ~43 px; 14 px okraj hore aj dole).
        row_content_h = ROW_CONTENT_H
        y_start = self.y + 43 + 14
        last_top = self.y + self.h - 14 - row_content_h
        row_h = (last_top - y_start) / max(1, len(players) - 1)

        for i, player in enumerate(players):
            y = round(y_start + i * row_h)

            # Vodorovný oddeľovač medzi hráčmi — v strede medzery medzi
            # spodkom guličiek a menom ďalšieho hráča
            if i < len(players) - 1:
                sep_y = round(y + row_content_h + (row_h - row_content_h) / 2)
                self.canvas.line(DIVIDER, (self.x + 10, sep_y),
                                 (self.x + self.w - 10, sep_y), width=1)

            # Zvýraznenie ak je na ťahu
            is_current = (
                current_round and
                current_round.phase == "tricks" and
                current_round.get_current_player_index() == i
            )
            name_color = ui_style.BTN_TEXT_HOVER if is_current else ui_style.TEXT

            # Meno
            name_surf = self.font_small.render(
                player.name[:10], True, name_color
            )
            self.canvas.blit(name_surf, (self.x + 10, y))

            streak_end_x = self.x + 10 + NO_PENALTY_STREAK * self.bullet_spacing + self.bullet_r
            icon_x = max(self.x + 10 + name_surf.get_width() + 6, streak_end_x + 10)

            # Skutočné a zobraté body (stĺpce vpravo)
            finished = bool(current_round and current_round.phase == "done")
            real, taken = self._row_points(player, i, current_round, finished,
                                           players)
            self._draw_points(y, real, taken)

            # Ikonky horníkov a záväzku — zmenšia sa, ak by zasiahli do
            # stĺpca s číslami (najhorší prípad: dlhé meno + 2 horníci + záväzok)
            icons = []
            if current_round:
                for suit in ("leaf", "acorn"):
                    if current_round.illuminated_by.get(suit) == i:
                        icons.append(("suit", suit))
                if current_round.declaration_player == i:
                    icons.append(("decl", current_round.declaration_type))
            sizes = {"suit": 28, "decl": 38}
            need = sum(sizes[k] + 4 for k, _ in icons)
            avail = (self.x + self.w - NUM_ZONE - 4) - icon_x
            k = 1.0 if need <= avail or need == 0 else max(0.6, avail / need)
            for kind, key in icons:
                size = max(16, round(sizes[kind] * k))
                icon = self._icon(kind, key, size)
                if icon:
                    self.canvas.blit(icon, (icon_x, y + (ROW_CONTENT_H - size) // 2 - 2))
                    icon_x += size + 4

            # Zelené guličky — séria bez trestných bodov
            streak = player.no_penalty_streak
            self._draw_streak(x=self.x + 10, y=y + BULLET_DY, streak=streak)

    def _icon(self, kind: str, key: str, size: int):
        """Ikonka horníka / záväzku v danej veľkosti (cache v canvase)."""
        try:
            if kind == "suit":
                path = os.path.join(SUIT_ICONS_PATH, f"{key}-icon@small.png")
            else:
                path = os.path.join("assets", "graphics", f"{key}.png")
            return self.canvas.image(path, (size, size))
        except (FileNotFoundError, pygame.error):
            return None

    def _row_points(self, player, index, current_round, finished, players):
        """(reálne, zobraté) body riadku; None = nezobrazovať.
        Kolo so záväzkom: počas hry nič, po uzavretí výsledok záväzku."""
        if current_round is None:
            return None, None
        if self._scores_before is not None and finished:
            before = self._scores_before[index]
        else:
            before = player.total_score
        real = actual_round_points(current_round, player, index, before,
                                   finished=finished)
        taken = None if current_round.declaration_type is not None \
            else player.round_points
        return real, taken

    def _draw_points(self, y: int, real, taken):
        """Čísla "reálne / zobraté": reálne (červené > 0, zelené < 0, tlmené 0),
        lomka a zobraté celkovo (biele) — koľko bodov z koľkých. V kole so
        záväzkom je len výsledok (bez lomky)."""
        c = self.canvas
        cy = y + 22
        slash_x = self.x + self.w - SLASH_X
        if real is None:
            return
        if real > 0:
            text, color = str(real), PENALTY_COLOR
        elif real < 0:
            text, color = "\u2212" + str(-real), COLOR_GREEN
        else:
            text, color = "0", ui_style.TEXT_DIM
        surf = self.font_num.render(text, True, color)
        if taken is None:
            # záväzok: výsledok na mieste reálnych bodov, bez lomky
            c.blit(surf, surf.get_rect(midright=(slash_x - 8, cy)))
            return
        c.blit(surf, surf.get_rect(midright=(slash_x - 9, cy)))
        sl = self.font_num.render("/", True, ui_style.TEXT_DIM)
        c.blit(sl, sl.get_rect(center=(slash_x, cy)))
        tk = self.font_num.render(str(taken), True,
                                  ui_style.TEXT if taken else ui_style.TEXT_DIM)
        c.blit(tk, tk.get_rect(midleft=(slash_x + 9, cy)))

    def _draw_streak(self, x: int, y: int, streak: int):
        """Nakreslí 5 guličiek — zelené pre sériu, sivé prázdne."""
        max_show = NO_PENALTY_STREAK
        for i in range(max_show):
            cx = x + i * self.bullet_spacing + self.bullet_r
            if i < streak:
                # Plná zelená
                self.canvas.circle(COLOR_GREEN, (cx, y), self.bullet_r)
                self.canvas.circle(ui_style.TEXT, (cx, y), self.bullet_r, width=1)
            else:
                # Prázdna — tlmená zlatohnedá
                self.canvas.circle(EMPTY_BULLET, (cx, y), self.bullet_r, width=1)

        # Bonus text ak dosiahol max
        if streak >= max_show:
            bonus_surf = self.font_small.render("-10b!", True, COLOR_GREEN)
            self.canvas.blit(bonus_surf, (x + max_show * self.bullet_spacing + 5, y - 6))

    def __repr__(self) -> str:
        return "RoundStatus()"