# tutorial2_sandbox/test_zavazok_chapter.py
#
# Headless overenie celej kapitoly "zavazky" (ZavazokDirector) — na
# rozdiel od test_declaration_*.py tu NEJDE o skriptovanú hru: AI sú
# reálne (game/ai.py::AI, "easy"), kolo je reálne rozdanie (len pre
# vybraný seed), a za hráča tu ťahá jednoduchá, ručne napísaná
# strategia (nie skutočný človek) — len aby sme overili, že:
#   a) mechanika kapitoly (panely, "Skúsiť znova"/"Ďalej", striedanie
#      seedov, reálne tlačidlá záväzku + OK) funguje,
#   b) seed 160 ("Beriem všetko") je naozaj vyhrateľný reálnou hrou
#      proti reálnemu "easy" AI, nielen teoreticky podľa heuristiky,
#   c) aspoň niektorý z piatich seedov pre "Nechytím nič" vyjde.
#
# Strategia hráča je zámerne najjednoduchšia možná (chamtivý výber):
#   "Beriem všetko"  → vždy najvyššia legálna karta (maximalizuj šancu
#                      vyhrať štich),
#   "Nechytím nič"   → vždy najnižšia legálna karta (minimalizuj šancu
#                      vyhrať štich).
# Nie je to dôkaz optimálnej hry, len rozumný test, že seedy naozaj
# dávajú hráčovi reálnu šancu, nie iba teoretickú podľa
# DeclarationAdvisor heuristiky.
#
# Záväzok sa v tejto kapitole NEZAMYKÁ — hráč klikne na skutočné
# tlačidlá "Beriem všetko"/"Nechytím nič" + "OK" v príprave, úplne
# rovnako ako v ostrej hre (pozri tutorial/zavazok_director.py). Test
# teda musí tieto kliky simulovať (funkcia confirm_declaration_if_needed
# nižšie), nielen kliky na karty. Čo sa stane pri zámerne ZLOM výbere
# záväzku sa netestuje — seed na daný typ nie je stavaný, takže to
# prirodzene zlyhá a vedie na bežné "Skúsiť znova", žiadna špeciálna
# vetva v kóde na to nie je potrebná.
#
# Použitie:
#   python tutorial2_sandbox/test_zavazok_chapter.py

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Explicitné logické rozlíšenie (gui/display.py). Predtým test bežal na
# tom, čo nahlásil dummy ovládač (1024×768) — teda na inom rozložení než
# hra pri 1080p. Rework rozlíšení, krok 2 (claude/11_…ANALYSIS.md, R9).
os.environ.setdefault("CHUJ_RESOLUTION", "1920x1080")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

pygame.time.delay = lambda ms: None

from game.ai import AI  # noqa: E402
from tutorial.scripted_round import build_tutorial_game_state  # noqa: E402
from gui.screen import Screen  # noqa: E402

from tutorial2_sandbox.zavazok_director import ZavazokDirector  # noqa: E402

MAX_FRAMES = 300_000
MAX_RETRIES_PER_STAGE = 30  # poistka proti nekonečnej slučke v teste


def human_turn_card(screen, game_state, declaration_type: str):
    """Vyberie kartu pre hráča podľa jednoduchej stratégie (pozri hlavu
    súboru) a klikne na ňu presne tak, ako skutočný klik myšou."""
    rnd = game_state.current_round
    if rnd is None or rnd.phase != "tricks" or rnd.current_trick is None:
        return False
    if screen.trick_waiting or screen.card_throw_animation.in_flight:
        return False
    if rnd.get_current_player_index() != game_state.human_index:
        return False
    player = game_state.players[game_state.human_index]
    legal = player.hand.get_playable_cards(
        rnd.current_trick.lead_suit, rnd.trick_number,
        declaration_active=True,
    )
    if not legal:
        return False
    if declaration_type == "all":
        card = max(legal, key=lambda c: c.rank_order)
    else:
        card = min(legal, key=lambda c: c.rank_order)
    pos = screen.card_renderer.hand_card_center(
        game_state.human_index, player.hand.cards, card
    )
    screen._handle_click(pos)
    return True


def confirm_declaration_if_needed(screen, game_state, declaration: str):
    """Klikne na tlačidlo záväzku (ak ešte nie je zvolené to, ktoré
    chceme) a potom na OK — presne tou istou cestou ako skutočný klik
    myšou, cez gui/preparation_handler.py (nič sa neobchádza).

    Klikáme na STRED tlačidla. Predtým sa klikalo pri ľavom okraji, lebo
    pri headless 1024×768 (dummy ovládač) sa stred "Nechytím nič"
    prekrýval s "Chujogramom" (doc 04 §5). Od reworku rozlíšení (krok 2)
    beží test v logickom priestore 1920×1080, kde sa tlačidlá
    neprekrývajú — klik na stred je zároveň regresný test R1."""
    rnd = game_state.current_round
    if rnd is None or rnd.phase != "preparation" or screen.dealing:
        return
    if screen.active_declaration != declaration:
        rect = (screen.phase_renderer._button_decl_all_rect()
                if declaration == "all"
                else screen.phase_renderer._button_decl_none_rect())
        screen._handle_click(rect.center)
        return
    screen._handle_click(screen.phase_renderer._button_ok_rect().center)


def run_test() -> bool:
    """Hráč vždy zvolí záväzok, ktorý daný stupeň navrhuje (štandardný
    priebeh kapitoly)."""
    random.seed()  # skutočne náhodné zamiešanie "Nechytím nič" seedov
    director = ZavazokDirector()
    game_state = build_tutorial_game_state(first_player_index=0)
    ai_players = [None] + [
        AI(game_state.players[i], difficulty="easy", logger=game_state.logger)
        for i in range(1, len(game_state.players))
    ]
    settings = {"tips_enabled": False, "animation_speed": 2.0,
                "table_bg": "table.jpg",
                "chapter_banner": "SANDBOX — ZÁVÄZKY"}
    screen = Screen(game_state, ai_players, debug=False, new_game=True,
                    settings=settings, director=director)

    screen._start_round()

    log = []
    retries_this_stage = 0
    seen_stage = director.stage_index
    frames = 0
    while frames < MAX_FRAMES and screen.running:
        frames += 1
        screen.clock.tick(0)
        screen.step_frame()

        if director.stage_index != seen_stage:
            seen_stage = director.stage_index
            retries_this_stage = 0

        if director.ui_state == "intro":
            pos = director.lesson_panel.next_button.center
            screen._handle_click(pos)
        elif director.ui_state == "prep":
            decl = director.current_stage["declaration"]
            confirm_declaration_if_needed(screen, game_state, decl)
        elif director.ui_state == "playing":
            decl = director.current_stage["declaration"]
            human_turn_card(screen, game_state, decl)
        elif director.ui_state == "done":
            if director.last_result == "fail":
                retries_this_stage += 1
                log.append(f"stage {director.stage_index} "
                          f"('{director.current_stage['declaration']}') "
                          f"seed={director.current_seed} ZLYHALO "
                          f"(pokus {retries_this_stage})")
                if retries_this_stage > MAX_RETRIES_PER_STAGE:
                    print(f"PRERUŠENÉ: stage {director.stage_index} "
                          f"zlyhala {retries_this_stage}x za sebou — "
                          f"poistka proti nekonečnej slučke.")
                    for line in log:
                        print(" ", line)
                    pygame.quit()
                    return False
            else:
                log.append(f"stage {director.stage_index} "
                          f"('{director.current_stage['declaration']}') "
                          f"seed={director.current_seed} ÚSPECH")
            pos = director.lesson_panel.next_button.center
            screen._handle_click(pos)

    ok = (not screen.running) and screen._chapter_exit == "skip"

    print(f"snímky: {frames}")
    print("priebeh:")
    for line in log:
        print(" ", line)
    print(f"_chapter_exit = {screen._chapter_exit!r}")
    print("VÝSLEDOK: OK — kapitola dobehla do konca" if ok
          else "VÝSLEDOK: CHYBA — kapitola sa nedokončila")

    pygame.quit()
    return ok


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)
