# game/savegame.py
#
# Uloženie a obnova rozohratej hry, aby sa dala dohrať aj po zatvorení a
# znovuotvorení programu.
#
# Princíp: neukladá sa "fotka" všetkých objektov, ale RECEPT na kolo —
# rozdanie tak, ako padlo, vysvietenia, záväzok a poradie zahraných
# kariet. Pri načítaní sa kolo prehrá od začiatku cez normálne herné
# metódy. Je to o čosi viac práce než priama serializácia, ale iba takto
# sedí aj pamäť AI (kto je void v akej farbe, čo už padlo, kto vysvietil)
# — a tá sa inak nedá vierohodne obnoviť. Ten istý vzor používa aj
# tester (_replay_history).
#
# Súbor: Documents/Chuj/savegame.json, vedľa settings.json a profile.json.

import json
import os

from game.ai import AI
from game.advisor import Advisor
from game.card import Card
from game.game_state import GameState
from game.hand import Hand
from game.stats_collector import StatsCollector

SAVE_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "savegame.json"
)

SAVE_VERSION = 1

# Polia zberača štatistík, ktoré musia prežiť reštart, aby dohratá hra
# mala správne čísla aj za kolá odohraté pred zatvorením.
_COLLECTOR_FIELDS = (
    "rounds", "clean_rounds", "worst_round", "longest_clean_streak",
    "_clean_streak", "leaf_over_caught", "acorn_over_caught",
    "hearts_caught", "illuminated", "illuminated_caught_own",
    "declared_none", "declared_none_ok", "declared_all", "declared_all_ok",
    "sweeps", "streak_bonus", "reset_100",
)


def _card_to_str(card: Card) -> str:
    return f"{card.suit}:{card.rank}"


def _card_from_str(text: str) -> Card:
    suit, rank = text.split(":")
    return Card(suit, rank)


# ----------------------------------------------------------------------
# Uloženie
# ----------------------------------------------------------------------

def save_game(game_state: GameState, ai_players: list) -> bool:
    """
    Uloží rozohratú hru. Vracia True pri úspechu — zlyhanie zápisu nesmie
    zhodiť hru, hráč len príde o možnosť pokračovať.

    Dohratú hru (phase == "game_over") neukladá — tá sa už dohrať nedá.
    """
    if game_state is None or game_state.phase == "game_over":
        return False

    rnd = game_state.current_round
    round_data = None
    if rnd is not None and rnd.dealt_hands and rnd.phase in ("preparation",
                                                             "tricks"):
        # Poradie zahraných kariet: najprv uzavreté štichy, potom ten
        # rozohraný. Presne v tomto poradí sa bude pri načítaní prehrávať.
        #
        # Ak je rozohraný štich práve KOMPLETNÝ, ale ešte nezozbieraný
        # (stane sa len pri zatvorení okna presne v tej chvíli —
        # pri odchode cez Menu ho Screen._reset_trick_state uzavrie sám),
        # prehranie ho uzavrie za neho. Je to zámer: karty padli, takže
        # štich niekomu patrí, a obnoviť ho ako "visiaci" by hru zaseklo
        # — Screen čaká na príznak trick_waiting, ktorý po načítaní nemá
        # kto nastaviť.
        plays = []
        for trick in rnd.tricks:
            plays.extend([[i, _card_to_str(c)] for i, c in trick.played_cards])
        if rnd.current_trick is not None:
            plays.extend(
                [[i, _card_to_str(c)] for i, c in rnd.current_trick.played_cards]
            )
        round_data = {
            "deal_seed": rnd.deal_seed,
            "first_player_index": rnd.first_player_index,
            "phase": rnd.phase,
            "dealt_hands": [
                [_card_to_str(c) for c in hand] for hand in rnd.dealt_hands
            ],
            "illuminated_by": dict(rnd.illuminated_by),
            "declaration_player": rnd.declaration_player,
            "declaration_type": rnd.declaration_type,
            "plays": plays,
        }

    collector = game_state.stats_collector
    data = {
        "version": SAVE_VERSION,
        "human_index": game_state.human_index,
        "players": [
            {
                "name": p.name,
                "total_score": p.total_score,
                "no_penalty_streak": p.no_penalty_streak,
                "bullets": p.bullets,
            }
            for p in game_state.players
        ],
        "difficulties": [
            (ai.difficulty if ai is not None else None) for ai in ai_players
        ],
        "round_number": game_state.round_number,
        "first_player_index": game_state.first_player_index,
        "round_history": game_state.round_history,
        "round_scores_history": game_state.round_scores_history,
        "bullet_history": game_state.bullet_history,
        "round": round_data,
        "stats": (
            {f: getattr(collector, f) for f in _COLLECTOR_FIELDS}
            if collector is not None else None
        ),
    }

    try:
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (OSError, TypeError, ValueError):
        return False


def has_save() -> bool:
    return os.path.exists(SAVE_PATH)


def delete_save():
    try:
        os.remove(SAVE_PATH)
    except OSError:
        pass


# ----------------------------------------------------------------------
# Načítanie
# ----------------------------------------------------------------------

def load_game(logger=None) -> tuple | None:
    """
    Obnoví uloženú hru. Vracia (game_state, ai_players), alebo None ak
    uložená hra neexistuje, je poškodená, alebo sa ju nepodarí
    zrekonštruovať — v takom prípade sa súbor zmaže, nech hra nezostane
    zaseknutá na chybnom zázname.
    """
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # Súbor existuje, ale nedá sa prečítať. Musí zmiznúť — inak by
        # menu donekonečna ponúkalo "Pokračovať", ktoré vždy zlyhá.
        delete_save()
        return None

    try:
        return _rebuild(data, logger)
    except Exception:
        # Nepodarilo sa prehrať — radšej začať odznova než zamrznúť.
        delete_save()
        return None


def _rebuild(data: dict, logger=None) -> tuple:
    if data.get("version") != SAVE_VERSION:
        raise ValueError("neznáma verzia uloženej hry")

    players_data = data["players"]
    human_index = data.get("human_index", 0)
    game_state = GameState([p["name"] for p in players_data], human_index)
    if logger is not None:
        game_state.logger = logger

    for player, saved in zip(game_state.players, players_data):
        player.total_score = saved["total_score"]
        player.no_penalty_streak = saved["no_penalty_streak"]
        player.bullets = saved["bullets"]

    game_state.round_history = data.get("round_history", [])
    game_state.round_scores_history = data.get("round_scores_history", [])
    game_state.bullet_history = data.get("bullet_history", [])
    game_state.first_player_index = data.get("first_player_index", 0)

    ai_players = [
        None if diff is None
        else AI(game_state.players[i], difficulty=diff,
                logger=game_state.logger)
        for i, diff in enumerate(data.get("difficulties", []))
    ]
    while len(ai_players) < len(game_state.players):
        ai_players.append(None)

    advisor = None
    if 0 <= human_index < len(game_state.players):
        advisor = Advisor(game_state.players[human_index], logger=None)
        game_state.advisor = advisor

    collector = StatsCollector(human_index)
    saved_stats = data.get("stats")
    if saved_stats:
        for field in _COLLECTOR_FIELDS:
            if field in saved_stats:
                setattr(collector, field, saved_stats[field])
    game_state.stats_collector = collector

    round_data = data.get("round")
    if round_data is None:
        # Hra bola uložená medzi kolami — ďalšie kolo sa rozdá normálne.
        game_state.round_number = data.get("round_number", 0)
        game_state.phase = "playing"
        return game_state, ai_players

    _rebuild_round(game_state, ai_players, advisor, round_data,
                   data.get("round_number", 1))
    return game_state, ai_players


def _rebuild_round(game_state, ai_players, advisor, rd, round_number):
    """Zrekonštruuje rozohraté kolo prehraním od rozdania."""
    # start_new_round() číslo kola zvýši, preto ho nastavíme o jedno nižšie.
    game_state.round_number = max(0, round_number - 1)
    game_state.first_player_index = rd["first_player_index"]
    game_state.start_new_round()

    rnd = game_state.current_round
    # Rozdanie z náhodného balíčka zahodíme a nahradíme uloženým — inak by
    # každý hráč dostal iné karty, než mal pred zatvorením hry.
    dealt = [[_card_from_str(c) for c in hand] for hand in rd["dealt_hands"]]
    for player, cards in zip(game_state.players, dealt):
        player.hand = Hand()
        player.receive_cards(list(cards))
    rnd.dealt_hands = [list(h) for h in dealt]
    rnd.deal_seed = rd.get("deal_seed")

    for i, ai in enumerate(ai_players):
        if ai is not None:
            ai.reset_memory()
            ai.memory.init_with_hand(list(dealt[i]))
    if advisor is not None:
        advisor.reset_memory()
        advisor.init_with_hand(list(dealt[game_state.human_index]))

    def feed(method, *args):
        for ai in ai_players:
            if ai is not None:
                getattr(ai, method)(*args)
        if advisor is not None:
            getattr(advisor, method)(*args)

    # Vysvietenia — po hráčoch, nech sedí aj to, kto čo vysvietil.
    illuminated_by = rd.get("illuminated_by") or {}
    for idx in range(len(game_state.players)):
        leaf = illuminated_by.get("leaf") == idx
        acorn = illuminated_by.get("acorn") == idx
        if leaf or acorn:
            rnd.process_revealing(idx, leaf, acorn)
            feed("record_illumination", idx, leaf, acorn)

    decl_player = rd.get("declaration_player")
    decl_type = rd.get("declaration_type")
    if decl_player is not None and decl_type:
        rnd.process_declaration(decl_player, decl_type)
        feed("record_declaration", decl_player, decl_type)

    if rd.get("phase") == "preparation":
        # Hráč ešte nepotvrdil prípravu — nechávame ho presne tam.
        return

    rnd.finish_preparation()

    for player_index, card_text in rd.get("plays", []):
        card = _card_from_str(card_text)
        if not rnd.play_card(player_index, card):
            raise ValueError(
                f"uložená hra: hráč {player_index} nemôže zahrať {card}"
            )
        if rnd.current_trick.is_complete:
            played = list(rnd.current_trick.played_cards)
            winner = rnd.current_trick.get_winner_index()
            feed("record_trick", played, winner, rnd.trick_number)
            rnd.finish_trick()
            if rnd.phase == "tricks":
                rnd.start_trick()

    # Ak sa hra ukladala tesne po dokončení štichu, nový ešte nezačal.
    if rnd.phase == "tricks" and rnd.current_trick is None:
        rnd.start_trick()
