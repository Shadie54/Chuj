# tester/regression_tutorial_full_flow.py
#
# End-to-end headless regresia CELEJ postupnosti kapitol tutoriálu
# presne tak, ako ju tutorial_main.CHAPTERS/main() spúšťa jednu za
# druhou: "zaklady" -> "zavazky" -> "trening".
#
# Vznikol priamo z bugu 2026-10-21 (po odohraní kola tréningovej hry sa
# nerozdali ďalšie karty), ktorý existujúce testy nemohli odhaliť —
# každý testoval svoju kapitolu izolovane (regression_tutorial.py len
# kapitolu 1, tutorial2_sandbox/test_zavazok_chapter.py len kapitolu
# 2), žiadny neprešiel reálnu sekvenciu všetkých troch za sebou tak,
# ako to robí hráč z menu Tutoriál. Príčina bugu bola navyše medzi-
# kapitolová (pripojenie diriguenta na úvodný panel kapitoly 3 vypnulo
# automatické rozdanie ďalšieho kola — gui/screen.py::step_frame()::
# next_round_timer, podmienka "self.director is None") — presne druh
# problému, ktorý izolované testy jednotlivých kapitol nemusia vidieť.
#
# Kapitoly 1 a 2 sa spúšťajú cez SKUTOČNÉ tutorial_main.run_chapter_*()
# funkcie (teda aj cez gui/screen.py::Screen.run()) — kliky sa vsúvajú
# obalením Screen.step_frame na úrovni TRIEDY (rovnaký trik ako
# run_whole_chapter() v regression_tutorial.py, len spoločný pre
# všetky tri kapitoly naraz, aby sa odhalilo aj prípadné vzájomné
# ovplyvňovanie). Kapitola 1 využíva rovnakú krokovaciu logiku ako
# regression_tutorial.py::act_as_player() (importovanú odtiaľ, nie
# duplikovanú — kópia poradia je zradná, pozri komentár tam).
#
# Kapitola 3 (tréningová hra) sa spúšťa rovnako cez skutočnú
# run_chapter_trening() — AŽ NA úvodný panel
# (tutorial_main._show_trening_intro_panel), ktorý je na čas testu
# nahradený no-op. Dôvod: je to samostatná mini-slučka nad SUROVÝMI
# pygame udalosťami (nie nad Screen), jej správanie (zobraz/zavri
# klikom, nedotkne sa auto-rozdania) bolo overené samostatne pri jej
# vzniku (2026-10-21) a simulovať tu surové pygame udalosti by test
# len zbytočne krehčilo bez toho, aby to pridalo overenie niečoho
# nového. Táto skúška cieli na to, čo sa minule NEODHALILO: viacero
# kôl tréningovej hry automaticky za sebou.
#
# Samotná hra má od 2026-10-21 diriguenta (TreningScoreDirector —
# jednorazové panely "90b"/"reset na 100b"), ktorý si ale spúšťanie
# ďalšieho kola rieši sám (pozri jeho hlavu súboru), takže sa pôvodný
# bug nemôže zopakovať. Dispatcher nižšie preto pre ňu nerozlišuje
# "director is None", ale isinstance TreningScoreDirector — a keď je
# práve zobrazený jej vysvetľujúci panel, len klikne ďalej (reálne
# prekročenie 90b/reset pri náhodnom rozdaní a "hard" AI nie je počas
# krátkeho testu zaručené, ale KEĎ nastane, test tým neskolabuje).
#
# GameOverScreen (zobrazí sa, ak niekto v tréningu prekročí 100b skôr,
# než test odohrá cieľový počet kôl) je z rovnakého dôvodu nahradený
# tak, aby okamžite vrátil "menu" — nejde o súčasť toho, čo sa pokazilo,
# a tiež by inak potreboval vlastné vsúvanie klikov (má vlastnú
# blokujúcu run() slučku).
#
# Použitie:
#   python tester/regression_tutorial_full_flow.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Dôležité: tester.regression_tutorial MUSÍ byť prvý import — presmeruje
# HOME/USERPROFILE do dočasného priečinka PRED tým, než sa čokoľvek
# herné (config, game_setup, ...) importuje a počíta si z neho cesty k
# profilu/nastaveniam/uloženej hre. Rovnaká bezpečnostná poistka ako v
# regression_tutorial.py — tento test sa tiež nemá dotknúť skutočného
# Documents/Chuj hráča.
import tester.regression_tutorial as rt  # noqa: E402

import random  # noqa: E402

import pygame  # noqa: E402

import tutorial_main  # noqa: E402
from gui.screen import Screen  # noqa: E402
from gui.game_over_screen import GameOverScreen  # noqa: E402
from tutorial.tutorial_director import TutorialDirector  # noqa: E402
from tutorial.zavazok_director import ZavazokDirector  # noqa: E402
from tutorial.trening_score_director import TreningScoreDirector  # noqa: E402
from tutorial2_sandbox.test_zavazok_chapter import (  # noqa: E402
    confirm_declaration_if_needed, human_turn_card,
)

MAX_FRAMES_PER_CHAPTER = 200_000
TRENING_ROUNDS_TARGET = 3


# ----------------------------------------------------------------------
# Ovládanie — jeden dispatcher pre všetky tri kapitoly
# ----------------------------------------------------------------------

def _drive_zavazok(screen, game_state, director):
    if director.ui_state in ("intro", "done"):
        screen._handle_click(director.lesson_panel.next_button.center)
    elif director.ui_state == "prep":
        confirm_declaration_if_needed(
            screen, game_state, director.current_stage["declaration"])
    elif director.ui_state == "playing":
        human_turn_card(
            screen, game_state, director.current_stage["declaration"])


def _drive_trening(screen, game_state, director, state):
    """Kapitola 3 — TreningScoreDirector pripojený, ale len na
    jednorazové panely 90b/reset (pozri jeho hlavu súboru). Hráč klikne
    OK bez záväzku a v štichoch zahrá prvú legálnu kartu; keď director
    ukáže vysvetľujúci panel, len klikne ďalej. Po TRENING_ROUNDS_TARGET
    odohratých kolách odíde cez "Preskočiť" v hornom páse — presne
    tlačidlo, ktorým by odišiel aj reálny hráč."""
    if director.ui_state == "panel":
        screen._handle_click(director.lesson_panel.next_button.center)
        return
    rnd = game_state.current_round
    if rnd is None:
        return
    state["rounds_seen"].add(game_state.round_number)
    if len(state["rounds_seen"]) > state["target"]:
        if screen.chapter_banner is not None:
            screen._handle_click(screen.chapter_banner.button.center)
        return
    if screen.dealing:
        return
    if rnd.phase == "preparation":
        if screen._shows("ok"):
            screen._handle_click(screen.phase_renderer._button_ok_rect().center)
        return
    if rnd.phase == "tricks":
        if (screen.trick_waiting or screen.card_throw_animation.in_flight
                or rnd.current_trick is None
                or rnd.get_current_player_index() != game_state.human_index):
            return
        player = game_state.players[game_state.human_index]
        legal = player.hand.get_playable_cards(
            rnd.current_trick.lead_suit, rnd.trick_number,
            declaration_active=rnd.declaration_type is not None,
        )
        if legal:
            pos = screen.card_renderer.hand_card_center(
                game_state.human_index, player.hand.cards, legal[0])
            screen._handle_click(pos)


def install_dispatcher(trening_state):
    """Nahradí Screen.step_frame (na úrovni triedy — platí pre VŠETKY
    tri kapitoly) verziou, ktorá po reálnom kroku vloží jeden klik
    podľa toho, aký director (ak vôbec) je práve pripojený. Vracia
    funkciu na obnovenie pôvodného step_frame a reset počítadla snímok
    pre ďalšiu kapitolu."""
    original = Screen.step_frame
    frames = {"n": 0}

    def patched(self):
        original(self)
        frames["n"] += 1
        if frames["n"] > MAX_FRAMES_PER_CHAPTER:
            self.running = False
            return
        director = self.director
        if isinstance(director, TutorialDirector):
            rt.act_as_player(self, self.game_state, director)
        elif isinstance(director, ZavazokDirector):
            _drive_zavazok(self, self.game_state, director)
        elif isinstance(director, TreningScoreDirector):
            _drive_trening(self, self.game_state, director, trening_state)

    Screen.step_frame = patched

    def reset_frame_counter():
        frames["n"] = 0

    def restore():
        Screen.step_frame = original

    return reset_frame_counter, restore


def main():
    problems = []
    print(f"(dočasný domovský priečinok: {rt._SANDBOX})\n")

    trening_state = {"rounds_seen": set(), "target": TRENING_ROUNDS_TARGET}
    reset_frame_counter, restore_step_frame = install_dispatcher(trening_state)

    orig_intro_panel = tutorial_main._show_trening_intro_panel
    tutorial_main._show_trening_intro_panel = lambda: None

    orig_gameover_run = GameOverScreen.run
    GameOverScreen.run = lambda self: "menu"

    try:
        print("=" * 70)
        print("1) Kapitola 'Základy'")
        print("=" * 70)
        reset_frame_counter()
        # Kapitola 1 má vlastný pevný seed rozdania (TUTORIAL_DEAL_SEED
        # v tutorial/tutorial_director.py) nezávislý od random.seed().
        result1 = tutorial_main.run_chapter_zaklady()
        print(f"  výsledok: {result1!r}")
        if result1 != "skip":
            problems.append(
                f"kapitola 'zaklady' vrátila {result1!r}, čakalo sa 'skip'")

        print()
        print("=" * 70)
        print("2) Kapitola 'Záväzok'")
        print("=" * 70)
        reset_frame_counter()
        random.seed()  # skutočne náhodné zamiešanie seedov "Nechytím nič"
        result2 = tutorial_main.run_chapter_zavazky()
        print(f"  výsledok: {result2!r}")
        if result2 != "skip":
            problems.append(
                f"kapitola 'zavazky' vrátila {result2!r}, čakalo sa 'skip'")

        print()
        print("=" * 70)
        print("3) Kapitola 'Tréningová hra' — viac kôl za sebou "
              "(presne to, čo sa minule pokazilo)")
        print("=" * 70)
        reset_frame_counter()
        result3 = tutorial_main.run_chapter_trening()
        rounds = len(trening_state["rounds_seen"])
        print(f"  výsledok: {result3!r}, odohraných kôl: {rounds}")
        if result3 not in ("skip", "menu"):
            problems.append(f"kapitola 'trening' vrátila {result3!r}")
        if rounds < 2:
            problems.append(
                f"tréningová hra odohrala len {rounds} kolo/kôl — presne "
                f"toto bol bug (2026-10-21): po 1. kole sa ďalšie "
                f"nerozdalo automaticky"
            )
    finally:
        restore_step_frame()
        tutorial_main._show_trening_intro_panel = orig_intro_panel
        GameOverScreen.run = orig_gameover_run
        pygame.quit()
        import shutil
        shutil.rmtree(rt._SANDBOX, ignore_errors=True)

    print()
    print("=" * 70)
    for p in problems:
        print(f"  !! {p}")
    print("VÝSLEDOK:", "celá sekvencia kapitol prechádza" if not problems
          else f"{len(problems)} problémov")
    print("=" * 70)
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
