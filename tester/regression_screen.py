# tester/regression_screen.py
#
# Regresný test celej obrazovky ostrej hry (gui/screen.py::Screen).
#
# Načo je to dobré: tester/simulator.py overuje HERNÚ LOGIKU (Round, AI,
# bodovanie), ale obchádza GUI. Tento test naopak odohrá celé kolá cez
# skutočný Screen — cez tie isté metódy, ktoré volá Screen.run() v jednej
# iterácii slučky, vrátane klikov hráča cez reálny _handle_tricks_click a
# card_renderer. Beží headless (SDL dummy driver), takže nepotrebuje
# obrazovku a dá sa pustiť kedykoľvek.
#
# Použitie:
#   python tester/regression_screen.py                   # vypíše stopu
#   python tester/regression_screen.py --out pred.txt    # uloží stopu
#   ...zmeny v kóde...
#   python tester/regression_screen.py --out po.txt
#   fc pred.txt po.txt        (Windows)  /  diff pred.txt po.txt  (Linux)
#
# Stopa musí zostať IDENTICKÁ pri každej zmene, ktorá nemá meniť priebeh
# hry. Presne takto sa overila etapa 1 refaktoru tutoriálu (pridanie
# nepovinného "režiséra" do Screen) — pozri
# claude/08_TUTORIAL_REFACTOR_DESIGN.md.
#
# Pozor: stopa zámerne NEOBSAHUJE počet snímok ani časy — tie sa medzi
# behmi líšia a nič nevypovedajú. Obsahuje len herné fakty.

import argparse
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

# Blokujúce delay() v Screen._handle_ai_turn len zdržuje test. Na priebeh
# hry nemá vplyv — Screen sa aj tak riadi get_ticks() a stavom animácií.
pygame.time.delay = lambda ms: None

from game_setup import create_game   # noqa: E402
from gui.screen import Screen        # noqa: E402

DEFAULT_SEED = 20260926
DEFAULT_ROUNDS = 2
MAX_FRAMES = 500_000


def _new_screen(seed: int):
    random.seed(seed)
    settings = {
        "tips_enabled": True,        # nech sa otestuje aj cesta tipov
        "animation_speed": 2.0,
        "table_bg": "table.jpg",
    }
    game_state, ai_players = create_game(settings)
    # Meno hráča môže prísť z profilu na disku — v stope ho zjednotíme,
    # nech test nezávisí od toho, aký profil je práve aktívny.
    game_state.players[0].name = "Hráč"
    # Test nesmie zapisovať do štatistík profilu.
    game_state.stats_collector = None

    screen = Screen(game_state, ai_players, debug=False, new_game=False,
                    settings=settings)
    return screen, game_state


def build_trace(seed: int = DEFAULT_SEED,
                rounds: int = DEFAULT_ROUNDS) -> list[str]:
    """Odohrá zadaný počet kôl cez Screen a vráti deterministickú stopu."""
    screen, game_state = _new_screen(seed)

    trace: list[str] = []
    seen_tricks: set = set()
    scored_rounds: set = set()
    rounds_done = 0

    def note(line):
        trace.append(line)

    def human_click_if_possible():
        """Za hráča klikne na prvú povolenú kartu — reálnou cestou klikom,
        nie obídením GUI."""
        rnd = game_state.current_round
        if rnd is None or rnd.phase != "tricks" or rnd.current_trick is None:
            return
        if screen.trick_waiting or screen.card_throw_animation.in_flight:
            return
        if rnd.get_current_player_index() != game_state.human_index:
            return
        player = game_state.players[game_state.human_index]
        playable = player.hand.get_playable_cards(
            rnd.current_trick.lead_suit, rnd.trick_number,
            declaration_active=rnd.declaration_type is not None,
        )
        if not playable:
            return
        pos = screen.card_renderer.hand_card_center(
            game_state.human_index, player.hand.cards, playable[0]
        )
        screen._handle_tricks_click(pos)

    def confirm_preparation_if_needed():
        """V prípravnej fáze klikne OK (bez záväzku, bez vysvietenia)."""
        rnd = game_state.current_round
        if rnd is None or rnd.phase != "preparation" or screen.dealing:
            return
        screen._handle_preparation_click(
            screen.phase_renderer._button_ok_rect().center
        )

    def record_finished_tricks():
        rnd = game_state.current_round
        if rnd is None:
            return
        for i, trick in enumerate(rnd.tricks):
            key = (game_state.round_number, i)
            if key in seen_tricks:
                continue
            seen_tricks.add(key)
            cards = " ".join(f"{p}:{c}" for p, c in trick.played_cards)
            note(f"kolo {game_state.round_number} štich {i + 1}: {cards} "
                 f"-> víťaz {trick.get_winner_index()} "
                 f"body {trick.total_base_points}")

    note(f"seed={seed} rounds={rounds}")
    screen._start_round()
    note(f"kolo {game_state.round_number} rozdanie "
         f"seed={game_state.current_round.deal_seed}")
    for i, p in enumerate(game_state.players):
        note(f"  ruka {i}: " + " ".join(str(c) for c in p.hand.cards))

    frames = 0
    while frames < MAX_FRAMES and rounds_done < rounds:
        frames += 1
        screen.clock.tick(0)   # bez limitu FPS — test nemá bežať v reálnom čase

        round_before = game_state.round_number

        was_dealing = screen.dealing
        # Jedna snímka presne tak, ako ju beží hra — nekopírujeme si
        # poradie volaní, aby test nemohol odbehnúť od skutočnosti.
        screen.step_frame()
        if game_state.round_number > round_before:
            note(f"kolo {game_state.round_number} rozdanie "
                 f"seed={game_state.current_round.deal_seed}")
        if was_dealing and not screen.dealing:
            note(f"kolo {game_state.round_number} po rozdaní ruka hráča: "
                 + " ".join(str(c) for c in
                            game_state.players[
                                game_state.human_index].hand.cards))
        if not screen.dealing:
            confirm_preparation_if_needed()
            human_click_if_possible()

        record_finished_tricks()

        rnd = game_state.current_round
        if (rnd is not None and rnd.phase == "done"
                and game_state.round_number not in scored_rounds):
            scored_rounds.add(game_state.round_number)
            rp = " ".join(f"{p.name}={p.round_points}"
                          for p in game_state.players)
            sc = " ".join(f"{p.name}={p.total_score}"
                          for p in game_state.players)
            note(f"kolo {game_state.round_number} KONIEC body kola: {rp}")
            note(f"kolo {game_state.round_number} KONIEC skóre: {sc}")
            note(f"kolo {game_state.round_number} guličky: "
                 f"{game_state.bullet_history[-1] if game_state.bullet_history else None}")
            rounds_done += 1

    note(f"odohrané kolá: {rounds_done}")
    if rounds_done < rounds:
        note("!! test nedohral požadovaný počet kôl — pozri MAX_FRAMES")
    return trace


# ----------------------------------------------------------------------
# Samostatné kontroly (nie súčasť stopy)
# ----------------------------------------------------------------------

def check_resume_sort() -> tuple[bool, str]:
    """
    Po návrate do rozohratej hry ("Pokračovať") musí byť ruka hráča
    zoradená rovnako ako po rozdaní.

    Bug z 2026-09-26: Screen.run() zoraďoval ruku len vo vetve rozdávania,
    ktorá pri new_game=False vôbec nenastane — hráč tak po znovuotvorení
    hry videl karty v poradí, v akom padli pri rozdaní.
    """
    from game.hand import Hand

    screen, game_state = _new_screen(DEFAULT_SEED)
    screen._start_round()

    # Zámerne rozhádzaná ruka, akoby prišla z uloženej hry.
    player = game_state.players[game_state.human_index]
    scrambled = list(player.hand.cards)
    random.shuffle(scrambled)
    player.hand = Hand()
    player.receive_cards(scrambled)

    expected = list(scrambled)
    tmp = Hand()
    tmp.cards = list(scrambled)
    tmp.sort_hand()
    expected = list(tmp.cards)

    # Presne to, čo urobí run() pri new_game=False.
    screen.new_game = False
    screen._sort_human_hand()

    got = list(player.hand.cards)
    ok = got == expected
    detail = ("ruka po návrate je zoradená" if ok else
              f"zoradenie zlyhalo: {[str(c) for c in got]}")
    return ok, detail


def check_round_counter() -> tuple[bool, str]:
    """
    Panel KOLO (gui/round_status.py) musí v prvom kole ukazovať "KOLO 1".

    Bug z 2026-09-26: GameState.start_new_round() priraďoval
    Round.round_number PRED zvýšením čítača, takže hodnota bola vždy o
    jedna nižšia a prvé kolo sa zobrazovalo ako "KOLO 0" — hoci herný log
    už správne hovoril o kole 1.
    """
    screen, game_state = _new_screen(DEFAULT_SEED)
    seen = []
    for _ in range(3):
        screen._start_round()
        screen.dealing = False
        screen.deal_animation = None
        seen.append(game_state.current_round.round_number)
    ok = seen == [1, 2, 3]
    return ok, ("čísla kôl " + str(seen) +
                ("" if ok else " — očakávané [1, 2, 3]"))


def main():
    parser = argparse.ArgumentParser(
        description="Regresný test obrazovky ostrej hry (headless)."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--out", default=None,
                        help="súbor, do ktorého sa stopa uloží")
    parser.add_argument("--checks-only", action="store_true",
                        help="len samostatné kontroly, bez stopy")
    args = parser.parse_args()

    checks = [
        ("zoradenie ruky po 'Pokračovať'", check_resume_sort),
        ("číslo kola v paneli KOLO", check_round_counter),
    ]
    ok = True
    for name, fn in checks:
        passed, detail = fn()
        ok = ok and passed
        print(f"[kontrola] {name}: {'OK' if passed else 'CHYBA'} — {detail}",
              file=sys.stderr)

    if args.checks_only:
        sys.exit(0 if ok else 1)

    trace = build_trace(args.seed, args.rounds)
    text = "\n".join(trace)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"stopa uložená do {args.out} ({len(trace)} riadkov)",
              file=sys.stderr)
    else:
        print(text)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
