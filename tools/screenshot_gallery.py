# tools/screenshot_gallery.py
#
# Galéria obrazoviek — headless (bez okna) vykreslí všetky dôležité
# obrazovky hry pri zadanom rozlíšení a uloží ich ako PNG.
#
# Načo: rework rozlíšení (claude/11_RESOLUTION_REWORK_ANALYSIS.md, krok 0).
#   1. Pred akoukoľvek zmenou sa vyrobí REFERENCIA pri 1920×1080.
#   2. Po každom kroku reworku sa galéria vyrobí znova a porovná sa
#      (--compare): pri 1920×1080 sa nesmie zmeniť ani pixel.
#   3. Pri iných rozlíšeniach (aj väčších než monitor, napr. 4K) slúži na
#      vizuálnu kontrolu — PNG sa dá prezrieť pri 100 % v prehliadači.
#
# Nástroj hru NEMENÍ a NEZAPISUJE do Documents/Chuj (profil, uložená hra,
# nastavenia, logy) — domovský priečinok sa presmeruje do dočasného
# priečinka s pevným, vymysleným profilom. Výsledok je deterministický:
# pevné seedy, PYTHONHASHSEED=0 a "falošné hodiny" (pygame.time.get_ticks
# sa posúva o presne 16 ms na snímku, nie podľa reálneho času).
#
# Použitie:
#   python tools/screenshot_gallery.py --out gallery/ref_1920x1080
#   python tools/screenshot_gallery.py --resolution 1366x768 --out gallery/1366x768
#   python tools/screenshot_gallery.py --out gallery/po --compare gallery/ref_1920x1080
#   python tools/screenshot_gallery.py --list                # zoznam scén
#   python tools/screenshot_gallery.py --only menu,game      # len niektoré skupiny
#
# Pozor: fonty. Hra používa Tahomu (Windows). Galériu na porovnanie treba
# vždy vyrábať na tom istom počítači — referencia z iného PC (iné fonty)
# sa pixel po pixeli líšiť bude.

import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRAME_MS = 16          # falošné hodiny: o toľko sa posunie čas na snímku
GAME_SEED = 20261023   # seed hry pre herné scény
MENU_SEED = 1          # seed náhodných kariet v pozadí menu

GROUPS = ("menu", "game", "gameover", "tutorial")


# ----------------------------------------------------------------------
# Príprava prostredia — MUSÍ prebehnúť pred importom pygame/config/game
# ----------------------------------------------------------------------

def _ensure_hashseed():
    """AI iteruje cez dict/set s reťazcami — bez PYTHONHASHSEED=0 by sa
    priebeh hry medzi behmi líšil. Rovnaký self-restart ako v
    tester_main.py (subprocess, nie os.execv)."""
    if os.environ.get("PYTHONHASHSEED") != "0":
        env = dict(os.environ, PYTHONHASHSEED="0")
        sys.exit(subprocess.run([sys.executable] + sys.argv, env=env).returncode)


def _isolate_home() -> str:
    """Presmeruje ~ do dočasného priečinka (Windows: USERPROFILE,
    Linux: HOME), aby nástroj nesiahol na skutočný profil, uloženú hru,
    nastavenia ani logy. Vráti cestu k dočasnému domovu."""
    home = tempfile.mkdtemp(prefix="chuj_gallery_")
    os.environ["HOME"] = home
    os.environ["USERPROFILE"] = home
    os.makedirs(os.path.join(home, "Documents", "Chuj"), exist_ok=True)
    return home


def _write_fake_profile(home: str):
    """Vymyslený profil s niekoľkými hrami, aby obrazovka Profil ukázala
    všetky sekcie (nie len "ZATIAĽ ŽIADNE DÁTA")."""
    games = []
    for i, (scores, loser) in enumerate([
        ([104, 62, 48, 77], 0), ([55, 101, 70, 33], 1),
        ([88, 41, 103, 66], 2), ([71, 59, 92, 106], 3),
        ([96, 108, 45, 63], 1),
    ]):
        games.append({
            "difficulties": ["hard", "hard", "medium"],
            "rounds": 9 + i, "final_scores": scores, "my_index": 0,
            "loser_index": loser, "clean_rounds": 3 + i % 2,
            "worst_round": 16, "longest_clean_streak": 2,
            "leaf_over_caught": 1, "acorn_over_caught": i % 2,
            "hearts_caught": 14 + i, "illuminated": i % 3,
            "illuminated_caught_own": 0, "declared_none": 1,
            "declared_none_ok": i % 2, "declared_all": i % 2,
            "declared_all_ok": 0, "sweeps": i % 2, "streak_bonus": 0,
            "reset_100": 1 if i == 2 else 0, "bullets": 1,
        })
    payload = {"version": 1, "active": "Hráč",
               "profiles": {"Hráč": {"name": "Hráč", "abandoned": 2,
                                     "games": games}}}
    path = os.path.join(home, "Documents", "Chuj", "profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _force_resolution(width: int, height: int):
    """Vnúti hre rozlíšenie bez skutočného monitora.

    Dnes config.py číta rozlíšenie z pygame.display.Info() PRI IMPORTE —
    preto tu Info() podvrhneme ešte pred importom configu. Po kroku 2
    reworku bude mať hra vlastný prepínač (premenná prostredia
    CHUJ_RESOLUTION) — nastavujeme ju už teraz, takže nástroj bude
    fungovať pred aj po zmene bez úpravy."""
    import pygame
    os.environ["CHUJ_RESOLUTION"] = f"{width}x{height}"
    os.environ.setdefault("CHUJ_DESKTOP", f"{width}x{height}")

    class _FakeInfo:
        current_w = width
        current_h = height

    pygame.display.Info = lambda: _FakeInfo()


class FakeClock:
    """Deterministický čas — pygame.time.get_ticks() vracia toto."""

    def __init__(self):
        self.now = 1000

    def advance(self, ms: int = FRAME_MS):
        self.now += ms


# ----------------------------------------------------------------------
# Scény
# ----------------------------------------------------------------------

class Gallery:
    def __init__(self, out_dir: str, width: int, height: int, clock: FakeClock):
        import pygame
        self.pygame = pygame
        self.out_dir = out_dir
        self.clock = clock
        # Po kroku 2 reworku otvára okno gui/display.py a obrazovky kreslia
        # na LOGICKÝ povrch; pred ním (pôvodný kód) priamo na okno.
        try:
            from gui import display
            self.display = display
            self.window = display.get_surface()
        except ImportError:
            self.display = None
            self.window = pygame.display.set_mode((width, height))
        self.saved: list[str] = []
        os.makedirs(out_dir, exist_ok=True)

    def shot(self, name: str, surface=None, present: bool = True):
        """Uloží to, čo by videl hráč — fyzické okno po present()."""
        if surface is None:
            if present and self.display is not None:
                self.display.present()
            surface = self.pygame.display.get_surface()
        path = os.path.join(self.out_dir, f"{name}.png")
        self.pygame.image.save(surface, path)
        self.saved.append(name)
        print(f"  {name}.png", file=sys.stderr)

    # --- pomocné pre Screen ---------------------------------------------

    def frame(self, screen, n: int = 1):
        for _ in range(n):
            self.clock.advance()
            screen.step_frame()

    def run_until(self, screen, cond, max_frames: int = 20_000,
                  autoplay: bool = True) -> bool:
        """Beží snímky, kým cond() nie je pravda. autoplay = za hráča
        potvrdzuje prípravu a hrá prvú povolenú kartu (rovnako ako
        tester/regression_screen.py)."""
        if cond():
            return True
        for _ in range(max_frames):
            self.frame(screen)
            # Podmienku kontrolujeme hneď po snímke, ešte PRED autoplay —
            # inak by autoplay zahral za hráča práve v tej snímke, keď sa
            # dostal na ťah, a podmienka "hráč je na ťahu" by nikdy nevyšla.
            if cond():
                return True
            if autoplay and not screen.dealing:
                self._confirm_prep(screen)
                self._human_play(screen)
        return cond()

    @staticmethod
    def _confirm_prep(screen):
        gs = screen.game_state
        rnd = gs.current_round
        if rnd is None or rnd.phase != "preparation" or screen.dealing:
            return
        screen._handle_preparation_click(
            screen.phase_renderer._button_ok_rect().center)

    @staticmethod
    def _human_play(screen):
        gs = screen.game_state
        rnd = gs.current_round
        if rnd is None or rnd.phase != "tricks" or rnd.current_trick is None:
            return
        if screen.trick_waiting or screen.card_throw_animation.in_flight:
            return
        if rnd.get_current_player_index() != gs.human_index:
            return
        player = gs.players[gs.human_index]
        playable = player.hand.get_playable_cards(
            rnd.current_trick.lead_suit, rnd.trick_number,
            declaration_active=rnd.declaration_type is not None)
        if playable:
            pos = screen.card_renderer.hand_card_center(
                gs.human_index, player.hand.cards, playable[0])
            screen._handle_tricks_click(pos)

    @staticmethod
    def human_turn_idle(screen) -> bool:
        gs = screen.game_state
        rnd = gs.current_round
        return (rnd is not None and rnd.phase == "tricks"
                and rnd.current_trick is not None
                and not screen.trick_waiting
                and not screen.card_throw_animation.in_flight
                and not screen.trick_animation.cards_in_flight
                and rnd.get_current_player_index() == gs.human_index)

    # --- skupina: menu ----------------------------------------------------

    def scenes_menu(self):
        import random
        from gui.menu import Menu
        from gui.tutorial_menu import TutorialMenu
        from gui.settings_screen import SettingsScreen
        from gui.stats_screen import StatsScreen
        from game_setup import load_settings

        random.seed(MENU_SEED)
        menu = Menu(self.window, show_continue=True)
        menu._update_hover((0, 0))
        menu._draw()
        self.shot("menu_01_hlavne")

        random.seed(MENU_SEED)
        menu = Menu(self.window, show_continue=False)
        menu._update_hover((0, 0))
        menu._draw()
        self.shot("menu_02_hlavne_bez_pokracovat")

        tmenu = TutorialMenu(self.window, ["zaklady", "zavazky", "trening"])
        tmenu._update_hover((0, 0))
        tmenu._draw()
        self.shot("menu_03_tutorial")

        settings = SettingsScreen(self.window, load_settings())
        settings._update_hover((0, 0))
        settings._draw()
        self.shot("menu_04_nastavenia")
        if hasattr(settings, "tab_rects"):           # záložky od kroku 4
            settings.active_tab = "zobrazenie"
            settings._draw()
            self.shot("menu_04b_nastavenia_zobrazenie")
            if hasattr(settings, "mode_buttons"):    # výber režimu od kroku 7
                settings.pending_windowed = bool(settings.window_sizes)
                settings._draw()
                self.shot("menu_04c_nastavenia_okno")
                # dialóg po prepnutí — bez skutočného prepnutia okna
                import pygame
                settings.confirm = {"old": None, "deadline":
                                    pygame.time.get_ticks() + 15000}
                settings._draw()
                self.shot("menu_04d_nastavenia_potvrdenie")
                settings.confirm = None
            settings.active_tab = "hra"

        stats = StatsScreen(self.window)
        stats._draw()
        self.shot("menu_05_profil")

    # --- skupina: game ----------------------------------------------------

    def _new_game_screen(self, extra_settings: dict | None = None,
                         director=None):
        import random
        from game_setup import create_game
        from gui.screen import Screen

        random.seed(GAME_SEED)
        settings = {"tips_enabled": True, "animation_speed": 1.5,
                    "table_bg": "table.jpg"}
        settings.update(extra_settings or {})
        game_state, ai_players = create_game(settings)
        game_state.players[0].name = "Hráč"
        game_state.stats_collector = None
        screen = Screen(game_state, ai_players, debug=False, new_game=False,
                        settings=settings, director=director)
        return screen, game_state

    def scenes_game(self):
        screen, gs = self._new_game_screen()
        screen._start_round()

        self.frame(screen, 25)
        self.shot("game_01_rozdavanie")

        self.run_until(screen, lambda: not screen.dealing, autoplay=False)
        self.frame(screen, 2)
        self.shot("game_02_priprava")

        screen.active_declaration = "none"
        self.frame(screen)
        self.shot("game_03_priprava_zavazok_vybraty")
        screen.active_declaration = None

        self._confirm_prep(screen)
        self.run_until(screen, lambda: self.human_turn_idle(screen),
                       autoplay=False)
        self.frame(screen, 2)
        self.shot("game_04_stich1_hrac_na_tahu")

        self.run_until(screen, lambda: (
            gs.current_round.trick_number >= 2 and self.human_turn_idle(screen)))
        self.frame(screen, 2)
        self.shot("game_05_stich3_hrac_na_tahu")

        screen.show_last_trick = True
        self.frame(screen)
        self.shot("game_06_posledny_stich")
        screen.show_last_trick = False

        screen.info_overlay.visible = True
        screen.info_overlay.active_tab = "bodovanie"
        self.frame(screen)
        self.shot("game_07_pravidla_bodovanie")
        screen.info_overlay.active_tab = "pravidla"
        self.frame(screen)
        self.shot("game_08_pravidla_pravidla")
        demo = getattr(screen.info_overlay, "rules_demo", None)
        if demo is not None:
            # Animovaná ukážka štichov — každá scéna vo výsledku a scéna 2
            # aj uprostred pohybu karty (deterministicky, falošné hodiny).
            import pygame
            for i in range(6):
                demo.select(i)
                demo._t0 = pygame.time.get_ticks() - 4500
                self.frame(screen)
                self.shot(f"game_08{chr(ord('a') + i)}_pravidla_scena{i + 1}")
            demo.select(1)
            demo._t0 = pygame.time.get_ticks() - 2000
            self.frame(screen)
            self.shot("game_08g_pravidla_scena2_pohyb")
        screen.info_overlay.visible = False

        # Koniec kola (správa + bubliny), potom druhé kolo s Chujogramom.
        self.run_until(screen, lambda: gs.current_round.phase == "done")
        self.frame(screen, 3)
        self.shot("game_09_koniec_kola")

        self.run_until(screen, lambda: (
            gs.round_number >= 2 and not screen.dealing
            and gs.current_round.phase == "preparation"), autoplay=False)
        screen.chujogram.toggle()
        self.frame(screen, 30)
        self.shot("game_10_chujogram")
        return gs

    # --- skupina: gameover ------------------------------------------------

    def scenes_gameover(self, gs=None):
        from gui.game_over_screen import GameOverScreen
        if gs is None:
            screen, gs = self._new_game_screen()
            screen._start_round()
            self.run_until(screen, lambda: gs.current_round.phase == "done")
        for p, score in zip(gs.players, (104, 62, 48, 77)):
            p.total_score = score
        go = GameOverScreen(self.window, gs.players, gs.players[0],
                            gs.round_number, gs)
        go._draw()
        self.shot("gameover_01_prehra_hraca")
        go.show_chujogram = True
        go._draw()
        self.shot("gameover_02_chujogram")

        gs.players[0].total_score, gs.players[1].total_score = 62, 104
        go = GameOverScreen(self.window, gs.players, gs.players[1],
                            gs.round_number, gs)
        go._draw()
        self.shot("gameover_03_vyhra")

    # --- skupina: tutorial ------------------------------------------------

    def scenes_tutorial(self):
        from game_setup import load_settings
        from gui.screen import Screen
        from tutorial.tutorial_director import TutorialDirector
        from tutorial.scripted_ai import ScriptedAI
        from tutorial.scripted_round import build_tutorial_game_state
        from tutorial.zavazok_director import ZavazokDirector
        from tutorial.trening_score_director import TreningScoreDirector
        import random

        # --- kapitola 1 (Základy) — rovnaká stavba ako
        # tutorial_main.py::run_chapter_zaklady, len bez run().
        director = TutorialDirector()
        gs = build_tutorial_game_state(director.first_player_index)
        ai = [None] + [ScriptedAI(gs.players[i], director)
                       for i in range(1, len(gs.players))]
        settings = dict(load_settings())
        settings["tips_enabled"] = False
        settings["chapter_banner"] = "TUTORIÁL — PRIEBEH KOLA"
        screen = Screen(gs, ai, debug=False, new_game=False,
                        settings=settings, director=director)

        # Animácia "čo je štich" — chvíľa, keď sú vidno všetky 4 karty.
        self.frame(screen, 170)
        self.shot("tut1_01_uvod_stich")

        def click_next():
            btn = director.lesson_panel.next_button
            if not btn.width:
                return False
            screen._handle_click(btn.center)
            self.frame(screen, 3)
            return True

        click_next()
        self.shot("tut1_02_trestne_karty")
        click_next()
        self.shot("tut1_03_body_rozdanie")
        click_next()                                   # "Rozdať karty"
        self.run_until(screen, lambda: not screen.dealing, autoplay=False)
        self.frame(screen, 3)
        self.shot("tut1_04_po_rozdani")
        click_next()
        self.shot("tut1_05_vysvietenie")

        # --- kapitola 2 (Záväzok) — úvodný panel po rozdaní
        random.seed(GAME_SEED)
        director2 = ZavazokDirector()
        gs2 = build_tutorial_game_state(first_player_index=0)
        from game.ai import AI
        ai2 = [None] + [AI(gs2.players[i], difficulty="easy",
                           logger=gs2.logger)
                        for i in range(1, len(gs2.players))]
        settings2 = dict(load_settings())
        settings2["tips_enabled"] = False
        settings2["chapter_banner"] = "TUTORIÁL — ZÁVÄZOK"
        screen2 = Screen(gs2, ai2, debug=False, new_game=False,
                         settings=settings2, director=director2)
        screen2._start_round()
        self.run_until(screen2, lambda: not screen2.dealing, autoplay=False)
        self.frame(screen2, 3)
        self.shot("tut2_01_zavazok_uvod")

        # --- kapitola 3 (Tréning) — úvodný panel (vlastná slučka v
        # tutorial_main.py, zachytíme ho cez háčik na display.flip) a
        # príprava prvého kola s pásom kapitoly.
        self._shot_trening_intro()

        screen3, gs3 = self._new_game_screen(
            {"tips_enabled": True, "chapter_banner": "TRÉNINGOVÁ HRA"},
            director=TreningScoreDirector())
        screen3._start_round()
        self.run_until(screen3, lambda: not screen3.dealing, autoplay=False)
        self.frame(screen3, 2)
        self.shot("tut3_02_trening_priprava")

    def _shot_trening_intro(self):
        """_show_trening_intro_panel() je nekonečná slučka čakajúca na klik.
        Pri prvom flip() uložíme obrazovku a podstrčíme klik na tlačidlo."""
        pygame = self.pygame
        import tutorial_main
        state = {"flips": 0}
        real_flip = pygame.display.flip
        real_get = pygame.event.get
        captured = {}

        def fake_flip():
            state["flips"] += 1
            if state["flips"] == 1:
                # present() už logický povrch do okna preškáloval
                self.shot("tut3_01_trening_uvod", present=False)

        def fake_get(*a, **k):
            real_get(*a, **k)   # vyprázdni frontu
            if state["flips"] >= 1:
                panel = captured.get("panel")
                pos = panel.next_button.center if panel else (0, 0)
                if self.display is not None:
                    # get_events() prepočíta fyzické → logické, takže
                    # podvrhnutý klik musí byť vo fyzických súradniciach.
                    vp = self.display.viewport()
                    pos = (round(pos[0] * vp.scale) + vp.ox,
                           round(pos[1] * vp.scale) + vp.oy)
                return [pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                           button=1, pos=pos)]
            return []

        real_panel_cls = tutorial_main.LessonPanel

        class _Spy(real_panel_cls):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                captured["panel"] = self

        pygame.display.flip = fake_flip
        pygame.event.get = fake_get
        tutorial_main.LessonPanel = _Spy
        try:
            tutorial_main._show_trening_intro_panel()
        finally:
            pygame.display.flip = real_flip
            pygame.event.get = real_get
            tutorial_main.LessonPanel = real_panel_cls


# ----------------------------------------------------------------------
# Porovnanie
# ----------------------------------------------------------------------

def compare_dirs(new_dir: str, ref_dir: str) -> bool:
    """Porovná PNG pixel po pixeli. Vypíše počet odlišných pixelov a
    uloží *_diff.png (odlišné pixely červenou)."""
    import pygame
    ok = True
    names = sorted(f for f in os.listdir(ref_dir)
                   if f.endswith(".png") and not f.endswith("_diff.png"))
    for name in names:
        new_path = os.path.join(new_dir, name)
        if not os.path.exists(new_path):
            print(f"[CHÝBA] {name}")
            ok = False
            continue
        a = pygame.image.load(os.path.join(ref_dir, name))
        b = pygame.image.load(new_path)
        if a.get_size() != b.get_size():
            print(f"[ROZMER] {name}: {a.get_size()} vs {b.get_size()}")
            ok = False
            continue
        arr_a = pygame.surfarray.pixels3d(a)
        arr_b = pygame.surfarray.pixels3d(b)
        diff_mask = (arr_a != arr_b).any(axis=2)
        count = int(diff_mask.sum())
        if count:
            ok = False
            diff = b.copy()
            dpx = pygame.surfarray.pixels3d(diff)
            dpx[diff_mask] = (255, 0, 0)
            del dpx
            pygame.image.save(diff, os.path.join(
                new_dir, name.replace(".png", "_diff.png")))
            print(f"[ROZDIEL] {name}: {count} px")
        else:
            print(f"[OK] {name}")
        del arr_a, arr_b
    return ok


# ----------------------------------------------------------------------

def parse_resolution(text: str) -> tuple[int, int]:
    w, h = text.lower().replace("×", "x").split("x")
    return int(w), int(h)


def main():
    parser = argparse.ArgumentParser(
        description="Headless galéria obrazoviek hry (PNG).")
    parser.add_argument("--resolution", default="1920x1080",
                        help="napr. 1366x768, 2560x1600, 3840x2160")
    parser.add_argument("--out", default=None,
                        help="priečinok na PNG (predvolené gallery/<rozlíšenie>)")
    parser.add_argument("--only", default=",".join(GROUPS),
                        help="skupiny oddelené čiarkou: " + ",".join(GROUPS))
    parser.add_argument("--compare", default=None,
                        help="priečinok s referenciou na porovnanie")
    parser.add_argument("--list", action="store_true", help="vypíše skupiny")
    args = parser.parse_args()

    if args.list:
        print("\n".join(GROUPS))
        return

    _ensure_hashseed()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    width, height = parse_resolution(args.resolution)
    out_dir = os.path.abspath(args.out or os.path.join(
        ROOT, "gallery", f"{width}x{height}"))
    compare_dir = os.path.abspath(args.compare) if args.compare else None

    home = _isolate_home()
    _write_fake_profile(home)

    os.chdir(ROOT)                      # assety sa hľadajú relatívne
    sys.path.insert(0, ROOT)

    import pygame
    clock = FakeClock()
    pygame.time.get_ticks = lambda: clock.now
    pygame.time.delay = lambda ms: None
    pygame.time.wait = lambda ms: None
    _force_resolution(width, height)
    pygame.init()

    gallery = Gallery(out_dir, width, height, clock)
    groups = [g.strip() for g in args.only.split(",") if g.strip()]
    print(f"Galéria {width}x{height} -> {out_dir}", file=sys.stderr)

    gs = None
    if "menu" in groups:
        gallery.scenes_menu()
    if "game" in groups:
        gs = gallery.scenes_game()
    if "gameover" in groups:
        gallery.scenes_gameover(gs)
    if "tutorial" in groups:
        gallery.scenes_tutorial()

    print(f"Uložených {len(gallery.saved)} obrázkov.", file=sys.stderr)

    if compare_dir:
        print(f"\nPorovnanie s {compare_dir}:")
        same = compare_dirs(out_dir, compare_dir)
        print("\nVÝSLEDOK: " + ("ZHODA" if same else "ROZDIELY"))
        sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
