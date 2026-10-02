# tester/regression_tutorial.py
#
# Regresný test naskriptovanej kapitoly tutoriálu (kapitola 1).
#
# Prejde celú kapitolu ako hráč — headless, cez skutočný
# gui/screen.py::Screen.step_frame() a Screen.run(), takže poradie volaní
# si test nekopíruje a nemôže odbehnúť od toho, čo beží v hre.
#
# Overuje štyri veci:
#   A. obe vetvy scenára dobehnú až po "Dokončiť" a dajú overený priebeh,
#   B. prvky rozhrania sa objavia v tom istom kroku ako v pôvodnom
#      tutoriáli (postupné odhaľovanie),
#   C. kým lekcia čaká na "Ďalej", nedá sa hrať a dokončený štich zostáva
#      odkrytý na stole,
#   D. tutoriál NIČ nezapíše na disk — žiadne štatistiky profilu, žiadny
#      herný log, žiadna uložená hra.
#
# BEZPEČNOSŤ: test si domovský priečinok presmeruje do dočasného, takže
# sa nikdy nedotkne skutočného Documents/Chuj hráča. Musí sa to stať
# PRED importom herných modulov — cesty k profilu, nastaveniam a uloženej
# hre sa počítajú pri importe.
#
# Použitie:
#   python tester/regression_tutorial.py

import os
import sys
import tempfile

_SANDBOX = tempfile.mkdtemp(prefix="chuj-tutorial-test-")
os.environ["HOME"] = _SANDBOX
os.environ["USERPROFILE"] = _SANDBOX
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib          # noqa: E402
import json             # noqa: E402
import random           # noqa: E402
import shutil           # noqa: E402

import pygame           # noqa: E402

# Blokujúce delay() v Screen._handle_ai_turn len zdržuje test.
pygame.time.delay = lambda ms: None

from game.card import Card                                     # noqa: E402
from game.game_logger import GameLogger                        # noqa: E402
from game import savegame                                      # noqa: E402
from game_setup import create_game                             # noqa: E402
from gui.screen import Screen                                  # noqa: E402
from tutorial.scripted_ai import ScriptedAI                    # noqa: E402
from tutorial.scripted_round import (                          # noqa: E402
    SilentLogger, build_tutorial_game_state,
)
from tutorial.tutorial_director import TutorialDirector        # noqa: E402
from tutorial.tutorial_steps import STEPS, BRANCH_B_STEPS      # noqa: E402

CHUJ_DIR = os.path.join(_SANDBOX, "Documents", "Chuj")
LOGS_DIR = os.path.join(CHUJ_DIR, "logs")

MAX_FRAMES = 120_000
STALL_FRAMES = 4000

ELEMENTS = ("round_status", "chujogram", "tips", "info", "menu",
            "ok", "declaration")
EXPECTED_A = [0, 2, 3, 1, 2, 1, 1, 1]
EXPECTED_B = [0, 2, 3, 1, 2, 0, 1, 3]
EXPECTED_FIRST_SEEN = {
    "round_status": "trick2_collect",
    "chujogram": "chujogram_wait",
    "ok": "phase_list",
    "declaration": "phase_list",
}


# ----------------------------------------------------------------------
# Ovládanie kapitoly
# ----------------------------------------------------------------------

def build_chapter(seed=7):
    random.seed(seed)
    director = TutorialDirector()
    game_state = build_tutorial_game_state(director.first_player_index)
    ai_players = [None] + [
        ScriptedAI(game_state.players[i], director)
        for i in range(1, len(game_state.players))
    ]
    settings = {"tips_enabled": False, "animation_speed": 2.0,
                "table_bg": "table.jpg",
                "chapter_banner": "TUTORIÁL — PRIEBEH KOLA"}
    screen = Screen(game_state, ai_players, debug=False, new_game=False,
                    settings=settings, director=director)
    return screen, game_state, director


def act_as_player(screen, game_state, director, prefer_card=None) -> bool:
    """Vykoná jeden klik, ktorý od hráča aktuálny krok práve žiada."""
    if screen.dealing:
        return False
    step = director.current_step()
    if step is None:
        return False
    rnd = game_state.current_round

    if (step["kind"] == "trick" and rnd is not None
            and rnd.phase == "tricks" and rnd.current_trick is not None
            and not screen.trick_waiting
            and not screen.card_throw_animation.in_flight
            and rnd.get_current_player_index() == 0
            and not director.is_paused()):
        player = game_state.players[0]
        legal = player.hand.get_playable_cards(
            rnd.current_trick.lead_suit, rnd.trick_number,
            declaration_active=rnd.declaration_type is not None)
        allowed = director.restrict_playable(legal)
        if allowed:
            card = prefer_card if prefer_card in allowed else allowed[0]
            screen._handle_click(screen.card_renderer.hand_card_center(
                0, player.hand.cards, card))
            return True

    if step["kind"] == "phase_list":
        phase = step["phases"][director.phase_index]
        if (phase["key"] == "vysvietenie"
                and not director.illumination_interacted):
            q = Card("acorn", "over")
            if q in game_state.players[0].hand.cards:
                screen._handle_click(screen.card_renderer.hand_card_center(
                    0, game_state.players[0].hand.cards, q))
                return True
        if phase["key"] == "zavazok" and screen._shows("ok"):
            screen._handle_click(
                screen.phase_renderer._button_ok_rect().center)
            return True

    # Otvoriť a zavrieť Posledný štich musia byť dve rôzne snímky —
    # režisér si "hráč to videl" všíma raz za snímku.
    if screen.show_last_trick and director.last_trick_viewed:
        screen._handle_click((5, 5))
        return True
    if step.get("requires_last_trick_view") and not director.last_trick_viewed:
        if not screen.show_last_trick:
            screen._handle_click(
                screen.phase_renderer._button_last_trick_rect().center)
        else:
            screen._handle_click((5, 5))
        return True

    if step.get("key") == "chujogram_wait" and not director.chujogram_opened:
        screen._handle_click(
            screen.phase_renderer._button_chujogram_rect().center)
        return True

    button = director.lesson_panel.next_button
    if button.width:
        screen._handle_click(button.center)
        return True
    return False


def walk(screen, game_state, director, prefer_card=None, on_frame=None):
    problems, frames = [], 0
    last_marker, last_change = None, 0

    while frames < MAX_FRAMES and screen.running and not director.finished:
        frames += 1
        screen.clock.tick(0)
        screen.step_frame()
        if screen.dealing:
            continue
        step = director.current_step()
        if step is None:
            break
        if on_frame is not None:
            on_frame(step, screen, director)

        marker = (director.step_index, director.phase_index)
        if marker != last_marker:
            last_marker, last_change = marker, frames
        elif frames - last_change > STALL_FRAMES:
            problems.append(
                f"zaseknutie na kroku {marker} "
                f"({step.get('key') or step['kind']})")
            break

        act_as_player(screen, game_state, director, prefer_card)

    if not director.finished and not problems:
        problems.append(f"kapitola nedobehla (krok {director.step_index})")
    return problems, frames


def run_whole_chapter(screen, game_state, director, prefer_card=None):
    """Prejde kapitolu cez SKUTOČNÉ Screen.run(), vrátane toho, čo run()
    robí pri odchode. Kliky vsúvame obalením step_frame — inak sa do
    run() dostať nedajú."""
    original = screen.step_frame
    counter = {"frames": 0}

    def patched():
        original()
        counter["frames"] += 1
        if counter["frames"] > MAX_FRAMES:
            screen.running = False
            return
        act_as_player(screen, game_state, director, prefer_card)

    screen.step_frame = patched
    return screen.run(), counter["frames"]


def winners_of(game_state):
    rnd = game_state.current_round
    return [t.get_winner_index() for t in rnd.tricks] if rnd else []


# ----------------------------------------------------------------------
# Snímka priečinka
# ----------------------------------------------------------------------

def seed_directory():
    """Naplní Documents/Chuj tak, ako to vyzerá u hráča, ktorý hru hral.
    Ide o DOČASNÝ priečinok (pozri _SANDBOX hore), nie o skutočný."""
    shutil.rmtree(CHUJ_DIR, ignore_errors=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(os.path.join(CHUJ_DIR, "settings.json"), "w",
              encoding="utf-8") as f:
        json.dump({"ai1_difficulty": "hard", "tips_enabled": True}, f)
    with open(os.path.join(CHUJ_DIR, "profile.json"), "w",
              encoding="utf-8") as f:
        json.dump({"active": "Hráč", "profiles": {"Hráč": {"games": 42}}}, f)
    with open(os.path.join(CHUJ_DIR, "savegame.json"), "w",
              encoding="utf-8") as f:
        json.dump({"version": 1, "poznamka": "rozohratá ostrá hra"}, f)
    with open(os.path.join(LOGS_DIR, "current_game.txt"), "w",
              encoding="utf-8") as f:
        f.write("KOLO 7 — rozohratá ostrá hra\n")
    with open(os.path.join(LOGS_DIR, "game_20260101_120000.txt"), "w",
              encoding="utf-8") as f:
        f.write("stará dohratá hra\n")


def snapshot():
    out = {}
    for root, _dirs, files in os.walk(CHUJ_DIR):
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()[:16]
            out[os.path.relpath(path, CHUJ_DIR)] = (digest,
                                                    os.path.getsize(path))
    return out


def compare(before, after):
    problems = []
    for path in sorted(set(before) | set(after)):
        if path not in before:
            problems.append(f"pribudol súbor: {path}")
        elif path not in after:
            problems.append(f"zmizol súbor: {path}")
        elif before[path] != after[path]:
            problems.append(f"zmenil sa súbor: {path}")
    return problems


# ----------------------------------------------------------------------

def main():
    problems = []
    print(f"(dočasný domovský priečinok: {_SANDBOX})\n")

    print("=" * 70)
    print("A/B/C) Celá kapitola — základná vetva")
    print("=" * 70)
    screen, game_state, director = build_chapter()
    state = {"first_seen": {}, "steps": [], "paused_playable": 0,
             "trick_on_table": 0}

    def on_frame(step, scr, d):
        for element in ELEMENTS:
            if scr._shows(element) and element not in state["first_seen"]:
                state["first_seen"][element] = step.get("key") or step["kind"]
        marker = (d.step_index, d.phase_index)
        if not state["steps"] or state["steps"][-1] != marker:
            state["steps"].append(marker)
        rnd = game_state.current_round
        if (d.is_paused() and rnd is not None and rnd.phase == "tricks"
                and rnd.current_trick is not None):
            legal = game_state.players[0].hand.get_playable_cards(
                rnd.current_trick.lead_suit, rnd.trick_number,
                declaration_active=rnd.declaration_type is not None)
            if legal and d.restrict_playable(legal):
                state["paused_playable"] += 1
        if (step["kind"] == "trick" and rnd is not None
                and rnd.current_trick is not None
                and rnd.current_trick.is_complete
                and d._released_trick != rnd.trick_number):
            state["trick_on_table"] += 1

    prob, frames = walk(screen, game_state, director, on_frame=on_frame)
    problems += prob
    w = winners_of(game_state)
    print(f"  víťazi štichov: {w}")
    print(f"  poradie krokov: {[s for s, _ in state['steps']]}")
    if w != EXPECTED_A:
        problems.append(f"víťazi {w} != overených {EXPECTED_A}")
    reached = {s for s, _ in state["steps"]}
    missing = [i for i in range(len(STEPS)) if i not in reached]
    if missing:
        problems.append(f"nenavštívené kroky: {missing}")

    print("  prvý výskyt prvkov rozhrania:")
    for element in ELEMENTS:
        print(f"    {element:14s} {state['first_seen'].get(element, 'nikdy')}")
    for element, want in EXPECTED_FIRST_SEEN.items():
        got = state["first_seen"].get(element)
        if got != want:
            problems.append(
                f"{element} sa objavil pri '{got}', čakalo sa '{want}'")
    if "tips" in state["first_seen"]:
        problems.append("Tipy sa v kapitole 1 ukázali")

    print(f"  povolená karta počas pauzy: {state['paused_playable']}× "
          f"(má byť 0)")
    print(f"  snímok s odkrytým dokončeným štichom: "
          f"{state['trick_on_table']}")
    if state["paused_playable"]:
        problems.append("počas pauzy sa dalo hrať")
    if state["trick_on_table"] < 8:
        problems.append("dokončený štich nezostal odkrytý na stole")

    print()
    print("=" * 70)
    print("A) Vetva B — hráč si v trick4 nechá guľového kráľa")
    print("=" * 70)
    screen_b, gs_b, d_b = build_chapter(seed=11)
    prob_b, _ = walk(screen_b, gs_b, d_b, prefer_card=Card("bell", "eight"))
    problems += prob_b
    w_b = winners_of(gs_b)
    print(f"  víťazi štichov: {w_b}")
    if w_b != EXPECTED_B:
        problems.append(f"víťazi vetvy B {w_b} != overených {EXPECTED_B}")
    else:
        variant = "trick8_p1" if w_b[6] == 1 else "trick8_p2"
        if d_b.step_for_trick(6) is not BRANCH_B_STEPS.get("trick7"):
            problems.append("trick7 neprišiel z vetvy B")
        if d_b.step_for_trick(7) is not BRANCH_B_STEPS.get(variant):
            problems.append(f"trick8 nie je variant {variant}")
        else:
            print(f"  trick7 z vetvy B, trick8 variant {variant}")

    print()
    print("=" * 70)
    print("D) Tutoriál nesmie nič zapísať na disk")
    print("=" * 70)
    seed_directory()
    before = snapshot()
    print(f"  pred behom: {len(before)} súborov")
    screen_d, gs_d, d_d = build_chapter(seed=13)
    result, frames_d = run_whole_chapter(screen_d, gs_d, d_d)
    print(f"  run() vrátil {result!r} po {frames_d} snímkach")
    # "skip" — prirodzené dokončenie poslednej lekcie sa od 2026-09-30
    # správa rovnako ako tlačidlo Preskočiť (main.py vďaka tomu skáče
    # rovno na ďalšiu kapitolu, pozri gui/screen.py::run() a
    # tutorial/tutorial_director.py).
    if result != "skip":
        problems.append(f"run() vrátil {result!r}, čakalo sa 'skip'")
    diffs = compare(before, snapshot())
    problems += diffs
    if not diffs:
        print("  ŽIADNA zmena na disku")
    if gs_d.stats_collector is not None:
        problems.append("tutoriál si založil zberač štatistík")
    if not isinstance(gs_d.logger, SilentLogger):
        problems.append("tutoriál nemá tichý logger")

    print()
    print("=" * 70)
    print("Protiskúška — v ostrej hre to musí fungovať ďalej")
    print("=" * 70)
    settings = {"tips_enabled": False, "animation_speed": 1.0,
                "table_bg": "table.jpg"}
    gs_real, ais_real = create_game(settings)
    Screen(gs_real, ais_real, debug=False, new_game=False, settings=settings)
    if gs_real.stats_collector is None:
        problems.append("ostrá hra prišla o zberač štatistík")
    else:
        print("  ostrá hra si zakladá zberač štatistík")

    os.remove(os.path.join(CHUJ_DIR, "savegame.json"))
    gs_real.start_new_round()
    if not (savegame.save_game(gs_real, ais_real)
            and os.path.exists(os.path.join(CHUJ_DIR, "savegame.json"))):
        problems.append("ostrá hra sa už nedá uložiť")
    else:
        print("  ostrá hra sa dá uložiť")

    log_path = os.path.join(LOGS_DIR, "current_game.txt")
    os.remove(log_path)
    logger = GameLogger()
    logger.entries.append("skúška")
    logger.save_round()
    if not os.path.exists(log_path):
        problems.append("ostrá hra už nepíše herný log")
    else:
        print("  ostrá hra píše herný log")

    os.remove(log_path)
    silent = SilentLogger()
    silent.new_round(1, "Hráč", {})
    silent.save_round()
    if os.path.exists(log_path):
        problems.append("tichý logger napriek tomu zapísal log")
    else:
        print("  tichý logger nezapísal nič")

    shutil.rmtree(_SANDBOX, ignore_errors=True)

    print()
    print("=" * 70)
    for p in problems:
        print(f"  !! {p}")
    print("VÝSLEDOK:", "tutoriál prechádza" if not problems
          else f"{len(problems)} problémov")
    print("=" * 70)
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
