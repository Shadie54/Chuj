# tutorial_main.py
#
# Samostatný launcher pre testovanie tutoriálu bez zásahu do hlavnej hry
# (rovnaký princíp ako tester_main.py). Zároveň orchestrátor KAPITOL
# tutoriálu — CHAPTERS nižšie je zoznam (id, run_fn) dvojíc, kde každá
# run_fn je samostatne spustiteľná funkcia (vráti "advance"/"quit").
# Vďaka tomu bude neskôr, keď sa tutoriál zapojí do hlavného menu,
# triviálne postaviť nad CHAPTERS výber "len túto kapitolu na
# precvičenie" bez ďalšieho prerábania — main() nižšie je len jeden
# možný spôsob, ako CHAPTERS prejsť (v poradí, od začiatku).

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
from tutorial.tutorial_screen import TutorialScreen
from gui.screen import Screen
from gui.game_over_screen import GameOverScreen
from game_setup import load_settings, create_game
from config import DEBUG_MODE


def run_chapter_zaklady() -> str:
    """Kapitola 1 — plne naskriptovaná ukážka jedného kola (seed 679339).
    Vráti "advance" (dokončené tlačidlom Dokončiť, alebo Preskočiť) alebo
    "quit" (Esc)."""
    return TutorialScreen().run()


def run_chapter_trening() -> str:
    """Kapitola 2 — ostrá tréningová hra. ŽIADNE skriptovanie — reálny
    GameState/AI podľa uložených nastavení (rovnaká obtiažnosť ako "Nová
    hra" v hlavnom menu), identické s gui/screen.py::Screen. Beží kým
    hráč neklikne na Menu v hre (alebo nezavrie okno), s možnosťou "Hraj
    znova" cez GameOverScreen po prekročení 100 bodov.

    Jediný rozdiel oproti ostrej hre: tipy od AI sú tu zapnuté."""
    settings = dict(load_settings())
    # Tipy chceme v tréningovej kapitole vždy, bez ohľadu na to, ako ich
    # má hráč nastavené v ostrej hre. Meníme len túto lokálnu kópiu — do
    # settings.json sa nič nezapisuje (prepnutie tlačidlom priamo v hre
    # áno, to je vedomá voľba hráča).
    settings["tips_enabled"] = True
    while True:
        game_state, ai_players = create_game(settings)
        screen = Screen(game_state, ai_players, debug=DEBUG_MODE, settings=settings)
        result = screen.run()

        if result == "game_over" and game_state.loser is not None:
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

        # Hráč odišiel cez tlačidlo Menu v hre (alebo po Game Over zvolil
        # "Menu") — kapitola tréningovej hry sa tým považuje za ukončenú.
        return "advance"


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
