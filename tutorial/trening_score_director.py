# tutorial/trening_score_director.py
#
# Jednorazové vysvetľovacie panely pre dve bodovacie pravidlá v
# kapitole "Tréningová hra" (tutorial_main.py::run_chapter_trening()):
#   - "90b pravidlo" (HIGH_SCORE_THRESHOLD=90): keď niektorý hráč
#     prvýkrát v tejto hre dosiahne 90+ bodov, zelený/žaluďový horník
#     mu už nepočítajú do trestných bodov. Sleduje sa pre VŠETKÝCH
#     štyroch hráčov (hráč aj každý počítač samostatne), každého len
#     raz za hru. Ak v jednom kole prekročí hranicu viac hráčov naraz,
#     zobrazí sa JEDEN zlúčený panel so všetkými menami (dohodnuté v
#     konverzácii), nie viac po sebe.
#   - "reset na 90" (WINNING_SCORE=100/RESET_SCORE=90): keď HRÁČ (nie
#     počítače — user: "toto necháme len pre hráča") dosiahne presne
#     100 bodov a hra mu ho vráti na 90. Číta sa priamo z existujúceho
#     príznaku `Player.round_flags["reset_100"]`
#     (game/player.py::finalize_round()) — nič nové sa nepočíta.
#
# DÔLEŽITÉ ARCHITEKTONICKÉ ROZHODNUTIE (poučenie z bugu 2026-10-21,
# pozri claude poznámky k tej oprave): pripojenie AKÉHOKOĽVEK
# diriguenta k Screen vypína automatický štart ďalšieho kola
# (gui/screen.py::step_frame()::next_round_timer, podmienka
# "self.director is None"). Táto kapitola ale director potrebuje na
# celú hru (nielen na úvodný panel), takže namiesto vynechania
# diriguenta si tento director spúšťanie ďalšieho kola PREVEZME CELÉ
# na seba — v bežnom kole urobí presne to, čo by inak urobil natívny
# next_round_timer check (po tých istých ~2.5s zavolá
# screen._start_round()), len v kole, kde treba ukázať panel, túto
# automatiku na okamih nahradí čakaním na klik.
#
# Kontrakt (attach/setup_round/update/is_paused/handle_click/
# restrict_playable/draw/shows/suppress_declaration) je rovnaký ako u
# ostatných diriguentov tutoriálu — Screen sa nemenil.

import pygame

from config import HIGH_SCORE_THRESHOLD
from gui.lesson_panel import LessonPanel

NINETY_PLAYER_TEXT = (
    "Dosiahol si hranicu 90 bodov!\n\n"
    "Pri skóre 90 a viac bodov sa ti zelený ani žaluďový horník už "
    "nepočítajú do trestných bodov. Srdcia sa však počítajú naďalej."
)

NINETY_COMPUTER_TEXT = (
    "{name} dosiahol hranicu 90 bodov!\n\n"
    "Pri skóre 90 a viac bodov sa mu zelený ani žaluďový horník už "
    "nepočítajú do trestných bodov. Srdcia sa mu však počítajú naďalej."
)

NINETY_MERGED_TEXT = (
    "{names} práve dosiahli hranicu 90 bodov!\n\n"
    "Od tejto chvíle sa im zelený ani žaluďový horník nepočítajú do "
    "trestných bodov. Srdcia sa počítajú naďalej."
)

RESET100_TEXT = (
    "Presne 100 bodov? Vraciaš sa na 90!\n\n"
    "Ak dosiahneš presne 100 bodov, skóre sa ti automaticky zníži na "
    "90. Keď si blízko prehry, môžeš toto pravidlo využiť ako "
    "záchrannú stratégiu!"
)

PANEL_TITLE = "Pravidlo bodovania"
PANEL_BUTTON = "Pokračovať →"


def _join_names(names: list[str]) -> str:
    """Slovenské spojenie zoznamu mien: 'A a B' / 'A, B a C'."""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" a {names[-1]}"


class TreningScoreDirector:
    """Pozri hlavu súboru."""

    def __init__(self):
        self.screen = None
        self.lesson_panel = None

        self._score_before: dict[int, int] = {}
        self._shown_90: set[int] = set()
        self._shown_reset100 = False

        # "normal" (bežná hra, director sa do ničoho nemieša) | "panel"
        # (kolo doštichované, čaká sa na klik na vysvetľujúci panel,
        # než sa rozdá ďalšie kolo)
        self.ui_state = "normal"
        self.pending_text = None

    # ------------------------------------------------------------------

    def attach(self, screen):
        self.screen = screen
        self.lesson_panel = LessonPanel(screen.canvas)

    def setup_round(self):
        game_state = self.screen.game_state
        self._score_before = {
            i: p.total_score for i, p in enumerate(game_state.players)
        }
        self.ui_state = "normal"
        self.pending_text = None

    # ------------------------------------------------------------------
    # Priebeh — PREBERÁ natívne spúšťanie ďalšieho kola (pozri hlavu
    # súboru), inak sa správa úplne priehľadne.
    # ------------------------------------------------------------------

    def update(self):
        screen = self.screen
        if self.ui_state == "panel":
            return  # čaká sa na klik, next_round_timer tu nie je čo riešiť
        if not screen.next_round_timer:
            return
        if pygame.time.get_ticks() < screen.next_round_timer:
            return

        # Presne tu by natívny next_round_timer check (gui/screen.py)
        # zavolal screen._start_round() — robíme to za neho, lebo
        # pripojený director to natívne vypína.
        screen.next_round_timer = 0
        text = self._pending_panel_text()
        if text is not None:
            self.pending_text = text
            self.ui_state = "panel"
            return
        screen._start_round()

    def _pending_panel_text(self):
        """Vráti text panela, ktorý treba ukázať PRED ďalším kolom, ak
        nejaký — inak None (bežné pokračovanie bez prerušenia)."""
        game_state = self.screen.game_state
        human_idx = game_state.human_index
        human = game_state.players[human_idx]

        if not self._shown_reset100 and human.round_flags.get("reset_100"):
            self._shown_reset100 = True
            self._shown_90.add(human_idx)  # reset nevyhnutne prešiel aj cez 90+
            return RESET100_TEXT

        crossed = [
            i for i, p in enumerate(game_state.players)
            if i not in self._shown_90
            and self._score_before.get(i, 0) < HIGH_SCORE_THRESHOLD <= p.total_score
        ]
        if not crossed:
            return None
        self._shown_90.update(crossed)

        if len(crossed) == 1:
            i = crossed[0]
            if i == human_idx:
                return NINETY_PLAYER_TEXT
            return NINETY_COMPUTER_TEXT.format(name=game_state.players[i].name)

        names = [game_state.players[i].name for i in crossed]
        return NINETY_MERGED_TEXT.format(names=_join_names(names))

    def is_paused(self) -> bool:
        return self.ui_state == "panel"

    def handle_click(self, pos) -> bool:
        if self.ui_state != "panel":
            return False
        if not self.lesson_panel.next_button.collidepoint(pos):
            return False
        self.ui_state = "normal"
        self.pending_text = None
        self.screen._start_round()
        return True

    def restrict_playable(self, playable):
        return playable

    def draw(self):
        if self.ui_state != "panel":
            return
        self.lesson_panel.draw(
            title=PANEL_TITLE,
            paragraphs=self.pending_text,
            button_label=PANEL_BUTTON,
        )

    def shows(self, element: str) -> bool:
        return True

    def suppress_declaration(self) -> bool:
        return False
