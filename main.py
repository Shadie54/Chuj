# main.py

import ctypes
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

import sys
import pygame
from game.game_state import GameState
from game.ai import AI
from gui.screen import Screen
from gui.menu import Menu
from gui.settings_screen import SettingsScreen
from gui.game_over_screen import GameOverScreen
from config import DEBUG_MODE


def _create_game(settings: dict) -> tuple:
    player_names = ["Hráč", "Počítač 1", "Počítač 2", "Počítač 3"]
    human_index = 0
    game_state = GameState(player_names, human_index)
    game_state.setup_first_player()

    ai_players = []
    for i, player in enumerate(game_state.players):
        if player.is_human:
            ai_players.append(None)
        else:
            difficulty = settings.get(f"ai{i}_difficulty", "hard")
            ai_players.append(
                AI(player, difficulty=difficulty,
                   logger=game_state.logger)  # ← pridané
            )
    return game_state, ai_players


def _run_game(window, game_state, ai_players,
              new_game: bool = True) -> tuple:
    screen = Screen(game_state, ai_players,
                    debug=DEBUG_MODE, new_game=new_game)
    result = screen.run()
    return result, game_state, ai_players


def main():
    pygame.init()

    import config
    window = pygame.display.set_mode(
        (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    )
    pygame.display.set_caption("Chuj")

    # Ikonka okna
    try:
        icon = pygame.image.load("assets/graphics/icon.png")
        pygame.display.set_icon(icon)
    except FileNotFoundError:
        pass

    settings = {
        "ai1_difficulty": "hard",
        "ai2_difficulty": "hard",
        "ai3_difficulty": "hard",
    }

    active_game_state = None
    active_ai_players = None

    while True:
        menu = Menu(window, show_continue=active_game_state is not None)
        action = menu.run()

        if action == "quit":
            pygame.quit()
            sys.exit()

        elif action == "settings":
            settings_screen = SettingsScreen(window, settings)
            settings = settings_screen.run()

        elif action == "continue" and active_game_state is not None:
            result, active_game_state, active_ai_players = _run_game(
                window, active_game_state, active_ai_players,
                new_game=False
            )
            if result == "game_over" and active_game_state.loser is not None:
                game_over = GameOverScreen(
                    window,
                    active_game_state.players,
                    active_game_state.loser,
                    active_game_state.round_number
                )
                next_action = game_over.run()
                active_game_state = None
                active_ai_players = None
                if next_action == "new_game":
                    active_game_state, active_ai_players = _create_game(settings)

        elif action == "new_game":
            active_game_state, active_ai_players = _create_game(settings)
            result, active_game_state, active_ai_players = _run_game(
                window, active_game_state, active_ai_players
            )

            if result == "game_over" and active_game_state.loser is not None:
                game_over = GameOverScreen(
                    window,
                    active_game_state.players,
                    active_game_state.loser,
                    active_game_state.round_number
                )
                next_action = game_over.run()
                active_game_state = None
                active_ai_players = None
                if next_action == "new_game":
                    active_game_state, active_ai_players = _create_game(settings)


if __name__ == "__main__":
    main()