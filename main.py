# main.py

import ctypes
try:
    # Per-Monitor DPI (Win 8.1+) — správne rozlíšenie aj na druhom monitore
    # s iným zväčšením; staršie Windows: celosystémové DPI.
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import sys
import pygame
from gui.screen import Screen
from gui.menu import Menu
from gui.settings_screen import SettingsScreen
from gui.stats_screen import StatsScreen
from gui.game_over_screen import GameOverScreen
from gui.tutorial_menu import TutorialMenu
from config import DEBUG_MODE
# Nastavenia aj vytvorenie hry sú v game_setup.py, spoločne s
# tutorial_main.py. Dôležité: create_game() odtiaľ berie meno hráča z
# aktívneho profilu — lokálna kópia tejto funkcie v main.py by meno
# opäť natvrdo prepísala na "Hráč" (presne to sa raz už stalo).
from game_setup import load_settings, save_settings, create_game
# CHAPTERS = zoznam (id, run_fn) kapitol — jediný zdroj pravdy, zdieľaný
# so samostatným launcherom tutorial_main.py (pozri tam). TutorialMenu
# dostáva len id, main() podľa neho nájde a spustí zvolenú run_fn.
from tutorial_main import CHAPTERS
from gui import display
from game import savegame
from game import profile as profile_store


def _run_game(window, game_state, ai_players,
              new_game: bool = True, settings: dict = None) -> tuple:
    screen = Screen(game_state, ai_players,
                    debug=DEBUG_MODE, new_game=new_game,
                    settings=settings or {})
    result = screen.run()
    return result, game_state, ai_players


def main():
    pygame.init()

    # Okno (režim, rozlíšenie, ikonka, titulok) otvára výhradne
    # gui/display.py — podľa príkazového riadka (--resolution 1366x768
    # --windowed, --safe), premennej CHUJ_RESOLUTION, settings.json alebo
    # natívneho rozlíšenia monitora. `window` je LOGICKÝ povrch
    # 1920×1080/1200, nie nutne povrch okna.
    window = display.get_surface()

    settings = load_settings()

    active_game_state = None
    active_ai_players = None

    while True:
        # "Pokračovať" sa ponúka aj vtedy, keď v tomto spustení žiadna hra
        # nebeží, ale na disku čaká rozohratá z minula.
        menu = Menu(
            window,
            show_continue=(active_game_state is not None or savegame.has_save())
        )
        action = menu.run()

        if action == "quit":
            pygame.quit()
            sys.exit()


        elif action == "profile":
            StatsScreen(window).run()

        elif action == "tutorial":
            chapter_ids = [chapter_id for chapter_id, _ in CHAPTERS]
            chapter_runners = dict(CHAPTERS)
            choice = TutorialMenu(window, chapter_ids).run()
            while choice != "back":
                # "skip" — tlačidlo Preskočiť (aj prirodzené dokončenie
                # poslednej lekcie) — ide rovno na ďalšiu kapitolu bez
                # zobrazenia podmenu. "menu" — tlačidlo Menu v hre — aj
                # "skip" za poslednou kapitolou (niet už kam skočiť) sa
                # vracajú do podmenu Tutoriálu, NIE do hlavného menu
                # (pozri tutorial_main.py::run_chapter_*, gui/screen.py).
                result = chapter_runners[choice]()
                if result == "skip":
                    next_index = chapter_ids.index(choice) + 1
                    if next_index < len(chapter_ids):
                        choice = chapter_ids[next_index]
                        continue
                choice = TutorialMenu(window, chapter_ids).run()

        elif action == "settings":
            settings_screen = SettingsScreen(window, settings)
            settings = settings_screen.run()
            save_settings(settings)
            # Záložka Zobrazenie mohla okno vytvoriť nanovo (iné rozlíšenie).
            window = display.get_surface()
            # Aktualizuj obtiažnosť ak beží hra
            if active_ai_players is not None:
                for i, ai in enumerate(active_ai_players):
                    if ai is not None:
                        ai.difficulty = settings.get(f"ai{i}_difficulty", "hard")

        elif action == "continue":
            if active_game_state is None:
                loaded = savegame.load_game()
                if loaded is None:
                    # Poškodená alebo zmiznutá uložená hra — savegame si
                    # ju už zmazal, takže len naspäť do menu.
                    continue
                active_game_state, active_ai_players = loaded
                for i, ai in enumerate(active_ai_players):
                    if ai is not None:
                        ai.difficulty = settings.get(
                            f"ai{i}_difficulty", ai.difficulty
                        )

            result, active_game_state, active_ai_players = _run_game(
                window, active_game_state, active_ai_players,
                new_game=False, settings=settings
            )

            if result == "game_over" and active_game_state.losers:
                game_over = GameOverScreen(
                    window,
                    active_game_state.players,
                    active_game_state.losers,
                    active_game_state.round_number,
                    active_game_state
                )
                next_action = game_over.run()
                active_game_state = None
                active_ai_players = None
                if next_action == "new_game":
                    active_game_state, active_ai_players = create_game(settings)


        elif action == "new_game":
            # Nová hra zahadzuje rozohratú — až teraz sa tá stará ráta do
            # štatistík ako nedohratá.
            if savegame.has_save():
                profile_store.record_abandoned()
                savegame.delete_save()
            active_game_state, active_ai_players = create_game(settings)
            result, active_game_state, active_ai_players = _run_game(
                window, active_game_state, active_ai_players,
                settings=settings
            )

            if result == "game_over" and active_game_state.losers:
                while True:
                    game_over = GameOverScreen(
                        window,
                        active_game_state.players,
                        active_game_state.losers,
                        active_game_state.round_number,
                        active_game_state
                    )
                    next_action = game_over.run()
                    active_game_state = None
                    active_ai_players = None

                    if next_action == "new_game":
                        # Rovno spusti novú hru bez menu
                        active_game_state, active_ai_players = create_game(settings)
                        result, active_game_state, active_ai_players = _run_game(
                            window, active_game_state, active_ai_players,
                            settings=settings
                        )
                        if result != "game_over" or not active_game_state.losers:
                            break
                    else:
                        # menu — skoč von zo slučky
                        break

if __name__ == "__main__":
    main()