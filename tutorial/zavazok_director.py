# tutorial/zavazok_director.py
#
# Kapitola "Záväzok" (medzi "Základy" a "Tréningová hra" v
# tutorial_main.py::CHAPTERS). Na rozdiel od kapitoly 1 (tutorial/
# tutorial_director.py) ide o REÁLNU, nenaskriptovanú hru — hráč sám
# skúša splniť záväzok proti skutočnému AI (game/ai.py::AI, "easy"),
# bez vedenia za ruku. Návrh a overenie prebehlo v testovacom
# priečinku tutorial2_sandbox/ — pozri tutorial2_sandbox/
# test_zavazok_chapter.py (jednorazové nástroje na výber seedov
# nižšie, find_all_seeds.py/find_none_seeds.py, splnili svoj účel a
# boli odstránené 2026-10-21).
#
# Poradie a obsah (odsúhlasené v konverzácii):
#   1. "Beriem všetko" — seed 160 (hráč drží eso+kráľa v troch farbách,
#      v štvrtej je void — žiadna diera, kde by naňho súperi čakali so
#      schovanou vyššou kartou).
#   2. "Nechytím nič" — 5 seedov (330, 491, 1386, 1481, 1615), všetky
#      podľa game/ai_declaration.py::DeclarationAdvisor._can_take_none()
#      bezpečné (risk<=0); zamiešané raz na začiatku kapitoly, pri
#      opakovaní sa ide podľa tohto poradia. Seed 1386 je zámerne
#      ponechaný aj keď je citeľne krehkejší než ostatné štyri — dáva
#      hráčovi šancu okúsiť aj prehru, nielen úspech.
#   3. "Lov na trestné karty" (sweep) — 5 seedov (2185, 2733, 3695, 4629,
#      5435), vybrané z kandidátov vygenerovaných simuláciou 4x "hard"
#      AI (vrátane sedadla 0), kde sedadlo 0 skutočne dosiahne TICHÝ
#      sweep (zobral všetky trestné karty, bez vyhláseného záväzku).
#      Na rozdiel od stupňov 1-2 tu "declaration" je None — hráč sa
#      nerozhoduje vopred tlačidlom, len si má všimnúť príležitosť v
#      priebehu hry. Úspech sa preto nečíta z declaration_fulfilled
#      (pozri update() nižšie), ale z round_flags["sweep"]
#      (game/player.py::finalize_round(), vetva bez aktívneho záväzku).
#
# DÔLEŽITÉ (rozhodnutie v konverzácii): záväzok sa NEZAMYKÁ programovo.
# Hráč klikne na "Beriem všetko"/"Nechytím nič" a "OK" sám, úplne
# rovnakou cestou ako v ostrej hre — fáza "preparation" (gui/
# preparation_handler.py) sa nijako nepotláča (suppress_declaration()
# vracia False) ani neobchádza. Director len PRED touto fázou (po
# rozdaní, pred "OK"/tlačidlami záväzku) ukáže panel s výkladom, čo
# tento stupeň od hráča chce, a tlačidlá záväzku/OK schová, kým panel
# nezavrie — potom je voľba úplne na ňom. Ak si schválne (alebo
# omylom) vyberie iný záväzok, než ktorý stupeň navrhuje, alebo žiadny,
# nemá so seedom pripraveným pre ten druhý typ reálnu šancu uspieť —
# jednoducho to zlyhá a dostane "Skús znova", presne ako pri bežnom
# zlyhaní. Žiadne špeciálne rozlišovanie "správny vs. nesprávny výber"
# v kóde nie je potrebné.
#
# Výsledok kola (úspech/zlyhanie) sa pre stupne 1-2 číta z
# Player.declaration_fulfilled — ten nastavuje game/player.py::
# finalize_round() (úspech aj zlyhanie "all", úspech "none"); pri
# zlyhaní "none" ostáva na svojej pôvodnej hodnote False z
# reset_round() (score_round() tam pripočíta penalizáciu priamo,
# finalize_round() sa pre tento prípad nevolá). Pri žiadnom záväzku
# (hráč len klikne OK bez výberu) ostáva tiež False — číta sa to teda
# rovnako bez ohľadu na to, čo presne hráč v príprave zvolil.
#
# Stupeň 3 ("declaration" is None) nemá žiadny záväzok vyhlásený, takže
# declaration_fulfilled tu zostáva False bez ohľadu na výsledok — jeho
# úspech sa číta z Player.round_flags["sweep"] (nastavuje finalize_round()
# vo vetve bez aktívneho záväzku, keď all_penalty_taken=True).

import random

from game.deck import Deck
from gui.lesson_panel import LessonPanel, chujogram_offset
from tutorial.scripted_round import apply_scripted_deal

STAGES = [
    {
        "declaration": "all",
        "seeds": [160],
        "title": "Záväzok: Beriem všetko",
        "intro": (
            "Vyhlásením tohto záväzku sa pokúsiš získať všetkých 8 "
            "štichov. Ak uspeješ, odpočíta sa ti 20 bodov. Ak však "
            "prehráš čo i len jeden štich, pripíše sa ti 20 trestných "
            "bodov.\n\n"
            "Keď vyhlásiš záväzok, prvý štich začínaš ty — bez ohľadu "
            "na to, kto mal pôvodne začínať. Pri záväzku môžeš začať "
            "aj srdcovou kartou."
        ),
        "success_text": (
            "Záväzok splnený!\n\n"
            "Získal si všetkých 8 štichov a zo skóre sa ti odpočíta "
            "20 bodov. Ostatní hráči za toto kolo nezískajú žiadne "
            "trestné body."
        ),
        "fail_text": (
            "Záväzok nesplnený!\n\n"
            "Stratil si jeden zo štichov, takže záväzok \"Beriem "
            "všetko\" sa ti nepodarilo splniť.\n\n"
            "Skús to znova! Rozdanie zostáva rovnaké — tentoraz sa "
            "pokús vyhrať všetkých 8 štichov."
        ),
    },
    {
        "declaration": "none",
        "seeds": [330, 491, 1386, 1481, 1615],
        "title": "Záväzok: Nechytím nič",
        "intro": (
            "Vyhlásením tohto záväzku sa pokúsiš odohrať celé kolo "
            "bez získania jediného štichu. Ak uspeješ, odpočíta sa ti "
            "10 bodov. Ak však získaš čo i len jeden štich, pripíše "
            "sa ti 10 trestných bodov.\n\n"
            "Keď vyhlásiš záväzok, prvý štich začínaš ty — bez ohľadu "
            "na to, kto mal pôvodne začínať. Pri záväzku môžeš začať "
            "aj srdcovou kartou."
        ),
        "success_text": (
            "Záväzok splnený!\n\n"
            "Odohral si všetkých 8 štichov bez toho, aby si niektorý "
            "získal. Zo skóre sa ti odpočíta 10 bodov. Ostatní hráči "
            "za toto kolo nezískajú žiadne trestné body."
        ),
        "fail_text": (
            "Záväzok nesplnený!\n\n"
            "Získal si štich, takže záväzok \"Nechytím nič\" sa ti "
            "nepodarilo splniť.\n\n"
            "Skús to znova! Rozdanie zostáva rovnaké — tentoraz sa "
            "pokús vyhnúť všetkým štichom."
        ),
    },
    {
        "declaration": None,
        "seeds": [2185, 2733, 3695, 4629, 5435],
        "title": "Lov na trestné karty",
        "intro": (
            "Niekedy sa oplatí ísť proti hlavnému cieľu hry a pokúsiť sa "
            "získať všetky trestné karty v jednom kole. Ak sa ti to "
            "podarí, namiesto trestných bodov získaš bonus −10 bodov!\n\n"
            "Na rozdiel od záväzkov nemusíš nič vyhlasovať. Stačí využiť "
            "vhodnú príležitosť počas hry.\n\n"
            "Pamätaj, nemusíš vyhrať všetky štichy – stačí pozbierať "
            "všetky trestné karty."
        ),
        "success_text": (
            "Všetky trestné karty sú tvoje!\n\n"
            "Podarilo sa ti ich pozbierať všetky, takže sa ti zo skóre "
            "odpočíta 10 bodov."
        ),
        "fail_text": (
            "Tentoraz to nevyšlo!\n\n"
            "Niektorú z trestných kariet získal súper, takže sa body "
            "počítajú podľa bežných pravidiel.\n\n"
            "Skús to znova a pokús sa pozbierať všetky trestné karty!"
        ),
    },
]

OUTRO_TITLE = "Kapitola dokončená!"
OUTRO_TEXT = (
    "Prešiel si všetky tri situácie, ktoré môžu nastať v bežnej hre: "
    "záväzky \"Beriem všetko\" a \"Nechytím nič\" aj lov na trestné "
    "karty.\n\n"
    "Ak si niekedy nebudeš istý pravidlami, stačí počas hry kliknúť "
    "na tlačidlo \"Pravidlá\" — kedykoľvek si môžeš všetko zopakovať."
)
OUTRO_BUTTON = "Dokončiť"


class ZavazokDirector:
    """Pozri hlavu súboru. Kontrakt Screen<->director (attach/update/
    is_paused/handle_click/restrict_playable/draw/shows/
    suppress_declaration) je rovnaký, aký používa aj tutorial/
    tutorial_director.py::TutorialDirector — Screen ani jedna z
    produkčných ciest (ostrá hra, tréning, kapitola 1) sa tu nemenila."""

    def __init__(self, stages=None):
        self.stages = [dict(s) for s in (stages or STAGES)]
        for stage in self.stages:
            stage["seeds"] = list(stage["seeds"])
        # Stupeň s viac než jedným seedom ("Nechytím nič") sa raz na
        # začiatku kapitoly zamieša — pri opakovaní sa ide podľa tohto
        # (teraz už pevného) poradia.
        for stage in self.stages:
            random.shuffle(stage["seeds"])

        self.stage_index = 0
        self.attempt_index = [0] * len(self.stages)
        # "intro" (panel s výkladom, tlačidlá záväzku/OK schované) |
        # "prep" (hráč sám vyberá záväzok a klika OK — bežná fáza
        # "preparation") | "playing" (reálna hra, fáza "tricks") |
        # "done" (kolo skončilo, panel s výsledkom) | "outro" (len po
        # úspechu POSLEDNÉHO stupňa — záverečný panel s pripomienkou
        # tlačidla "Pravidlá", pred skutočným odchodom z kapitoly)
        self.ui_state = "intro"
        self.last_result = None  # None | "success" | "fail"

        self.screen = None
        self.lesson_panel = None

    # ------------------------------------------------------------------
    # Pripojenie k Screen (Screen.__init__, na konci)
    # ------------------------------------------------------------------

    def attach(self, screen):
        self.screen = screen
        self.lesson_panel = LessonPanel(screen.canvas)

    @property
    def current_stage(self) -> dict:
        return self.stages[self.stage_index]

    @property
    def current_seed(self) -> int:
        stage = self.current_stage
        return stage["seeds"][self.attempt_index[self.stage_index]
                              % len(stage["seeds"])]

    # ------------------------------------------------------------------
    # Štart kola (Screen._start_round, PRED pamäťou AI)
    # ------------------------------------------------------------------

    def setup_round(self):
        seed = self.current_seed
        game_state = self.screen.game_state

        hands, used_seed = Deck().deal(seed=seed)
        assert used_seed == seed
        apply_scripted_deal(game_state, hands, deal_seed=seed,
                            illuminations=())
        # Žiadny priamy zásah do záväzku/prípravy — kolo ostáva vo
        # fáze "preparation", presne ako po rozdaní v ostrej hre.
        # Hráč sám vyhlási (alebo nevyhlási) záväzok cez bežné
        # tlačidlá a "OK" (gui/preparation_handler.py), ktoré sa
        # objavia, hneď ako zavrie úvodný panel (pozri shows()).

        # Titulkový pás (gui/chapter_banner.py) ukazuje názov AKTUÁLNEHO
        # stupňa, nie celej kapitoly — nastavené tu, PRED prvým draw()
        # tohto kola, takže sa nikdy nezablysne stará hodnota.
        if self.screen.chapter_banner is not None:
            label = self.current_stage["title"].removeprefix("Záväzok: ")
            self.screen.chapter_banner.title = f"TUTORIÁL — {label.upper()}"

        self.ui_state = "intro"
        self.last_result = None

    # ------------------------------------------------------------------
    # Priebeh
    # ------------------------------------------------------------------

    def update(self):
        rnd = self.screen.game_state.current_round
        if rnd is None:
            return

        if self.ui_state == "prep":
            if rnd.phase != "preparation":
                # Hráč klikol OK — gui/preparation_handler.py::
                # confirm_preparation() už spracoval záväzok a
                # vysvietenie a spustil štichy (finish_preparation()).
                self.ui_state = "playing"
            return

        if self.ui_state == "playing" and rnd.phase == "done":
            human = self.screen.game_state.players[
                self.screen.game_state.human_index]
            if self.current_stage["declaration"] is None:
                # Stupeň "sweep" — bez vyhláseného záväzku zostáva
                # declaration_fulfilled vždy False, úspech sa číta z
                # round_flags["sweep"] (pozri hlavu súboru).
                success = bool(human.round_flags.get("sweep"))
            else:
                success = human.declaration_fulfilled
            self.last_result = "success" if success else "fail"
            self.ui_state = "done"

    def is_paused(self) -> bool:
        # Počas úvodného panelu stojí hra — AI nehrajú, kým hráč
        # neklikne "Hraj →" a neuvidí tlačidlá záväzku. Počas "prep" aj
        # "playing" ide o bežnú hru (príprava aj štichy), AI tam hrajú
        # normálne. Po konci kola (ui_state == "done") je kolo aj tak
        # dohraté, is_paused tam nemá na čom pracovať. "outro" je tiež
        # len statický panel po úplnom konci kapitoly.
        return self.ui_state in ("intro", "outro")

    def handle_click(self, pos) -> bool:
        if self.ui_state == "intro":
            if self.lesson_panel.next_button.collidepoint(pos):
                self.ui_state = "prep"
                return True
            return False

        if self.ui_state == "done":
            if not self.lesson_panel.next_button.collidepoint(pos):
                return False
            if self.last_result == "fail":
                self.attempt_index[self.stage_index] += 1
                self.screen._start_round()
            else:
                if self.stage_index + 1 < len(self.stages):
                    self.stage_index += 1
                    self.screen._start_round()
                else:
                    # Posledný stupeň splnený — ešte pred odchodom z
                    # kapitoly ukážeme záverečný panel s pripomienkou
                    # tlačidla "Pravidlá" (pozri OUTRO_TITLE/OUTRO_TEXT).
                    self.ui_state = "outro"
            return True

        if self.ui_state == "outro":
            if not self.lesson_panel.next_button.collidepoint(pos):
                return False
            self.screen._chapter_exit = "skip"
            self.screen.running = False
            return True

        # "prep" a "playing" — bežné klikanie (tlačidlá záväzku/OK,
        # karty v štichu); director sa do toho nemieša.
        return False

    def restrict_playable(self, playable):
        return playable

    def draw(self):
        if self.screen.dealing:
            return
        stage = self.current_stage

        if self.ui_state == "intro":
            self.lesson_panel.draw(
                title=stage["title"],
                paragraphs=stage["intro"],
                button_label="Hraj →",
                x_offset=chujogram_offset(self.screen),
            )
        elif self.ui_state == "done":
            if self.last_result == "success":
                text = stage["success_text"]
                button = ("Ďalej →"
                          if self.stage_index + 1 < len(self.stages)
                          else "Dokončiť")
            else:
                text = stage["fail_text"]
                button = "Skúsiť znova"
            self.lesson_panel.draw(
                title=stage["title"],
                paragraphs=text,
                button_label=button,
                x_offset=chujogram_offset(self.screen),
            )
        elif self.ui_state == "outro":
            self.lesson_panel.draw(
                title=OUTRO_TITLE,
                paragraphs=OUTRO_TEXT,
                button_label=OUTRO_BUTTON,
                center=True,
                x_offset=chujogram_offset(self.screen),
            )

    def shows(self, element: str) -> bool:
        # Tlačidlá záväzku a OK sa objavia až keď hráč zavrie úvodný
        # panel (ui_state == "intro" → schované) — predtým by sa dalo
        # kliknúť OK skôr, než si prečíta, čo sa od neho čaká.
        if self.ui_state == "intro" and element in ("declaration", "ok"):
            return False
        if element == "tips":
            # Tipy sú úloha tréningovej kapitoly (rovnaký dôvod ako v
            # tutorial/tutorial_director.py::shows() — bili by sa s
            # panelom výkladu, pozri komentár pri settings["tips_enabled"]
            # v tutorial_main.py::run_chapter_zavazky()). BEZ tohto
            # vracania False bolo tlačidlo "Tipy: ZAP/VYP" v tejto
            # kapitole viditeľné a klikateľné, a Screen._save_tips_setting()
            # by pri kliku ZAPÍSALA tipy do ZDIEĽANÉHO settings.json —
            # tichá zmena nastavenia OSTREJ hry len za kliknutie v
            # tutoriáli (Nález 2026-10-26, pri audite kolízií
            # tutoriál/ostrá hra).
            return False
        return True

    def suppress_declaration(self) -> bool:
        # Záväzok sa NEPOTLÁČA — hráč ho v tejto kapitole vyhlasuje
        # sám, rovnakými tlačidlami ako v ostrej hre.
        return False

    def blink(self, element: str) -> bool:
        """Pripomienka pre gui/phase_renderer.py (generický hák, pozri
        PhaseRenderer._blink). Kľúče:
        - "decl_all"/"decl_none" — kým hráč v stupni "all"/"none" ešte
          nevybral záväzok, pulzuje tlačidlo, ktoré k nemu patrí.
          Zmizne hneď po výbere ktoréhokoľvek tlačidla (aj iného, než
          ponúkané — výber ostáva na hráčovi, pozri hlavu súboru).
        - "ok" — v stupni "sweep" (declaration is None) hráč nemá čo
          vyhlasovať, takže namiesto tlačidla záväzku bliká OK, kým ho
          nestlačí. V stupňoch "all"/"none" OK nikdy nebliká (tam sa
          má kliknúť najprv na záväzok).
        - "info" — počas záverečného panelu ("outro") bliká tlačidlo
          "Pravidlá", na ktoré panel práve upozorňuje."""
        if element == "info":
            return self.ui_state == "outro"
        if self.ui_state != "prep" or self.screen.active_declaration is not None:
            return False
        declaration = self.current_stage["declaration"]
        if element in ("decl_all", "decl_none"):
            if declaration not in ("all", "none"):
                return False
            target = "decl_all" if declaration == "all" else "decl_none"
            return element == target
        if element == "ok":
            return declaration is None
        return False
