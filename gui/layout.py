# gui/layout.py
#
# Rozloženie hernej obrazovky ako funkcia logickej výšky L_h — rework
# rozlíšení, krok 5 (claude/11_RESOLUTION_REWORK_ANALYSIS.md §3.3d).
#
# Logická šírka je vždy 1920, výška L_h = 1080 (16:9) … 1200 (16:10).
# Prvky sú ukotvené ZVISLE:
#   hore   — ruka Počítača 2, menovka PC2, jeho bublina
#   stred  — stôl (štich), tlačidlá záväzku, ruky PC1/PC3 a ich menovky
#   dole   — ruka hráča, stĺpec tlačidiel, panely KOLO a TIP, správa,
#            menovka a bublina hráča
# Pri 16:10 sa tak extra výška (120 px) rozdelí: +60 px medzi ruku hráča
# a štich, +60 px medzi štich a ruku PC2.
#
# Pri L_h = 1080 dáva tento modul PRESNE tie isté čísla, aké boli predtým
# natvrdo v config.py / phase_renderer / speech_bubble / trick_animation
# (overené pixelovým porovnaním galérie). Pôvodné konštanty z config.py
# odstránil krok 8 — tento modul je jediný zdroj rozloženia hernej obrazovky.
#
# Rozloženie sa počíta pre AKTUÁLNU logickú výšku okna (gui/display.py),
# nie pre tú pri štarte — pripravené na zmenu rozlíšenia za behu (krok 7).

from dataclasses import dataclass, field

import pygame

from config import CARD_SIZE_MEDIUM

LOGICAL_W = 1920
CARD_W, CARD_H = CARD_SIZE_MEDIUM


@dataclass(frozen=True)
class GameLayout:
    l_h: int
    width: int = LOGICAL_W
    table_center: tuple[int, int] = (0, 0)
    hand_configs: dict = field(default_factory=dict)
    trick_positions: dict = field(default_factory=dict)
    trick_collect_targets: dict = field(default_factory=dict)
    button_y: int = 0
    label_positions: dict = field(default_factory=dict)
    bubble_positions: dict = field(default_factory=dict)
    round_result_positions: dict = field(default_factory=dict)
    message_center_y: int = 0
    deal_hint_y: int = 0
    lesson_max_right: int = 0
    lesson_max_bottom: int = 0

    # --- tlačidlá (pygame.Rect je meniteľný — vždy vraciame nový) ------

    def decl_all_rect(self) -> pygame.Rect:
        return pygame.Rect(self.table_center[0] - 420, self.button_y, 260, 50)

    def decl_none_rect(self) -> pygame.Rect:
        return pygame.Rect(self.table_center[0] - 140, self.button_y, 260, 50)

    def ok_rect(self) -> pygame.Rect:
        return pygame.Rect(self.table_center[0] + 140, self.button_y, 120, 50)

    def column_rect(self, slot: int) -> pygame.Rect:
        """Stĺpec tlačidiel vpravo dole, slot 0 = najvyššie (Tipy) …
        4 = najnižšie (Menu). Ukotvený k spodnému okraju."""
        return pygame.Rect(self.width - 600, self.l_h - 330 + slot * 60, 200, 50)

    def tip_panel_rect(self) -> pygame.Rect:
        return pygame.Rect(20, self.l_h - 270 - 20, 360, 270)

    def round_status_rect(self) -> pygame.Rect:
        return pygame.Rect(self.width - 370, self.l_h - 260 - 20, 350, 260)


# Poradie v stĺpci tlačidiel (zdola nahor: Menu, Pravidlá, Chujogram,
# Posledný štich, Tipy). Tlačidlo "Zoradiť" bolo odstránené 2026-09-26 —
# stĺpec sa vtedy posunul o miesto NIŽŠIE, aby Menu ostalo pri spodnom
# okraji a voľné miesto zostalo navrchu (slot 0 je preto Tipy).
COLUMN_SLOTS = {"tips": 0, "last_trick": 1, "chujogram": 2, "info": 3, "menu": 4}


def build_game_layout(l_h: int) -> GameLayout:
    W = LOGICAL_W
    tcx, tcy = W // 2, l_h // 2
    hand_bottom_y = l_h - 220            # 860 pri 1080 — ruka zámerne presahuje okraj

    hand_configs = {
        0: {"direction": "horizontal", "x": 400, "y": hand_bottom_y, "offset": 100},  # hráč — dole
        1: {"direction": "vertical", "x": 1600, "y": tcy - 390, "offset": 65},       # PC1 — vpravo
        2: {"direction": "horizontal", "x": 400, "y": -50, "offset": 100},           # PC2 — hore
        3: {"direction": "vertical", "x": 30, "y": tcy - 390, "offset": 65},         # PC3 — vľavo
    }
    trick_positions = {
        0: (tcx, tcy + 120),
        1: (tcx + 150, tcy),
        2: (tcx, tcy - 120),
        3: (tcx - 150, tcy),
    }
    # Kam letí zbieraný štich k víťazovi (gui/trick_animation.py).
    trick_collect_targets = {
        0: (W // 2, l_h - 150),          # 930 pri 1080
        1: (1620, tcy - 130),            # 410
        2: (W // 2, 20),
        3: (50, tcy - 130),
    }
    label_positions = {
        0: (tcx, l_h - 60),
        1: (W - 170, tcy),
        2: (tcx, 60),
        3: (170, tcy),
    }
    bubble_positions = {
        0: (tcx, l_h - 135),             # 945 — medzi kartou štichu a menovkou
        1: (W - 520, tcy - 160),         # 380
        2: (tcx, 245),
        3: (520, tcy - 160),
    }
    h0, h2 = hand_configs[0], hand_configs[2]
    round_result_positions = {
        0: (h0["x"] + CARD_W // 2, h0["y"] - 50),
        2: (h2["x"] + 7 * h2["offset"] + CARD_W + 90, 190),
    }
    return GameLayout(
        l_h=l_h,
        table_center=(tcx, tcy),
        hand_configs=hand_configs,
        trick_positions=trick_positions,
        trick_collect_targets=trick_collect_targets,
        button_y=tcy + CARD_H // 2 + 18,
        label_positions=label_positions,
        bubble_positions=bubble_positions,
        round_result_positions=round_result_positions,
        message_center_y=l_h - 290,      # 790 — tesne nad rukou hráča
        deal_hint_y=l_h - 60,
        lesson_max_right=tcx - 150 - CARD_W // 2 - 40,
        lesson_max_bottom=hand_bottom_y - 30,
    )


_cache: dict[int, GameLayout] = {}


def game() -> GameLayout:
    """Rozloženie pre aktuálnu logickú výšku okna."""
    from gui import display
    l_h = display.logical_height()
    layout = _cache.get(l_h)
    if layout is None:
        layout = _cache[l_h] = build_game_layout(l_h)
    return layout
