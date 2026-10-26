# tutorial_main.py
#
# Samostatný launcher pre testovanie tutoriálu bez zásahu do hlavnej hry
# (rovnaký princíp ako tester_main.py). Zároveň orchestrátor KAPITOL
# tutoriálu — CHAPTERS nižšie je zoznam (id, run_fn) dvojíc, kde každá
# run_fn je samostatne spustiteľná funkcia (vráti "skip"/"menu", pozri
# jej docstring). main.py (podmenu Tutoriál) nad CHAPTERS stavia výber
# "len túto kapitolu na precvičenie" a podľa "skip"/"menu" buď skočí na
# ďalšiu kapitolu, alebo sa vráti do podmenu — main() nižšie je iba
# samostatný spôsob, ako CHAPTERS prejsť (v poradí, od začiatku, bez
# menu vôbec).

# DPI awareness MUSÍ byť nastavená pred importom pygame/config — inak
# Windows nahlási zmenšené "virtualizované" rozlíšenie (napr. 125% scaling
# na notebooku) a gui/display.py by podľa neho zle zvolil rozlíšenie okna
# (rozmazaný obraz, okno väčšie než skutočná plocha).
# Rovnaký guard ako v main.py.
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

import os
import sys

import pygame
from gui.screen import Screen
from gui.game_over_screen import GameOverScreen
from gui.lesson_panel import LessonPanel
from game_setup import load_settings, create_game
from config import DEBUG_MODE, FPS
from tutorial.tutorial_director import TutorialDirector
from tutorial.scripted_ai import ScriptedAI
from tutorial.scripted_round import build_tutorial_game_state
from tutorial.zavazok_director import ZavazokDirector
from tutorial.trening_score_director import TreningScoreDirector
from game.ai import AI
from gui import display
from gui.canvas import draw_backdrop

TRENING_INTRO_TEXT = (
    "Teraz si zahráš naostro!\n\n"
    "V tréningovej hre už rozhoduješ sám. Pomáhať ti bude poradca, "
    "ktorý ti odporučí kartu a vysvetlí, prečo by ju zahral.\n\n"
    "Jeho rady ti môžu pomôcť, no nie vždy musí ísť o najlepší ťah. "
    "Neboj sa preto rozhodovať aj podľa seba!\n\n"
    "Poradcu môžeš kedykoľvek vypnúť."
)


def _show_trening_intro_panel(bg_path: str | None = None) -> None:
    """Krátky úvodný panel (poradca) PRED prvým kolom tréningovej hry.

    ÚMYSELNE samostatná mini-slučka, BEZ gui/screen.py::Screen a BEZ
    diriguenta: Screen vypína automatické rozdanie ďalšieho kola vždy,
    keď má pripojený director (step_frame()::next_round_timer check
    "self.director is None") — to by po prvom kole tréningovej hry
    nechalo stôl stáť navždy (nájdené v hre 2026-10-21). Táto funkcia
    teda nič z reálnej hry nepoužíva, len LessonPanel nad jednoduchým
    pozadím.

    bg_path: cesta k hráčovmu vlastnému "table_bg" (pozri
    run_chapter_trening) — bez neho by draw_backdrop() použil natvrdo
    zadaný default (rovnaký, aký má menu), čo pri reálnej hre pôsobilo
    nepatrične (Nález 2026-10-26). BEZ tmavého overlaya (na rozdiel od
    menu) — v reálnej hre sa stôl takto nikdy celoplošne nestmavuje,
    len samotný LessonPanel má vlastné tlmené pozadie. Panel aj text
    sú vycentrované na stred obrazovky (screen_center/center) — na
    rozdiel od bežných panelov v hre tu nie je žiadna ruka/stôl so
    štichom, ktorému by sa panel musel vyhýbať.

    Pri zatvorení okna (QUIT) počas panela skončí rovnako, ako by
    skončila ktorákoľvek iná obrazovka v hre (pygame.quit() + exit) —
    rovnaký vzor ako gui/tutorial_menu.py::TutorialMenu.run()."""
    # Kreslí sa cez Canvas priamo do okna (rework rozlíšení, krok 5).
    canvas = display.canvas()
    clock = pygame.time.Clock()
    lesson_panel = LessonPanel(canvas)

    while True:
        clock.tick(FPS)
        for event in display.get_events():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and lesson_panel.next_button.collidepoint(event.pos)):
                return

        if bg_path:
            draw_backdrop(canvas, bg_path=bg_path)
        else:
            draw_backdrop(canvas)

        lesson_panel.draw(
            title="Tréningová hra",
            paragraphs=TRENING_INTRO_TEXT,
            button_label="Hraj →",
            center=True,
            screen_center=True,
        )
        display.present()


def run_chapter_zaklady() -> str:
    """Kapitola 1 — plne naskriptovaná ukážka jedného kola (seed 679339).

    Beží na tom istom gui/screen.py::Screen ako ostrá hra aj kapitola 2.
    Scenár (tutorial/tutorial_steps.py) je len dáta; interpretuje ho
    tutorial/tutorial_director.py, ktorého Screen dostane ako nepovinného
    "režiséra". Bez neho je Screen presne tá istá ostrá hra ako predtým.

    Pôvodná verzia (tutorial/tutorial_screen.py, 1150 riadkov samostatného
    enginu, ktorý veľkú časť Screen duplikoval) bola nahradená v septembri
    2026 — pozri claude/07_TUTORIAL_REFACTOR_CATALOG.md (čo všetko robila)
    a claude/08_TUTORIAL_REFACTOR_DESIGN.md (ako a prečo sa to prerobilo).

    Vracia "skip" (tlačidlo Preskočiť v hornom páse, aj prirodzené
    dokončenie poslednej lekcie tlačidlom Dokončiť) alebo "menu" (bežné
    tlačidlo Menu dole) — presne to, čím skončí gui/screen.py::Screen.run()
    (pozri tam self._chapter_exit). main.py podľa toho skáče na ďalšiu
    kapitolu alebo do podmenu Tutoriálu.
    """
    director = TutorialDirector()
    game_state = build_tutorial_game_state(director.first_player_index)

    # Počítače hrajú podľa scenára, nie podľa uváženia. Vysvietenie
    # Počítača 1 nastavuje režisér už pri rozdaní, preto tu (False, False).
    ai_players = [None] + [
        ScriptedAI(game_state.players[i], director)
        for i in range(1, len(game_state.players))
    ]

    settings = dict(load_settings())
    # Tipy patria tréningovej kapitole; tu by sa ich panel vľavo dole bil
    # s panelom výkladu (pozri návrh §7 č. 6).
    settings["tips_enabled"] = False
    # Horný pás s názvom kapitoly a tlačidlom "Preskočiť"
    # (gui/chapter_banner.py). Meníme len túto lokálnu kópiu nastavení —
    # do settings.json sa nič nezapisuje.
    settings["chapter_banner"] = "TUTORIÁL — PRIEBEH KOLA"

    # new_game=False: úvodné kroky (prehľad trestných kariet, ako funguje
    # štich, body Rozdanie/Vysvietenie/Záväzok) sa hrajú nad PRÁZDNYM
    # stolom. Rozdanie spustí až režisér, keď na to dôjde scenár —
    # tlačidlom "Rozdať karty →".
    screen = Screen(game_state, ai_players, debug=DEBUG_MODE,
                    new_game=False, settings=settings, director=director)
    return screen.run()


def run_chapter_zavazky() -> str:
    """Kapitola 2 — Záväzky a špeciálne pravidlá. NA ROZDIEL OD
    kapitoly 1 ide o reálnu, nenaskriptovanú hru: hráč sám skúša
    splniť záväzok (resp. sweep) proti skutočnému AI (game/ai.py::AI,
    "easy"/"hard" — pozri tutorial/zavazok_director.py), bez vedenia
    za ruku. Tri stupne v tomto poradí: "Beriem všetko" (seed 160),
    "Nechytím nič" (5 seedov, zamiešané na začiatku kapitoly) a
    "Lov na trestné karty" (5 seedov). Návrh a overenie — vrátane
    toho, prečo práve tieto seedy — pozri tutorial/zavazok_director.py
    a tutorial2_sandbox/test_zavazok_chapter.py (10/10 headless behov).

    Záväzok sa NEZAMYKÁ — hráč ho vyhlasuje sám, cez bežné tlačidlá
    Beriem všetko/Nechytím nič/OK (fáza "preparation" sa nijako
    nepotláča ani neobchádza, pozri tutorial/zavazok_director.py pre
    detaily). Director len pred touto fázou ukáže panel s výkladom a
    tlačidlá záväzku/OK dočasne schová, kým ho hráč nezavrie. Pri
    zlyhaní ponúkne "Skúsiť znova" (rovnaký stupeň, ďalší seed v
    poradí), pri úspechu "Ďalej"/"Dokončiť".

    Vracia "skip"/"menu" rovnako ako ostatné kapitoly (pozri
    run_chapter_zaklady) — tu sa prakticky vždy vráti "skip"
    (dokončenie všetkých troch stupňov), "menu" len cez bežné tlačidlo
    Menu v hre."""
    director = ZavazokDirector()
    game_state = build_tutorial_game_state(first_player_index=0)

    # Skutočné AI, nie ScriptedAI — na rozdiel od kapitoly 1 tu hráč
    # hraje proti reálnemu rozhodovaniu, nie proti scenáru.
    ai_players = [None] + [
        AI(game_state.players[i], difficulty="easy", logger=game_state.logger)
        for i in range(1, len(game_state.players))
    ]

    settings = dict(load_settings())
    # Tipy by sa bili s panelom výkladu (rovnaký dôvod ako v kapitole 1).
    settings["tips_enabled"] = False
    settings["chapter_banner"] = "TUTORIÁL — ZÁVÄZKY A ŠPECIÁLNE PRAVIDLÁ"

    screen = Screen(game_state, ai_players, debug=DEBUG_MODE,
                    new_game=True, settings=settings, director=director)
    return screen.run()


def run_chapter_trening() -> str:
    """Kapitola 2 — ostrá tréningová hra. ŽIADNE skriptovanie — reálny
    GameState/AI podľa uložených nastavení (rovnaká obtiažnosť ako "Nová
    hra" v hlavnom menu), identické s gui/screen.py::Screen. Beží kým
    hráč neklikne na Menu v hre alebo na Preskočiť v hornom páse (alebo
    nezavrie okno), s možnosťou "Hraj znova" cez GameOverScreen po
    prekročení 100 bodov.

    Vracia "skip"/"menu" presne podľa toho, ktorým tlačidlom hráč odišiel
    (main.py podľa toho skáče na ďalšiu kapitolu alebo do podmenu
    Tutoriálu) — po Game Over vždy "menu" (Preskočiť už niet kam, kolo je
    dohraté).

    Jediný rozdiel oproti ostrej hre: tipy od AI sú tu zapnuté. Pred
    PRVÝM kolom tejto návštevy kapitoly sa navyše ukáže krátky úvodný
    panel vysvetľujúci poradcu (_show_trening_intro_panel() vyššie) —
    pri "Hraj znova" po Game Over sa už nezobrazí.

    Panel je ZÁMERNE samostatná slučka BEZ diriguenta na Screen —
    pripojenie diriguenta (čo i len na úvodnú obrazovku) vypína
    automatické rozdanie ďalšieho kola na celú reláciu (pozri
    gui/screen.py::step_frame()::next_round_timer) a tréning by po
    prvom kole zamrzol. (Nájdené v hre 2026-10-21.)

    Samotná hra MÁ diriguenta (tutorial/trening_score_director.py::
    TreningScoreDirector) — na rozdiel od úvodného panela si ale ten
    sám preberá spúšťanie ďalšieho kola (pozri jeho hlavu súboru), takže
    sa vyššie spomínaný bug nemôže zopakovať. Zobrazuje jednorazové
    vysvetlenia pravidiel "90b" a "reset na 100b". Nová instancia na
    každé "Hraj znova" (nový while cyklus nižšie) — vysvetlenia sa tak
    môžu zobraziť znova v novej hre."""
    settings = dict(load_settings())

    # Pozadie úvodného panelu = hráčovo vlastné "table_bg" (rovnaká
    # cesta ako gui/screen.py::Screen.__init__), nech panel vyzerá ako
    # súčasť reálnej hry, nie ako menu (Nález 2026-10-26).
    bg_file = settings.get("table_bg", "table.jpg")
    bg_path = os.path.join("assets", "graphics", bg_file)
    _show_trening_intro_panel(bg_path=bg_path if os.path.exists(bg_path) else None)

    # Tipy chceme v tréningovej kapitole vždy, bez ohľadu na to, ako ich
    # má hráč nastavené v ostrej hre. Meníme len túto lokálnu kópiu — do
    # settings.json sa nič nezapisuje (prepnutie tlačidlom priamo v hre
    # áno, to je vedomá voľba hráča).
    settings["tips_enabled"] = True
    # Horný pás dáva najavo, že nejde o ostrú hru, a ponúka odchod ďalej,
    # keby hráča tréning omrzel (gui/chapter_banner.py). Tá istá
    # komponenta ako v kapitole 1.
    settings["chapter_banner"] = "TRÉNINGOVÁ HRA"
    while True:
        game_state, ai_players = create_game(settings)
        director = TreningScoreDirector()
        screen = Screen(game_state, ai_players, debug=DEBUG_MODE,
                        settings=settings, director=director)
        result = screen.run()

        if result == "game_over":
            if game_state.loser is not None:
                game_over = GameOverScreen(
                    screen.screen,
                    game_state.players,
                    game_state.loser,
                    game_state.round_number,
                    game_state,
                )
                next_action = game_over.run()
                if next_action == "new_game":
                    continue
            # GameOverScreen vracia len "menu"/"new_game" (ošetrené
            # vyššie) — kolo je dohraté, Preskočiť už niet kam.
            return "menu"

        # "skip" (Preskočiť/prirodzené dokončenie) alebo "menu" (tlačidlo
        # Menu v hre) — presne to, čím Screen.run() skončil.
        return result


CHAPTERS = [
    ("zaklady", run_chapter_zaklady),
    ("zavazky", run_chapter_zavazky),
    ("trening", run_chapter_trening),
]


def main():
    for _chapter_id, run_chapter in CHAPTERS:
        action = run_chapter()
        if action == "quit":
            break
    pygame.quit()


if __name__ == "__main__":
    main()
