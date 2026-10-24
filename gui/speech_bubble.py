# gui/speech_bubble.py

import pygame
import os
from gui import layout
from config import (
    COLOR_WHITE, COLOR_GOLD, COLOR_YELLOW, COLOR_GREEN, COLOR_RED,
    FONT_SIZE_MEDIUM,
    SUIT_ICONS_PATH,
)


class SpeechBubble:
    def __init__(self, canvas):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.font_large = self.canvas.font(FONT_SIZE_MEDIUM + 4)
        self.font_medium = self.canvas.font(FONT_SIZE_MEDIUM)

        self._icon_cache: dict[str, pygame.Surface] = {}

        # Aktívne bubliny [{player_index, text, suit, timer, color}]
        self.bubbles: list[dict] = []

        # Zastavenie časovačov (pozri update()). Zapína to naskriptovaná
        # lekcia tutoriálu, kým čaká na hráča; ostrá hra to nikdy nemení.
        self.frozen: bool = False
        self._last_update: int = pygame.time.get_ticks()

        # Pozície bublín pre každého hráča.
        #
        # Hráč (0) a PC2 (2) sedia na tej istej zvislej osi ako karty
        # štichu v strede stola (layout.trick_positions) — pri pôvodných
        # hodnotách (820/380) preto bublina po štichu ("+N") zasahovala
        # priamo do práve zahranej karty (u PC2 dokonca celá bublina
        # ležala vnútri karty). Nové hodnoty (945/245) sú spočítané tak,
        # aby sa zmestili do medzery medzi kartou a menovkou hráča
        # (gui/phase_renderer.py::draw_player_labels) aj pre najvyšší typ
        # bubliny (TROMF s ikonkou, ~132px vrátane chvosta) — overené
        # vykreslením oboch prípadov na 1920×1080.
        # Od reworku rozlíšení (krok 5) z gui/layout.py — ukotvené ako ruky
        # (pri 1080p presne 945 / (W−520, 380) / 245 / (520, 380)).
        self.bubble_positions = dict(layout.game().bubble_positions)

        # Bodová bublina po štichu (show_round_result) pre hráča (0) a PC2
        # (2) má VLASTNÚ pozíciu, inú než bubble_positions vyššie. Dôvod:
        # hráč (0) aj PC2 (2) majú ruku kariet nakreslenú vodorovne presne
        # na TABLE_CENTER_X (layout.hand_configs) — bublina uprostred (945/245)
        # tak pri plnej ruke (8 kariet) zasahovala priamo do vlastných
        # kariet hráča (overené vykreslením). PC1 (1) a PC3 (3) majú ruku
        # zvislú mimo tejto osi, tam k prekryvu nedochádza — pre nich
        # bodová bublina ostáva na bubble_positions.
        # Hráč: nad jeho prvou kartou (ľavý koniec ruky) — úplne vľavo
        # (pred rukou) by zasahovala do panelu TIP (gui/tip_panel.py,
        # x=20..380 — prvá karta začína až na x=400). O 50px
        # vyššie než samotný vrch karty (hand_configs[0]["y"]), nech nad
        # ňou ostane viac vzduchu.
        # PC2: vpravo od jeho (rovnako širokej) ruky hore, tesne pri
        # kartách — medzera 90px necháva miesto pre chvost (max. šírka
        # bubliny "+130"/48px polovica + 24px chvost = 72px) aj s
        # rezervou, bez dotyku poslednej karty.
        # Výpočet (prvá karta ruky hráča, 50 px nad ňou; vpravo od ruky
        # PC2 + 90 px) je v gui/layout.py::build_game_layout.
        self.round_result_positions = dict(layout.game().round_result_positions)

    # ------------------------------------------------------------------
    # Pridanie bubliny
    # ------------------------------------------------------------------

    def show_trump(self, player_index: int, suit: str,
                   is_new: bool = False, duration_ms: int = 4000):
        """Zobrazí tromfovú bublinu."""
        text = "NOVÝ TROMF!" if is_new else "TROMF!"
        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=suit,
            duration_ms=duration_ms,
            color=COLOR_GOLD
        )

    def show_bid(self, player_index: int, text: str,
                 duration_ms: int = 5000):
        """Zobrazí biddingová bublinu (záväzok, vysvietenie, risk)."""
        if text is None:
            display_text = "Ja nič"
            color = (150, 150, 150)
        else:
            display_text = text
            color = COLOR_YELLOW

        # Hráč (0): rovnaká "bezpečná" pozícia ako bodová bublina po
        # štichu (show_round_result) — nad prvou kartou jeho ruky, nie v
        # strede nad celou rukou (bubble_positions[0]). Dlhší text (napr.
        # "Svietim žaluďového!") pri strednej pozícii zasahoval priamo do
        # kariet (nahlásené 2026-10-15).
        position = (
            self.round_result_positions.get(player_index)
            if player_index == 0 else None
        )

        self._add_bubble(
            player_index=player_index,
            text=display_text,
            suit=None,
            duration_ms=duration_ms,
            color=color,
            position=position,
        )

    def show_instruction(self, player_index: int, text: str):
        """
        Zobrazí inštrukciu ako bublinu hráča.
        Ostáva zobrazená kým ju manuálne neodstránime.
        """
        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=None,
            duration_ms=99999999,  # "nekonečno" — zmizne manuálne
            color=COLOR_WHITE
        )

    def hide_instruction(self, player_index: int):
        """Odstráni inštrukčnú bublinu."""
        self.bubbles = [
            b for b in self.bubbles
            if b["player_index"] != player_index
        ]

    # Smer chvostu podľa hráča v predvolenom prípade (pozri _draw_tail).
    _DEFAULT_TAIL_DIRECTION = {0: "down", 1: "right", 2: "up", 3: "left"}

    def _add_bubble(self, player_index: int, text: str,
                    suit: str | None, duration_ms: int, color: tuple,
                    position: tuple | None = None,
                    tail_direction: str | None = None):
        """Pridá bublinu do zoznamu.

        position — voliteľné prebitie štandardnej pozície
        (self.bubble_positions[player_index]); používa show_round_result()
        pre hráča (0) a PC2 (2), pozri self.round_result_positions.

        tail_direction — voliteľné prebitie smeru chvostu (inak podľa
        player_index, pozri _DEFAULT_TAIL_DIRECTION); používa
        show_round_result() pre PC2 (2), ktorého bodová bublina je vpravo
        od jeho ruky, takže chvost smeruje doľava (späť k ruke), nie hore
        ako pri jeho tromfovej/biddingovej bubline.
        """
        # Odstráň existujúcu bublinu toho istého hráča
        self.bubbles = [
            b for b in self.bubbles
            if b["player_index"] != player_index
        ]
        self.bubbles.append({
            "player_index": player_index,
            "text": text,
            "suit": suit,
            "timer": pygame.time.get_ticks() + duration_ms,
            "color": color,
            "position": position or self.bubble_positions[player_index],
            "tail_direction": tail_direction or self._DEFAULT_TAIL_DIRECTION[player_index]
        })

    # ------------------------------------------------------------------
    # Aktualizácia
    # ------------------------------------------------------------------

    def update(self):
        """Odstráni expirované bubliny.

        Keď je self.frozen zapnuté, časovače bublín stoja — o uplynulý
        čas sa im posunie koniec platnosti. Používa to naskriptovaná
        lekcia tutoriálu: tá beží na kliky, nie na čas, takže bublina,
        ktorá má hráčovi niečo povedať, nesmie zmiznúť, kým si číta
        výklad. V ostrej hre frozen nikdy nie je zapnuté a bubliny miznú
        po svojom čase presne ako predtým.
        """
        now = pygame.time.get_ticks()
        elapsed = now - self._last_update
        self._last_update = now
        if self.frozen and elapsed > 0:
            for bubble in self.bubbles:
                bubble["timer"] += elapsed
        self.bubbles = [
            b for b in self.bubbles
            if now < b["timer"]
        ]

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self):
        """Nakreslí všetky aktívne bubliny."""
        self.update()
        for bubble in self.bubbles:
            self._draw_bubble(bubble)

    def _draw_bubble(self, bubble: dict):
        """Nakreslí jednu bublinu."""
        player_index = bubble["player_index"]
        cx, cy = bubble["position"]

        text_surf = self.font_large.render(bubble["text"], True, bubble["color"])
        text_w = text_surf.get_width()
        text_h = text_surf.get_height()

        # Rozmery bubliny
        icon_size = 40 if bubble["suit"] else 0
        padding = 16
        bubble_w = max(text_w, icon_size) + padding * 2
        bubble_h = text_h + icon_size + padding * 2 + (8 if bubble["suit"] else 0)

        bx = cx - bubble_w // 2
        by = cy - bubble_h

        # Pozadie bubliny
        self.canvas.overlay(pygame.Rect((bx, by), (bubble_w, bubble_h)), (20, 12, 5, 220))

        # Okraj
        self.canvas.rect(bubble["color"],
            (bx, by, bubble_w, bubble_h),
            width=2, border_radius=12
        )

        # Chvost bubliny (trojuholník)
        self._draw_tail(cx, by + bubble_h, by, bubble_w, bubble_h,
                        bubble["tail_direction"], bubble["color"])

        # Text
        text_rect = text_surf.get_rect(
            centerx=cx,
            top=by + padding
        )
        self.canvas.blit(text_surf, text_rect)

        # Ikonka farby (ak je tromf)
        if bubble["suit"]:
            icon = self._load_icon(bubble["suit"], icon_size)
            if icon:
                icon_rect = icon.get_rect(
                    centerx=cx,
                    top=by + padding + text_h + 8
                )
                self.canvas.blit(icon, icon_rect)

    def _draw_tail(self, cx: int, base_y: int, by: int, bubble_w: int, bubble_h: int,
                   direction: str, color: tuple):
        tail_size = 12
        bx = cx - bubble_w // 2

        if direction == "down":
            # Chvost dole (zo spodku bubliny) — predvolené pre hráča (0)
            points = [
                (cx - tail_size, base_y),
                (cx + tail_size, base_y),
                (cx, base_y + tail_size * 2)
            ]
        elif direction == "right":
            # Chvost doprava (z pravého okraja bubliny) — predvolené pre PC1
            mid_y = by + bubble_h // 2
            right_x = bx + bubble_w
            points = [
                (right_x, mid_y - tail_size),
                (right_x, mid_y + tail_size),
                (right_x + tail_size * 2, mid_y)
            ]
        elif direction == "up":
            # Chvost hore (z vrchného okraja bubliny) — predvolené pre PC2
            points = [
                (cx - tail_size, by),
                (cx + tail_size, by),
                (cx, by - tail_size * 2)
            ]
        else:
            # Chvost doľava (z ľavého okraja bubliny) — predvolené pre PC3;
            # aj bodová bublina PC2 (show_round_result), lebo tá je vpravo
            # od jeho ruky a chvost má smerovať späť k nej.
            mid_y = by + bubble_h // 2
            points = [
                (bx, mid_y - tail_size),
                (bx, mid_y + tail_size),
                (bx - tail_size * 2, mid_y)
            ]

        self.canvas.polygon(color, points)

    def _load_icon(self, suit: str, size: int) -> pygame.Surface | None:
        """Načíta ikonku farby."""
        key = f"{suit}-{size}"
        if key not in self._icon_cache:
            path = os.path.join(SUIT_ICONS_PATH, f"{suit}-icon@medium.png")
            try:
                self._icon_cache[key] = self.canvas.image(path, (size, size))
            except (FileNotFoundError, pygame.error):
                self._icon_cache[key] = None
        return self._icon_cache[key]

    def show_round_result(self, player_index: int, points: int,
                          is_bidder: bool, fulfilled: bool = True):
        """Zobrazí výsledok kola ako bublinu.

        is_bidder=False (po každom štichu, pozri
        gui/screen.py::_process_waiting_trick) vždy ukazuje ČERVENÚ farbu
        — v CHUJ-i sú body vždy trestné, nikdy nie je "+body" niečo
        dobré."""
        if is_bidder:
            if fulfilled:
                text = f"+{points}"
                color = COLOR_GREEN
            else:
                text = f"-{points}"
                color = COLOR_RED
        else:
            text = f"+{points}"
            color = COLOR_RED

        self._add_bubble(
            player_index=player_index,
            text=text,
            suit=None,
            duration_ms=3000,
            color=color,
            position=self.round_result_positions.get(player_index),
            tail_direction="left" if player_index == 2 else None
        )

    def __repr__(self) -> str:
        return f"SpeechBubble(active={len(self.bubbles)})"