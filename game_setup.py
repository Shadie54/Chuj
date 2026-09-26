# game_setup.py
#
# Zdieľaná logika nastavení hry a vytvorenia novej partie — pôvodne
# súkromné funkcie v main.py (_load_settings/_save_settings/_create_game),
# vytiahnuté sem, aby ich mohol používať aj tutorial_main.py (kapitola
# "Ostrá tréningová hra" potrebuje presne rovnaké AI/nastavenia ako
# "Nová hra" v hlavnom menu) bez duplikovania kódu.

import os
from game.game_state import GameState
from game.ai import AI

SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "settings.json"
)


def load_settings() -> dict:
    import json
    default = {
        "ai1_difficulty": "hard",
        "ai2_difficulty": "hard",
        "ai3_difficulty": "hard",
        "table_bg": "table.jpg",
        "animation_speed": 1.5,
        # Tipy od AI (game/advisor.py) — v ostrej hre predvolene vypnuté,
        # hráč si ich zapína tlačidlom "Tipy" priamo v hre (voľba sa sem
        # uloží). Tréningová kapitola tutoriálu si ich zapína natvrdo.
        "tips_enabled": False,
    }
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            default.update(loaded)
            return default
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_settings(settings: dict):
    import json
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def create_game(settings: dict) -> tuple:
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
                AI(player, difficulty=difficulty, logger=game_state.logger)
            )
    return game_state, ai_players
