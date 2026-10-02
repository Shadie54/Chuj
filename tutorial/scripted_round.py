# tutorial/scripted_round.py
#
# Podstrčenie PEVNÉHO rozdania do reálneho GameState/Round, aby sa
# naskriptovaná kapitola tutoriálu dala odohrať na tej istej obrazovke
# (gui/screen.py::Screen) ako ostrá hra.
#
# Postup nie je nový — presne takto obnovuje rozohratú hru
# game/savegame.py::_rebuild_round(): nechá GameState rozdať normálne,
# a potom rozdanie prepíše tým, ktoré chce. Dôvod, prečo sa karty
# nevkladajú "rovno pri rozdávaní": Round.deal() je jediné miesto, kde
# sa kolo prepína do fázy "preparation" a zapisuje dealt_hands, a to
# všetko chceme nechať tak, ako je.
#
# Pozri claude/08_TUTORIAL_REFACTOR_DESIGN.md §3, §7.

from game.game_state import GameState
from game.hand import Hand


class SilentLogger:
    """
    Tichý náhradník game/game_logger.py::GameLogger pre tutoriál.

    GameLogger zapisuje priebeh kola do Documents/Chuj/logs/
    current_game.txt. Screen ho volá pri každom štichu a pri uzavretí
    kola — tutoriálové kolo by teda prepísalo log rozohratej OSTREJ hry,
    z ktorého sa diagnostikujú bugy. To je neprijateľné, takže
    tutoriálový GameState dostane namiesto neho túto triedu.

    __getattr__ vracia no-op pre čokoľvek, aby sa test nemusel udržiavať
    pri každom pridaní novej log_* metódy do GameLogger.
    """

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None
        return _noop

    def __repr__(self) -> str:
        return "SilentLogger()"


def human_player_name(default: str = "Hráč") -> str:
    """Meno hráča z aktívneho profilu — rovnako ako game_setup.create_game.
    Štatistiky nesmú byť podmienkou pre spustenie tutoriálu."""
    try:
        from game.profile import load_active_profile
        return load_active_profile().name or default
    except Exception:
        return default


def build_tutorial_game_state(first_player_index: int,
                              human_index: int = 0) -> GameState:
    """
    Postaví GameState pre naskriptovanú kapitolu.

    Rozdiely oproti ostrej hre (game_setup.create_game):
      - tichý logger (pozri SilentLogger),
      - prvý hráč sa NEURČUJE náhodne, ale podľa scenára,
      - žiadny stats_collector sa tu nezakladá; Screen ho pri aktívnom
        režisérovi tiež nezaloží, takže tutoriál sa do štatistík profilu
        nedostane.
    """
    names = [human_player_name(), "Počítač 1", "Počítač 2", "Počítač 3"]
    game_state = GameState(names, human_index)
    game_state.logger = SilentLogger()
    game_state.first_player_index = first_player_index
    return game_state


def apply_scripted_deal(game_state: GameState,
                        hands: dict,
                        deal_seed: int | None = None,
                        illuminations=()) -> None:
    """
    Nahradí práve rozdané (náhodné) kolo pevným rozdaním.

    Volá sa z režiséra hneď po GameState.start_new_round() a MUSÍ to byť
    ešte pred inicializáciou pamäte AI a radcu v Screen._start_round() —
    inak by si pamätali karty z rozdania, ktoré tu práve zahadzujeme.

    hands: {index hráča: [Card, ...]}
    deal_seed: číslo, ktoré sa ukáže v paneli KOLO. Nechať None znamená
        ponechať seed náhodného rozdania, ktoré sme práve zahodili —
        ten by rozdanie NEreprodukoval, čo je pre panel slúžiaci na
        hlásenie bugov horšie než nič. Preto sa sem posiela seed, z
        ktorého ruky naozaj pochádzajú.
    illuminations: [(index hráča, leaf, acorn), ...] — vysvietenia, ktoré
        majú byť v platnosti od začiatku kola (nie až po prípravnej fáze).
    """
    for i, player in enumerate(game_state.players):
        cards = hands.get(i) if isinstance(hands, dict) else hands[i]
        player.hand = Hand()
        player.receive_cards(list(cards))

    rnd = game_state.current_round
    rnd.dealt_hands = [list(player.hand.cards) for player in game_state.players]
    if deal_seed is not None:
        rnd.deal_seed = deal_seed

    for player_index, leaf, acorn in illuminations:
        rnd.process_revealing(player_index, leaf, acorn)
