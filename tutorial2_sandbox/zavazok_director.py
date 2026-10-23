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
# Výsledok kola (úspech/zlyhanie) sa číta z Player.declaration_fulfilled
# — ten nastavuje game/player.py::finalize_round() (úspech aj zlyhanie
# "all", úspech "none"); pri zlyhaní "none" ostáva na svojej pôvodnej
# hodnote False z reset_round() (score_round() tam pripočíta penalizáciu
# priamo, finalize_round() sa pre tento prípad nevolá). Pri žiadnom
# záväzku (hráč len klikne OK bez výberu) ostáva tiež False — číta sa
# to teda rovnako bez ohľadu na to, čo presne hráč v príprave zvolil.

import random

from game.deck import Deck
from gui.lesson_panel import LessonPanel
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
]


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
        # "done" (kolo skončilo, panel s výsledkom)
        self.ui_state = "intro"
        self.last_result = None  # None | "success" | "fail"

        self.screen = None
        self.lesson_panel = None

    # ------------------------------------------------------------------
    # Pripojenie k Screen (Screen.__init__, na konci)
    # ------------------------------------------------------------------

    def attach(self, screen):
        self.screen = screen
        self.lesson_panel = LessonPanel(screen.screen)

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
            self.last_result = ("success" if human.declaration_fulfilled
                                else "fail")
            self.ui_state = "done"

    def is_paused(self) -> bool:
        # Počas úvodného panelu stojí hra — AI nehrajú, kým hráč
        # neklikne "Hraj →" a neuvidí tlačidlá záväzku. Počas "prep" aj
        # "playing" ide o bežnú hru (príprava aj štichy), AI tam hrajú
        # normálne. Po konci kola (ui_state == "done") je kolo aj tak
        # dohraté, is_paused tam nemá na čom pracovať.
        return self.ui_state == "intro"

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
            )

    def shows(self, element: str) -> bool:
        # Tlačidlá záväzku a OK sa objavia až keď hráč zavrie úvodný
        # panel (ui_state == "intro" → schované) — predtým by sa dalo
        # kliknúť OK skôr, než si prečíta, čo sa od neho čaká.
        if self.ui_state == "intro" and element in ("declaration", "ok"):
            return False
        return True

    def suppress_declaration(self) -> bool:
        # Záväzok sa NEPOTLÁČA — hráč ho v tejto kapitole vyhlasuje
        # sám, rovnakými tlačidlami ako v ostrej hre.
        return False
