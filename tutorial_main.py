# tutorial_main.py
#
# Samostatný launcher pre testovanie tutoriálu bez zásahu do hlavnej hry
# (rovnaký princíp ako tester_main.py). Zároveň orchestrátor KAPITOL
# tutoriálu — CHAPTERS nižšie je zoznam (id, run_fn) dvojíc, kde každá
# run_fn je samostatne spustiteľná funkcia (vráti "skip"/"menu", pozri
# jej docstring). main.py (podmenu Tutoriál) nad CHAPTERS stavia výber
# "len túto kapitolu na precvičenie" a podľa "skip"/"menu" buď skočí na
# ďalšiu kapitolu, alebo sa vráti do podmenu — main() nižšie je iba
# samostatný spôsob, ako CHAPTERS prejsť (v poradí, od začiatku, bez
# menu vôbec).

# DPI awareness MUSÍ byť nastavená pred importom pygame/config — inak
# Windows nahlási zmenšené "virtualizované" rozlíšenie (napr. 125% scaling
# na notebooku) a config.py si podľa neho zle spočíta SCREEN_WIDTH/HEIGHT,
# takže karty vpravo/dole (PC1, ruka hráča) vypadnú mimo viditeľné plátno.
# Rovnaký guard ako v main.py.
import ctypes
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

import pygame
from gui.screen import Screen
from gui.game_over_screen import GameOverScreen
from game_setup import load_settings, create_game
from config import DEBUG_MODE
from tutorial.tutorial_director import TutorialDirector
from tutorial.scripted_ai import ScriptedAI
from tutorial.scripted_round import build_tutorial_game_state


def run_chapter_zaklady() -> str:
    """Kapitola 1 — plne naskriptovaná ukážka jedného kola (seed 679339).

    Beží na tom istom gui/screen.py::Screen ako ostrá hra aj kapitola 2.
    Scenár (tutorial/tutorial_steps.py) je len dáta; interpretuje ho
    tutorial/tutorial_director.py, ktorého Screen dostane ako nepovinného
    "režiséra". Bez neho je Screen presne tá istá ostrá hra ako predtým.

    Pôvodná verzia (tutorial/tutorial_screen.py, 1150 riadkov samostatného
    enginu, ktorý veľkú časť Screen duplikoval) bola nahradená v septembri
    2026 — pozri claude/07_TUTORIAL_REFACTOR_CATALOG.md (čo všetko robila)
    a claude/08_TUTORIAL_REFACTOR_DESIGN.md (ako a prečo sa to prerobilo).

    Vracia "skip" (tlačidlo Preskočiť v hornom páse, aj prirodzené
    dokončenie poslednej lekcie tlačidlom Dokončiť) alebo "menu" (bežné
    tlačidlo Menu dole) — presne to, čím skončí gui/screen.py::Screen.run()
    (pozri tam self._chapter_exit). main.py podľa toho skáče na ďalšiu
    kapitolu alebo do podmenu Tutoriálu.
    """
    director = TutorialDirector()
    game_state = build_tutorial_game_state(director.first_player_index)

    # Počítače hrajú podľa scenára, nie podľa uváženia. Vysvietenie
    # Počítača 1 nastavuje režisér už pri rozdaní, preto tu (False, False).
    ai_players = [None] + [
        ScriptedAI(game_state.players[i], director)
        for i in range(1, len(game_state.players))
    ]

    settings = dict(load_settings())
    # Tipy patria tréningovej kapitole; tu by sa ich panel vľavo dole bil
    # s panelom výkladu (pozri návrh §7 č. 6).
    settings["tips_enabled"] = False
    # Horný pás s názvom kapitoly a tlačidlom "Preskočiť"
    # (gui/chapter_banner.py). Meníme len túto lokálnu kópiu nastavení —
    # do settings.json sa nič nezapisuje.
    settings["chapter_banner"] = "TUTORIÁL — PRIEBEH KOLA"

    # new_game=False: úvodné kroky (prehľad trestných kariet, ako funguje
    # štich, body Rozdanie/Vysvietenie/Záväzok) sa hrajú nad PRÁZDNYM
    # stolom. Rozdanie spustí až režisér, keď na to dôjde scenár —
    # tlačidlom "Rozdať karty →".
    screen = Screen(game_state, ai_players, debug=DEBUG_MODE,
                    new_game=False, settings=settings, director=director)
    return screen.run()


def run_chapter_trening() -> str:
    """Kapitola 2 — ostrá tréningová hra. ŽIADNE skriptovanie — reálny
    GameState/AI podľa uložených nastavení (rovnaká obtiažnosť ako "Nová
    hra" v hlavnom menu), identické s gui/screen.py::Screen. Beží kým
    hráč neklikne na Menu v hre alebo na Preskočiť v hornom páse (alebo
    nezavrie okno), s možnosťou "Hraj znova" cez GameOverScreen po
    prekročení 100 bodov.

    Vracia "skip"/"menu" presne podľa toho, ktorým tlačidlom hráč odišiel
    (main.py podľa toho skáče na ďalšiu kapitolu alebo do podmenu
    Tutoriálu) — po Game Over vždy "menu" (Preskočiť už niet kam, kolo je
    dohraté).

    Jediný rozdiel oproti ostrej hre: tipy od AI sú tu zapnuté."""
    settings = dict(load_settings())
    # Tipy chceme v tréningovej kapitole vždy, bez ohľadu na to, ako ich
    # má hráč nastavené v ostrej hre. Meníme len túto lokálnu kópiu — do
    # settings.json sa nič nezapisuje (prepnutie tlačidlom priamo v hre
    # áno, to je vedomá voľba hráča).
    settings["tips_enabled"] = True
    # Horný pás dáva najavo, že nejde o ostrú hru, a ponúka odchod ďalej,
    # keby hráča tréning omrzel (gui/chapter_banner.py). Tá istá
    # komponenta ako v kapitole 1.
    settings["chapter_banner"] = "TRÉNINGOVÁ HRA"
    while True:
        game_state, ai_players = create_game(settings)
        screen = Screen(game_state, ai_players, debug=DEBUG_MODE, settings=settings)
        result = screen.run()

        if result == "game_over":
            if game_state.loser is not None:
                game_over = GameOverScreen(
                    screen.screen,
                    game_state.players,
                    game_state.loser,
                    game_state.round_number,
                    game_state,
                )
                next_action = game_over.run()
                if next_action == "new_game":
                    continue
            # GameOverScreen vracia len "menu"/"new_game" (ošetrené
            # vyššie) — kolo je dohraté, Preskočiť už niet kam.
            return "menu"

        # "skip" (Preskočiť/prirodzené dokončenie) alebo "menu" (tlačidlo
        # Menu v hre) — presne to, čím Screen.run() skončil.
        return result


CHAPTERS = [
    ("zaklady", run_chapter_zaklady),
    ("trening", run_chapter_trening),
]


def main():
    for _chapter_id, run_chapter in CHAPTERS:
        action = run_chapter()
        if action == "quit":
            break
    pygame.quit()


if __name__ == "__main__":
    main()
