# tester/regression_layout.py
#
# Regresný test rozloženia obrazoviek pri rôznych rozlíšeniach — rework
# rozlíšení, krok 3 (claude/11_RESOLUTION_REWORK_ANALYSIS.md §5, §6).
#
# Pre každé podporované rozlíšenie postaví (headless) obrazovky hry a
# overí v LOGICKÝCH súradniciach:
#   1. klikateľné prvky, ktoré sú na obrazovke súčasne, sa neprekrývajú
#      (napr. "Nechytím nič" × "Chujogram" — doc 04 §5, regresia R1),
#   2. klikateľné prvky nevyčnievajú z logického priestoru 1920×L_h,
#   3. ruky hráčov sú viditeľné (R2/R3 — ruka hráča pod okrajom, PC1 mimo).
# Pri 1920×1080 navyše overí prepnutie zobrazenia ZA BEHU (Nastavenia →
# Zobrazenie, krok 7): okno 1440×900 (logicky 1920×1200) → všetky obrazovky
# znova, s novou logickou výškou.
#
# Každé rozlíšenie beží v samostatnom procese (config.py si logickú výšku
# číta pri importe — gui/display.py, CHUJ_RESOLUTION).
#
# Použitie:
#   python tester/regression_layout.py              # všetky rozlíšenia
#   python tester/regression_layout.py --one 1366x768
#   python tester/regression_layout.py --verbose    # vypíše aj obdĺžniky

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cieľové rozlíšenia (analýza §3) + 1024×768 ako záťažový prípad bugu §5.
RESOLUTIONS = [
    "1366x768", "1280x720", "1600x900", "1920x1080", "2560x1440", "3840x2160",
    "1280x800", "1440x900", "1680x1050", "1920x1200", "2560x1600", "2880x1800",
    "2560x1080", "3440x1440", "1024x768",
]

# Minimálna viditeľná výška ruky hráča (logické px). Pri 1080p je 220 z 293.
MIN_HAND_VISIBLE = 200


def _overlaps(group: dict) -> list[str]:
    problems = []
    names = list(group)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ra, rb = group[a], group[b]
            if ra.colliderect(rb):
                clip = ra.clip(rb)
                problems.append(f"prekryv {a} × {b}: {clip.width}×{clip.height}")
    return problems


def _outside(group: dict, width: int, height: int,
             allow: tuple = ()) -> list[str]:
    import pygame
    area = pygame.Rect(0, 0, width, height)
    return [f"mimo obrazovky {name}: {rect}"
            for name, rect in group.items()
            if name not in allow and not area.contains(rect)]


def run_one(resolution: str, verbose: bool) -> list[str]:
    """Beží v samostatnom procese — prostredie sa nastaví PRED importom."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["CHUJ_RESOLUTION"] = resolution
    os.environ["CHUJ_DESKTOP"] = resolution     # ponuka veľkostí okna
    home = tempfile.mkdtemp(prefix="chuj_layout_")
    os.environ["HOME"] = home
    os.environ["USERPROFILE"] = home
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)

    import pygame
    pygame.time.delay = lambda ms: None

    from config import SCREEN_WIDTH
    from gui import layout
    from game_setup import load_settings
    from gui import display

    problems: list[str] = []
    tag = ""

    def check(screen_name: str, group: dict, allow_outside: tuple = ()):
        W, H = SCREEN_WIDTH, display.logical_height()
        if verbose:
            for name, rect in group.items():
                print(f"    {tag}{screen_name}.{name}: {rect}")
        for p in _overlaps(group) + _outside(group, W, H, allow_outside):
            problems.append(f"{tag}{screen_name}: {p}")

    def check_all():
        check_screens(display.get_surface(), check, problems)

    check_all()
    if resolution == "1920x1080":
        from gui.settings_screen import SettingsScreen
        settings = SettingsScreen(display.get_surface(), load_settings())
        settings.pending_windowed = True
        settings.pending_size = (1440, 900)
        settings._apply_display()
        settings._confirm_keep()
        mode, vp = display.current_mode(), display.viewport()
        if (mode.width, mode.height, mode.windowed) != (1440, 900, True) \
                or vp.l_h != 1200 or layout.game().l_h != 1200:
            problems.append(f"prepnutie za behu: {mode} {vp}")
        tag = "[po prepnutí 1440x900] "
        check_all()
    return problems


def check_screens(window, check, problems: list[str]):
    """Postaví všetky obrazovky pre AKTUÁLNE okno a skontroluje ich."""
    import random
    import pygame
    from config import SCREEN_WIDTH, CARD_SIZE_MEDIUM
    from gui import layout
    from game_setup import create_game, load_settings
    from gui.screen import Screen
    from gui.menu import Menu
    from gui.tutorial_menu import TutorialMenu
    from gui.settings_screen import SettingsScreen
    from gui.stats_screen import StatsScreen
    from gui.game_over_screen import GameOverScreen
    from gui.chapter_banner import ChapterBanner
    from gui import display

    HAND_CONFIGS = layout.game().hand_configs
    W, H = SCREEN_WIDTH, display.logical_height()

    # --- herná obrazovka -------------------------------------------------
    random.seed(1)
    game_state, ai_players = create_game({"tips_enabled": True})
    game_state.stats_collector = None
    screen = Screen(game_state, ai_players, debug=False, new_game=False,
                    settings={"tips_enabled": True})
    screen._start_round()
    screen.dealing = False
    screen.deal_animation = None
    pr = screen.phase_renderer

    cw, ch = CARD_SIZE_MEDIUM
    hand_cfg = HAND_CONFIGS[0]
    n_cards = len(game_state.players[0].hand.cards)
    hand = pygame.Rect(hand_cfg["x"], hand_cfg["y"],
                       (n_cards - 1) * hand_cfg["offset"] + cw, ch)
    # Ruka zámerne presahuje spodný okraj — do testu ide jej viditeľná časť
    # (klikateľná plocha), vrchných 20 px navyše kvôli vysvieteniu horníka.
    hand_visible = hand.clip(pygame.Rect(0, 0, W, H)).inflate(0, 20).move(0, -10)
    if hand_visible.height - 20 < MIN_HAND_VISIBLE:
        problems.append(f"hra: ruka hráča viditeľná len {hand_visible.height - 20} px "
                        f"(min. {MIN_HAND_VISIBLE})")

    column = {
        "Tipy": pr._button_tips_rect(),
        "Posledný štich": pr._button_last_trick_rect(),
        "Chujogram": pr._button_chujogram_rect(),
        "Pravidlá": pr._button_info_rect(),
        "Menu": pr._button_menu_rect(),
    }
    check("hra/príprava", {**column,
                           "Beriem všetko": pr._button_decl_all_rect(),
                           "Nechytím nič": pr._button_decl_none_rect(),
                           "OK": pr._button_ok_rect(),
                           "ruka hráča": hand_visible},
          allow_outside=("ruka hráča",))
    check("hra/štichy", {**column, "ruka hráča": hand_visible},
          allow_outside=("ruka hráča",))

    banner = ChapterBanner(display.canvas(), "TUTORIÁL")
    check("hra/kapitola", {**column, "Preskočiť": banner.button})

    # Ruky súperov musia byť aspoň z 2/3 na obrazovke.
    for idx, name in ((1, "PC1"), (3, "PC3")):
        cfg = HAND_CONFIGS[idx]
        rect = pygame.Rect(cfg["x"], cfg["y"], ch, 7 * cfg["offset"] + cw)
        vis = rect.clip(pygame.Rect(0, 0, W, H))
        if vis.width * vis.height < 0.66 * rect.width * rect.height:
            problems.append(f"hra: ruka {name} väčšinou mimo obrazovky {rect}")

    ov = screen.info_overlay
    check("pravidlá", {"Zavrieť": ov.btn_close, "Bodovanie": ov.tab_bodovanie,
                       "Pravidlá": ov.tab_pravidla})

    # --- menu ------------------------------------------------------------
    menu = Menu(window, show_continue=True)
    check("menu", {b["label"]: b["rect"] for b in menu.buttons})
    tmenu = TutorialMenu(window, ["zaklady", "zavazky", "trening"])
    check("tutoriál menu", {b["label"]: b["rect"] for b in tmenu.buttons})

    settings = SettingsScreen(window, load_settings())
    group = {"Späť": settings.back_button["rect"],
             "šípka ←": settings.bg_arrow_left["rect"],
             "šípka →": settings.bg_arrow_right["rect"],
             "slider": settings.slider_rect.inflate(20, settings.slider_handle_radius * 3)}
    for name, buttons in settings.ai_buttons.items():
        for btn in buttons:
            group[f"{name}/{btn['difficulty']}"] = btn["rect"]
    for i, rect in enumerate(settings.bg_rects):
        group[f"pozadie {i}"] = rect
    for key, rect in getattr(settings, "tab_rects", {}).items():
        group[f"záložka {key}"] = rect
        for pkey, panel in (("panel AI", settings.panel_ai),):
            if panel.colliderect(rect):
                problems.append(f"nastavenia: {pkey} × záložka {key}")
    for key, panel in (("panel AI", settings.panel_ai),
                       ("panel animácie", settings.panel_anim),
                       ("panel pozadie", settings.panel_bg)):
        if panel.colliderect(settings.back_button["rect"]):
            problems.append(f"nastavenia: {key} × Späť")
        if not pygame.Rect(0, 0, W, H).contains(panel):
            problems.append(f"nastavenia: {key} mimo obrazovky {panel}")
    check("nastavenia", group)

    # Záložka Zobrazenie (režim Okno — vtedy je na nej najviac prvkov)
    settings.active_tab = "zobrazenie"
    settings.pending_windowed = bool(settings.window_sizes)
    group = {"Späť": settings.back_button["rect"],
             "Použiť": settings._apply_rect()}
    for key, rect in settings.tab_rects.items():
        group[f"záložka {key}"] = rect
    for btn in settings.mode_buttons:
        group[btn["label"]] = btn["rect"]
    for btn in settings.size_buttons:
        group["okno %dx%d" % btn["size"]] = btn["rect"]
    panels = [("panel režim", settings.panel_mode)]
    if settings.pending_windowed:
        panels.append(("panel veľkosť", settings.panel_size))
    for key, panel in panels:
        for other in ("Späť", "Použiť"):
            if panel.colliderect(group[other]):
                problems.append(f"zobrazenie: {key} × {other}")
    check("zobrazenie", group)
    check("potvrdenie", {"Ponechať": settings.confirm_keep,
                         "Vrátiť": settings.confirm_revert})

    stats = StatsScreen(window)
    profil = {"meno": stats.name_field,
              "Premenovať": stats.rename_button["rect"],
              "podrobnosti": stats.detail_rect,
              "Späť": stats.back_button["rect"]}
    profil.update({f"dlaždica {k}": r for k, r in stats.tile_rects.items()})
    check("profil", profil)

    go = GameOverScreen(window, game_state.players, [game_state.players[0]],
                        1, game_state)
    check("koniec hry", {"Nová hra": go.btn_new_game, "Menu": go.btn_menu,
                         "Chujogram": go.btn_chujogram})



def main():
    parser = argparse.ArgumentParser(description="Regresný test rozloženia.")
    parser.add_argument("--one", default=None, help="len jedno rozlíšenie (interné)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.one:
        problems = run_one(args.one, args.verbose)
        for p in problems:
            print(f"  {p}")
        sys.exit(1 if problems else 0)

    failed = []
    for res in RESOLUTIONS:
        cmd = [sys.executable, os.path.abspath(__file__), "--one", res]
        if args.verbose:
            cmd.append("--verbose")
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        lines = [ln for ln in proc.stdout.splitlines()
                 if ln.startswith("  ") or args.verbose]
        status = "OK" if proc.returncode == 0 else "CHYBA"
        print(f"[{status}] {res}")
        for ln in lines:
            print(ln)
        if proc.returncode not in (0, 1):
            print(proc.stderr[-2000:])
        if proc.returncode != 0:
            failed.append(res)

    print()
    print("VÝSLEDOK: " + ("všetky rozlíšenia OK" if not failed
                          else f"chyby pri {', '.join(failed)}"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
