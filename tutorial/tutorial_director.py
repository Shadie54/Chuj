# tutorial/tutorial_director.py
#
# Režisér naskriptovanej kapitoly tutoriálu — nepovinný spolupracovník
# gui/screen.py::Screen (parameter director). Bez neho je Screen presne
# tá istá ostrá hra ako predtým; s ním beží naskriptovaná lekcia.
#
# STAV: etapa 2 refaktoru — kostra. Režisér zatiaľ NEKRESLÍ výklad,
# NEPAUZUJE a NEODHAĽUJE UI postupne (shows() vracia všade True,
# is_paused() vracia False, draw() nerobí nič). Jeho jedinou úlohou je
# zatiaľ dokázať, že naskriptované kolo prebehne na reálnom Screen od
# rozdania po skórovanie: podstrčí pevné rozdanie, kŕmi ScriptedAI
# kartami zo scenára a hráčovi zúži voľbu na to, čo scenár ponúka.
# Kroky, texty a pauzy pribudnú v etape 4.
#
# Pozri claude/08_TUTORIAL_REFACTOR_DESIGN.md (§3 architektúra,
# §10 etapy) a claude/07_TUTORIAL_REFACTOR_CATALOG.md (čo všetko musí
# nakoniec vedieť).

import pygame

from config import (
    BUTTON_RADIUS, CARD_SIZE_MEDIUM, COLOR_BUTTON_PRIMARY, COLOR_GOLD,
    COLOR_GRAY, COLOR_PANEL_BG, COLOR_WHITE,
    SCREEN_WIDTH, TABLE_CENTER_X, TABLE_CENTER_Y,
)
from game.card import Card
from gui.lesson_panel import LessonPanel, PANEL_LEFT, PANEL_TOP, BUTTON_H
from tutorial.scripted_round import apply_scripted_deal
from tutorial.tutorial_steps import (
    STEPS, BRANCH_B_STEPS, build_tutorial_hands,
)

# Ruky pochádzajú zo skutočnej hry so seedom 679339 (pozri docstring
# build_tutorial_hands). Ukazujeme ho v paneli KOLO namiesto seedu
# náhodného rozdania, ktoré pri štarte zahadzujeme — ten by rozdanie
# nereprodukoval.
TUTORIAL_DEAL_SEED = 679339

# Poradie štichov v scenári. Index v tomto zozname = Round.trick_number.
TRICK_KEYS = (
    "trick1", "trick2", "trick3", "trick4",
    "trick5", "trick6", "trick7", "trick8",
)


class TutorialDirector:
    """Riadi naskriptovanú kapitolu nad reálnym Screen."""

    # --- animácia "čo je štich" (krok "trick_demo") --------------------
    # 4 ľubovoľné karty, len na ukážku — zámerne iné ako prvá skutočná
    # karta neskôr v scenári (acorn/under), nech ich hráč s ňou nezamieňa.
    _DEMO_CARDS = (
        Card("heart", "ace"),
        Card("bell", "king"),
        Card("leaf", "nine"),
        Card("acorn", "ten"),
    )
    _DEMO_GAP = 30                 # medzera medzi kartami v rade
    # Časovanie — o 50% pomalšie oproti pôvodnému (všetky hodnoty ×2), nech
    # animácia pôsobí pokojnejšie, menej rušivo.
    _DEMO_APPEAR_STEP_MS = 700    # odstup medzi objavením kariet
    _DEMO_APPEAR_FADE_MS = 500    # ako dlho trvá nafarbenie jednej karty
    _DEMO_APPEAR_END_MS = 3 * _DEMO_APPEAR_STEP_MS + _DEMO_APPEAR_FADE_MS
    _DEMO_HOLD_MS = 1400          # pauza, keď sú vidno všetky 4
    _DEMO_COLLECT_MS = 1000       # "zobratie" — zbalia sa k stredu a zmiznú
    _DEMO_PAUSE_MS = 1000         # prázdna pauza pred ďalším opakovaním
    _DEMO_CYCLE_MS = (_DEMO_APPEAR_END_MS + _DEMO_HOLD_MS
                      + _DEMO_COLLECT_MS + _DEMO_PAUSE_MS)

    # Počas kroku "trick_demo" banner hovorí "ÚVOD" namiesto bežného
    # "PRIEBEH KOLA" zo settings — ešte sa totiž nehrá žiadne kolo.
    # TODO: znenie overiť — pozri _sync_banner_title().
    _INTRO_BANNER_TITLE = "TUTORIÁL — ÚVOD"

    def __init__(self):
        self.screen = None
        self.lesson_panel: LessonPanel | None = None
        # Čím sa kapitola skončí pre tutorial_main.py::CHAPTERS:
        # "advance" (pokračuj ďalšou kapitolou) alebo "quit".
        self.exit_action: str = "advance"
        self._steps_by_key = {s["key"]: s for s in STEPS if "key" in s}
        # Chybu v dynamickom texte scenára nahlásime len raz, nech
        # nezaplaví konzolu 60× za sekundu.
        self._text_error_logged = False
        self._playable_error_logged = False

        # --- stav krokovania -------------------------------------------
        self.step_index: int = 0
        self.phase_index: int = 0       # bod v rámci kroku "phase_list"
        self.finished: bool = False

        # Latche "hráč to už raz vyskúšal". Zámerne sa nikdy nevracajú na
        # False — stačí vyskúšať raz (rovnako ako v pôvodnom tutoriáli).
        self.illumination_interacted: bool = False
        self.last_trick_viewed: bool = False
        self.chujogram_opened: bool = False

        # Postupné odhaľovanie UI (pozri shows()). Hráč nemá pred sebou od
        # prvej sekundy celé rozhranie — každý prvok sa objaví až v kroku,
        # ktorý o ňom hovorí.
        self.show_round_status: bool = False
        self.chujogram_revealed: bool = False

        # Číslo štichu, pre ktorý hráč už klikol "Ďalej" — dovtedy je
        # dokončený štich zmrazený na stole aj s výkladom.
        self._released_trick: int | None = None
        self._last_trick_number: int = 0
        self._deal_requested: bool = False

        # Časová základňa animácie kroku "trick_demo" — nastaví sa pri
        # prvom vykreslení, animácia odvtedy beží v slučke (pozri
        # _draw_trick_demo()).
        self._demo_start_time: int | None = None

    # ------------------------------------------------------------------
    # Prepojenie so Screen
    # ------------------------------------------------------------------

    def attach(self, screen):
        """Volá Screen na konci svojho __init__."""
        self.screen = screen
        self.lesson_panel = LessonPanel(screen.screen)
        # Pôvodný názov bannera zo settings — _sync_banner_title() sa naň
        # vracia mimo kroku "trick_demo".
        self._default_banner_title = screen.settings.get("chapter_banner")

    @property
    def first_player_index(self) -> int:
        """Kto začína prvý štich — odvodené zo scenára, nie natvrdo, nech
        to sedí aj keď sa scenár prepíše."""
        pre = self._steps_by_key["trick1"].get("pre_human") or []
        return pre[0][0] if pre else 0

    # ------------------------------------------------------------------
    # Háky, ktoré volá Screen
    # ------------------------------------------------------------------

    def setup_round(self):
        """Podstrčí pevné rozdanie hneď po GameState.start_new_round()."""
        apply_scripted_deal(
            self.screen.game_state,
            build_tutorial_hands(),
            deal_seed=TUTORIAL_DEAL_SEED,
            # Počítač 1 má zeleného horníka vysvieteného od začiatku —
            # zámerná odchýlka od pôvodnej hry, aby sa dalo naživo ukázať,
            # čo znamená mať vysvietených oboch horníkov. Musí to byť už
            # tu, nie až v prípravnej fáze: inak by ho počas výkladu ešte
            # nebolo vidno (pozri návrh §7 č. 5).
            illuminations=[(1, True, False)],
        )

    def update(self):
        """
        Volá Screen každú snímku. Režisér tu sleduje herný stav a podľa
        neho posúva kroky — namiesto toho, aby mu Screen o každej
        udalosti hlásil hákom (pozri návrh §3.2).
        """
        if self.screen is None:
            return

        # Latche: hráč si otvoril posledný štich / siahol na horníka /
        # otvoril Chujogram.
        if self.screen.show_last_trick:
            self.last_trick_viewed = True
        if self.screen.selected_illumination:
            self.illumination_interacted = True
        if getattr(self.screen.chujogram, "visible", False):
            self.chujogram_opened = True

        rnd = self._round()

        # Rozdanie dobehlo -> len zrušíme príznak čakania na animáciu.
        # Bod "Rozdanie" ostáva aktívny ešte ďalej (panel_content() v ňom
        # od tejto chvíle ukazuje "ako štich funguje" namiesto pôvodného
        # textu) — na "Vysvietenie" sa posunie až explicitným klikom na
        # "Ďalej" cez handle_click(), nie automaticky.
        if self._deal_requested and rnd is not None and not self.screen.dealing:
            self._deal_requested = False

        # Hráč potvrdil prípravu tlačidlom OK (kolo prešlo do štichov) ->
        # krok "phase_list" tým končí.
        if (rnd is not None and rnd.phase == "tricks"
                and self._step_kind() == "phase_list"):
            self._enter_step(self.step_index + 1)

        # Štich sa uzavrel -> ďalší krok scenára.
        if rnd is not None and rnd.trick_number != self._last_trick_number:
            self._last_trick_number = rnd.trick_number
            self._released_trick = None
            self._enter_step(self.step_index + 1)

        # Krok "chujogram_wait" čaká, kým hráč Chujogram naozaj otvorí.
        step = self.current_step()
        if (step is not None and step.get("key") == "chujogram_wait"
                and self.chujogram_opened):
            self._enter_step(self.step_index + 1)

    def is_paused(self) -> bool:
        """
        Má sa hra zastaviť a čakať na hráča?

        Zastavuje sa vždy, keď aktuálny krok nie je štich (hráč si číta
        výklad), a pri kroku "štich" vtedy, keď už všetky štyri karty
        padli — vtedy sa ukáže text_after a čaká sa na "Ďalej", ktoré
        spustí zber štichu k víťazovi.
        """
        if self.screen is None:
            return False
        step = self.current_step()
        if step is None:
            return True
        if step["kind"] != "trick":
            return True
        rnd = self._round()
        if rnd is None:
            return True

        # Krok scenára sa posúva až v update(), teda o snímku po tom, čo
        # Round uzavrel štich. V tej medzere už beží NOVÝ štich, ale krok
        # ešte ukazuje ten predošlý — a keby sa vtedy hralo, hráč by mohol
        # zahrať kartu do štichu, o ktorom sa ešte len ide hovoriť
        # (restrict_playable by pýtala možnosti nesprávneho kroku).
        # Kým sa krok nezrovná so štichom, stojíme.
        if self.step_for_trick(rnd.trick_number) is not step:
            return True

        if self._released_trick == rnd.trick_number:
            return False
        trick = rnd.current_trick
        return trick is not None and trick.is_complete

    def shows(self, element: str) -> bool:
        """
        Postupné odhaľovanie UI.

        Hráč nemá pred sebou od prvej sekundy celé rozhranie — každý prvok
        sa objaví až v kroku, ktorý o ňom hovorí. Zodpovedá to pôvodnému
        tutoriálu, ktorý tieto prvky jednoducho nekreslil, kým nemali byť
        vidno.

        Tlačidlá prípravy ("Beriem všetko", "Nechytím nič", OK) patria
        výhradne bodu "Záväzok" — inak by hráč mohol prípravu potvrdiť už
        pri bode "Vysvietenie" a preskočiť tým časť výkladu.

        "Posledný štich" nestrážime: Screen ho sám kreslí až keď je nejaký
        odohratý štich (trick_number > 0), čo je presne to isté pravidlo,
        aké mal pôvodný tutoriál.
        """
        if element in ("ok", "declaration"):
            step = self.current_step()
            if step is None or step["kind"] != "phase_list":
                return False
            return step["phases"][self.phase_index]["key"] == "zavazok"
        if element == "round_status":
            return self.show_round_status
        if element == "chujogram":
            return self.chujogram_revealed
        if element == "tips":
            # Tipy sú úloha tréningovej kapitoly. Navyše by sa ich panel
            # vľavo dole bil s panelom výkladu (návrh §7 č. 6).
            return False
        if element == "player_labels":
            # V oboch úvodných, vycentrovaných krokoch ("trick_demo" aj
            # "penalty_overview") menovky hráčov nemajú čo ukazovať — stôl
            # je ešte prázdny a ani jeden krok nehovorí o konkrétnych
            # hráčoch.
            step = self.current_step()
            return step is None or step["kind"] not in (
                "trick_demo", "penalty_overview"
            )
        return True

    # ------------------------------------------------------------------
    # Krokovanie
    # ------------------------------------------------------------------

    def current_step(self):
        """Aktuálny krok scenára, vrátane vetvenia (pozri step_for_trick)."""
        if self.step_index >= len(STEPS):
            return None
        step = STEPS[self.step_index]
        if self._trick_winner(5) == 0:
            key = step.get("key")
            if key == "trick8":
                winner7 = self._trick_winner(6)
                key = "trick8_p1" if winner7 == 1 else "trick8_p2"
            alt = BRANCH_B_STEPS.get(key)
            if alt is not None:
                return alt
        return step

    def _enter_step(self, index: int):
        self.step_index = index
        self.phase_index = 0
        step = self.current_step()
        if step is None:
            return
        # Panel KOLO sa prvýkrát ukáže pri vstupe do "trick2_collect" —
        # presne keď ho text prvýkrát spomína. Tento krok nasleduje AŽ PO
        # doletení kariet k víťazovi, takže panel vtedy už ukazuje
        # pripísané skóre, nie staré.
        if step.get("key") == "trick2_collect":
            self.show_round_status = True
        # Chujogram sa sprístupní v kroku, ktorý hráča vyzve ho otvoriť.
        if step.get("key") == "chujogram_wait":
            self.chujogram_revealed = True

    def _advance_phase(self):
        """Posunie sa na ďalší bod kroku "phase_list", alebo (na poslednom
        bode) na nasledujúci krok scenára."""
        step = self.current_step()
        if step is None or step["kind"] != "phase_list":
            return
        if self.phase_index + 1 < len(step["phases"]):
            self.phase_index += 1
        else:
            self._enter_step(self.step_index + 1)

    def _step_kind(self) -> str | None:
        step = self.current_step()
        return step["kind"] if step else None

    # ------------------------------------------------------------------
    # Klik na tlačidlo "Ďalej"
    # ------------------------------------------------------------------

    def handle_click(self, pos) -> bool:
        """
        Dostane klik pred zvyškom Screen. Vracia True, keď ho spotreboval.

        Zaujíma ho výhradne tlačidlo "Ďalej" v paneli s výkladom —
        všetko ostatné (karty, Chujogram, Menu) rieši Screen po svojom.
        """
        if self.screen is None or self.lesson_panel is None:
            return False
        button = self.lesson_panel.next_button
        if not button.width or not button.collidepoint(pos):
            return False

        step = self.current_step()
        if step is None:
            return False

        if step["kind"] == "trick":
            # Samostatný krok "zber štichu" v scenári neexistuje — "Ďalej"
            # po odohratom štichu rovno pustí jeho zber k víťazovi.
            rnd = self._round()
            if rnd is not None:
                self._released_trick = rnd.trick_number
            return True

        if step["kind"] == "phase_list":
            phase = step["phases"][self.phase_index]
            if phase.get("action") == "deal" and self._round() is None:
                # Skutočné rozdanie kariet — len kým ešte nie sú rozdané.
                # Bod "Rozdanie" potom ostáva aktívny ďalej (ukáže "ako
                # štich funguje", pozri panel_content()); DRUHÝ klik na
                # "Ďalej" už nejde sem, ale do vetvy nižšie.
                self._deal_requested = True
                self.screen._start_round()
            else:
                self._advance_phase()
            return True

        if self.step_index + 1 >= len(STEPS):
            # Posledný krok ("Dokončiť") — kapitola končí prirodzene,
            # rovnako ako Preskočiť (main.py pokračuje ďalšou kapitolou,
            # pozri Screen.run()/self._chapter_exit).
            self.finished = True
            self.exit_action = "advance"
            self.screen._chapter_exit = "skip"
            self.screen.running = False
            return True

        self._enter_step(self.step_index + 1)
        return True

    def _hide_button(self, step) -> bool:
        """
        Kedy sa tlačidlo "Ďalej" NEUKAZUJE.

        Šesť nezávislých dôvodov, prevzatých 1:1 z pôvodného
        tutorial_screen.py::_draw_panel(): hráč má najprv vykonať akciu,
        ktorú mu prikazuje zlatá inštrukcia — zahrať kartu, kliknúť na
        horníka, otvoriť Chujogram, otvoriť Posledný štich — alebo v kroku
        Záväzok pokračovať výhradne tlačidlom OK, nech sa naučí, že práve
        ono potvrdzuje rozhodnutie.
        """
        kind = step["kind"]
        is_phase_list = kind == "phase_list"
        is_trick = kind == "trick"
        phase = step["phases"][self.phase_index] if is_phase_list else None

        rnd = self._round()
        trick_settled = (
            rnd is not None
            and rnd.current_trick is not None
            and rnd.current_trick.is_complete
            and not self.screen.card_throw_animation.in_flight
        )

        return bool(
            kind == "human_play"
            or (is_trick and not trick_settled)
            or step.get("key") == "chujogram_wait"
            or (is_phase_list and phase["key"] == "zavazok")
            or (is_phase_list and phase["key"] == "vysvietenie"
                and not self.illumination_interacted)
            or (step.get("requires_last_trick_view")
                and not self.last_trick_viewed)
        )

    def suppress_declaration(self) -> bool:
        """Krok Záväzok je v kapitole 1 zámerne nanečisto — tlačidlá sa
        dajú kliknúť, ale záväzok sa reálne nevyhlási (rozhodnutie:
        návrh §9 č. 1). Skutočný záväzok by naskriptované kolo rozbil."""
        return True

    def draw(self):
        """
        Nakreslí panel s výkladom (gui/lesson_panel.py).

        Panel ukazuje aktuálny krok scenára aj s tlačidlom "Ďalej"
        (ak sa v tomto kroku má ukázať — pozri _hide_button).
        """
        if self.screen is None or self.lesson_panel is None:
            return
        if self.screen.dealing:
            # Počas rozdávania kreslí celú plochu DealAnimation.
            return
        step = self.current_step()
        if step is None:
            return

        self._sync_banner_title(step)

        if step["kind"] == "trick_demo":
            # Vlastné, výnimočne vycentrované rozloženie — nie bežný
            # bočný LessonPanel (pozri _draw_centered_panel).
            self._draw_centered_intro(step)
            return
        if step["kind"] == "penalty_overview":
            # Rovnaké vycentrované rozloženie ako "trick_demo" — pozri
            # _draw_centered_penalty_overview.
            self._draw_centered_penalty_overview(step)
            return

        content = self.panel_content(
            step,
            phase_index=self.phase_index,
            trick_played=self._human_has_played(),
            show_button=not self._hide_button(step),
        )
        self.lesson_panel.draw(
            counter=f"Krok {min(self.step_index + 1, len(STEPS))}/{len(STEPS)}",
            x_offset=self._chujogram_offset(),
            **content
        )

    def _sync_banner_title(self, step: dict):
        """Počas kroku "trick_demo" (ešte pred akýmkoľvek kolom) banner
        hovorí "ÚVOD" namiesto bežného "PRIEBEH KOLA"; mimo neho sa vracia
        na pôvodný názov zo settings. Netýka sa kapitoly 2 (Tréning) —
        tá director vôbec nemá."""
        banner = self.screen.chapter_banner
        if banner is None:
            return
        if step.get("key") == "intro_trick_demo":
            banner.title = self._INTRO_BANNER_TITLE
        else:
            banner.title = self._default_banner_title

    def _draw_centered_panel(self, step: dict, content_w: int,
                             content_h: int, draw_content):
        """
        Spoločné vycentrované rozloženie pre kroky "trick_demo" aj
        "penalty_overview" (výnimočne, mimo bežného úzkeho bočného
        LessonPanel) — nadpis, text a ľubovoľný obsahový riadok pod ním
        (animácia alebo karty), všetko na stred obrazovky, na tmavom
        poloprieehľadnom podklade (rovnaký princíp ako bežný LessonPanel).

        draw_content(top) nakreslí samotný obsahový riadok — dostane y-ovú
        súradnicu jeho horného okraja; content_w/content_h sú jeho rozmery,
        potrebné na výpočet podkladu a na odsadenie pod textom.

        next_button sa aj tak ukladá do self.lesson_panel.next_button —
        handle_click() vie len o LessonPanel, nie o konkrétnom kroku, a
        vďaka tomu to funguje bez zmeny.
        """
        surface = self.screen.screen
        panel = self.lesson_panel
        cx = TABLE_CENTER_X

        counter = f"Krok {min(self.step_index + 1, len(STEPS))}/{len(STEPS)}"
        title = step.get("title")
        body_text = step.get("text", "")
        max_text_w = min(820, SCREEN_WIDTH - 160)

        counter_font = panel.font_small
        counter_h = counter_font.get_linesize()
        spacing = 20

        def layout(font):
            lines = LessonPanel.wrap_paragraphs(body_text, font, max_text_w)
            line_h = font.get_linesize()
            title_h = font.get_linesize() if title else 0
            text_h = len(lines) * line_h
            total = (counter_h + spacing + title_h + (10 if title else 0)
                     + text_h + spacing + content_h + spacing + BUTTON_H)
            return lines, line_h, title_h, total

        body_font = panel.font_medium
        lines, line_h, title_h, total_h = layout(body_font)
        available_h = panel.max_bottom - PANEL_TOP
        if total_h > available_h:
            body_font = panel.font_small
            lines, line_h, title_h, total_h = layout(body_font)

        ty = PANEL_TOP + max(0, (available_h - total_h) // 2)

        pad_x, pad_y = 50, 30
        backdrop_w = max(max_text_w, content_w) + 2 * pad_x
        backdrop_h = total_h + 2 * pad_y
        backdrop_rect = pygame.Rect(0, 0, backdrop_w, backdrop_h)
        backdrop_rect.centerx = cx
        backdrop_rect.top = ty - pad_y
        backdrop = pygame.Surface((backdrop_w, backdrop_h), pygame.SRCALPHA)
        backdrop.fill((*COLOR_PANEL_BG, 235))
        surface.blit(backdrop, backdrop_rect.topleft)
        pygame.draw.rect(surface, COLOR_GOLD, backdrop_rect,
                         width=2, border_radius=14)

        counter_surf = counter_font.render(counter, True, COLOR_GRAY)
        surface.blit(counter_surf, counter_surf.get_rect(centerx=cx, top=ty))
        ty += counter_h + spacing

        if title:
            title_surf = body_font.render(title, True, COLOR_GOLD)
            surface.blit(title_surf, title_surf.get_rect(centerx=cx, top=ty))
            ty += title_h + 10

        for line in lines:
            line_surf = body_font.render(line, True, COLOR_WHITE)
            surface.blit(line_surf, line_surf.get_rect(centerx=cx, top=ty))
            ty += line_h
        ty += spacing

        draw_content(ty)
        ty += content_h + spacing

        button_label = "Ďalej →"
        text_surf = panel.font_medium.render(button_label, True, COLOR_WHITE)
        btn_w = text_surf.get_width() + 50
        button_rect = pygame.Rect(0, 0, btn_w, BUTTON_H)
        button_rect.centerx = cx
        button_rect.top = ty
        overlay = pygame.Surface((btn_w, BUTTON_H), pygame.SRCALPHA)
        overlay.fill((*COLOR_BUTTON_PRIMARY, 230))
        surface.blit(overlay, button_rect.topleft)
        pygame.draw.rect(surface, COLOR_GOLD, button_rect,
                         width=2, border_radius=BUTTON_RADIUS)
        surface.blit(text_surf, text_surf.get_rect(center=button_rect.center))
        # Jediný dôvod, prečo sa krok vôbec dotýka LessonPanel — handle_click()
        # odtiaľ tlačidlo číta bez ohľadu na to, ktorý krok ho nakreslil.
        panel.next_button = button_rect

    def _draw_centered_intro(self, step: dict):
        """Úplne prvý krok — privítanie + "čo je štich". Obsahový riadok
        je animácia 4 kariet vedľa seba (_draw_trick_demo_row)."""
        card_w, card_h = CARD_SIZE_MEDIUM
        count = len(self._DEMO_CARDS)
        content_w = count * card_w + (count - 1) * self._DEMO_GAP
        self._draw_centered_panel(step, content_w, card_h,
                                  self._draw_trick_demo_row)

    def _draw_trick_demo_row(self, top: int):
        """
        Animácia "čo je štich": 4 karty sa postupne objavia VEDĽA SEBA
        (vodorovný rad, vycentrovaný), po chvíli sa spolu zbalia k stredu
        a zmiznú (štich si niekto vzal) — bez rúk, mien či pozícií
        konkrétnych hráčov, len princíp. Beží v slučke, kým je krok
        zobrazený (pozri _DEMO_* konštanty vyššie). top = horný okraj
        riadku, vypočítaný volajúcim (_draw_centered_panel) podľa toho,
        kde skončil text nad ním.
        """
        surface = self.screen.screen
        renderer = self.screen.card_renderer
        card_w, card_h = CARD_SIZE_MEDIUM
        gap = self._DEMO_GAP
        cx = TABLE_CENTER_X
        cy = top + card_h // 2
        count = len(self._DEMO_CARDS)
        total_w = count * card_w + (count - 1) * gap
        x0 = cx - total_w // 2

        now = pygame.time.get_ticks()
        if self._demo_start_time is None:
            self._demo_start_time = now
        elapsed = (now - self._demo_start_time) % self._DEMO_CYCLE_MS

        for i, card in enumerate(self._DEMO_CARDS):
            ox = x0 + i * (card_w + gap) + card_w // 2 - cx
            appear_t = i * self._DEMO_APPEAR_STEP_MS
            if elapsed < appear_t:
                continue

            if elapsed < self._DEMO_APPEAR_END_MS:
                local = elapsed - appear_t
                alpha = (255 if local >= self._DEMO_APPEAR_FADE_MS
                         else int(255 * local / self._DEMO_APPEAR_FADE_MS))
                x = cx + ox
            elif elapsed < self._DEMO_APPEAR_END_MS + self._DEMO_HOLD_MS:
                alpha = 255
                x = cx + ox
            elif elapsed < (self._DEMO_APPEAR_END_MS + self._DEMO_HOLD_MS
                            + self._DEMO_COLLECT_MS):
                t = ((elapsed - self._DEMO_APPEAR_END_MS - self._DEMO_HOLD_MS)
                     / self._DEMO_COLLECT_MS)
                x = cx + ox * (1 - t)
                alpha = int(255 * (1 - t))
            else:
                continue   # pauza pred ďalším opakovaním

            if alpha <= 0:
                continue
            img = renderer._get_card_image(card, size="medium").copy()
            img.set_alpha(alpha)
            rect = img.get_rect(center=(int(x), int(cy)))
            surface.blit(img, rect)
            if alpha == 255:
                pygame.draw.rect(surface, COLOR_GOLD, rect,
                                 width=2, border_radius=6)

    def _draw_centered_penalty_overview(self, step: dict):
        """
        Krok s prehľadom trestných kariet — rovnaké vycentrované
        rozloženie ako úvodný krok (_draw_centered_panel). Zelený a
        žaluďový horník ako samostatné karty, vedľa nich vejár VŠETKÝCH 8
        srdcových kariet (od esa zostupne — "cards"/"hearts" pripravuje
        tutorial_steps.py), mierne prekrytých (vidno len asi tretinu
        každej), aby sa zmestili na šírku bez pôsobenia ako osem
        oddelených kariet.

        Zámerne NEukazuje hodnotu pri vysvietení — v úvodnom prehľade by
        hráča mýlila skôr, než by pomohla; vysvietenie sa vysvetľuje až
        vo vlastnom kroku neskôr.
        """
        card_w, card_h = CARD_SIZE_MEDIUM
        specials = step.get("cards") or []
        hearts = step.get("hearts") or []
        heart_step = max(1, card_w // 3)   # ~2/3 prekryté = vidno tretinu
        content_w = self._penalty_row_w(specials, hearts, heart_step)
        # Karta + popis (pri vejári sa dlhší text zvykne zalomiť na 2
        # riadky, preto rezerva na 2 riadky aj pre horníkov) + body.
        content_h = card_h + 10 + 2 * 22 + 30

        def draw_row(top: int):
            self._draw_penalty_cards_row(
                top, specials, hearts, heart_step,
                step.get("hearts_label", ""), step.get("hearts_points", "")
            )

        self._draw_centered_panel(step, content_w, content_h, draw_row)

    def _draw_penalty_cards_row(self, top: int, specials: list,
                                hearts: list, heart_step: int,
                                hearts_label: str, hearts_points: str):
        """Nakreslí samotný riadok: zelený a žaluďový horník ako
        samostatné karty (vlastný popis a body pod každou), vedľa nich
        vejár sŕdc (jeden spoločný popis a body pod celým vejárom)."""
        surface = self.screen.screen
        panel = self.lesson_panel
        renderer = self.screen.card_renderer
        card_w, card_h = CARD_SIZE_MEDIUM
        gap = self._DEMO_GAP

        def draw_label(center_x: int, label: str, points: str):
            ty = top + card_h + 10
            for line in panel.wrap_text(label, panel.font_small, card_w + 30):
                surf = panel.font_small.render(line, True, COLOR_WHITE)
                surface.blit(surf, surf.get_rect(centerx=center_x, top=ty))
                ty += 22
            points_surf = panel.font_medium.render(points, True, COLOR_GOLD)
            surface.blit(points_surf, points_surf.get_rect(
                centerx=center_x, top=ty))

        x = TABLE_CENTER_X - self._penalty_row_w(specials, hearts, heart_step) // 2

        for card, label, points in specials:
            surface.blit(renderer._get_card_image(card, size="medium"),
                         (x, top))
            pygame.draw.rect(surface, COLOR_GOLD, (x, top, card_w, card_h),
                             width=2, border_radius=6)
            draw_label(x + card_w // 2, label, points)
            x += card_w + gap

        hearts_x0 = x
        for card in hearts:
            surface.blit(renderer._get_card_image(card, size="medium"),
                         (x, top))
            pygame.draw.rect(surface, COLOR_GOLD, (x, top, card_w, card_h),
                             width=2, border_radius=6)
            x += heart_step
        hearts_w = card_w + max(0, len(hearts) - 1) * heart_step
        if hearts:
            draw_label(hearts_x0 + hearts_w // 2, hearts_label, hearts_points)

    @staticmethod
    def _penalty_row_w(specials: list, hearts: list, heart_step: int) -> int:
        """Celková šírka riadku trestných kariet — zdieľaná medzi
        výpočtom podkladu (_draw_centered_penalty_overview) a samotným
        kreslením (_draw_penalty_cards_row), nech sa od seba nikdy
        nerozídu."""
        card_w, _ = CARD_SIZE_MEDIUM
        hearts_w = card_w + max(0, len(hearts) - 1) * heart_step
        gap = TutorialDirector._DEMO_GAP
        return len(specials) * (card_w + gap) + hearts_w

    # ------------------------------------------------------------------
    # Preklad "krok scenára" -> "obsah panelu"
    # ------------------------------------------------------------------

    def panel_content(self, step: dict, phase_index: int = 0,
                      trick_played: bool = False,
                      show_button: bool = False) -> dict:
        """
        Prevedie krok scenára na pomenované argumenty pre LessonPanel.

        Panel zámerne nevie nič o krokoch tutoriálu — všetko rozhodovanie
        "čo sa má v tomto kroku ukázať" je tu. Logika je prevzatá 1:1 z
        pôvodného tutorial_screen.py::_draw_panel().
        """
        kind = step["kind"]
        is_phase_list = kind == "phase_list"
        is_trick = kind == "trick"
        is_bullets = kind == "bullets"
        phase = step["phases"][phase_index] if is_phase_list else None
        acorn_lit = Card("acorn", "over") in self.illuminated_cards
        # Bod "Rozdanie" po doletení kariet ukazuje "ako štich funguje"
        # namiesto pôvodného textu, stále v TOM ISTOM bode (pozri
        # tutorial_steps.py: phase["bullets_after"], handle_click()).
        dealt = (
            is_phase_list and phase["key"] == "rozdanie"
            and self._round() is not None and not self.screen.dealing
        )

        labels: list[tuple[str, bool]] = []
        paragraphs: str | None = None
        bullets: list[str] | None = None

        if is_phase_list:
            labels = [(p["label"], p is phase) for p in step["phases"]]
            if dealt and phase.get("bullets_after"):
                bullets = phase["bullets_after"]
            else:
                paragraphs = phase["text"]
                if phase["key"] == "vysvietenie" and acorn_lit:
                    paragraphs = phase.get("text_after", phase["text"])
        elif is_trick:
            paragraphs = (self._trick_text_after(step) if trick_played
                          else step["text_before"])
        elif is_bullets:
            bullets = step["bullets"]
        else:
            text_fn = step.get("text_fn")
            paragraphs = text_fn(self) if text_fn is not None else step["text"]

        instruction = None
        if kind == "human_play":
            instruction = step["instruction"]
        elif is_trick and not trick_played:
            instruction = step["human_instruction"]
        elif is_phase_list:
            # Dobrovoľná inštrukcia (zrušiť / pokračovať) namiesto príkazu
            # sa týka VÝHRADNE bodu "vysvietenie", a to až keď hráč
            # horníka naozaj vysvietil. Ostatné body (rozdanie, zavazok)
            # majú vždy svoju bežnú inštrukciu — bez tejto podmienky by o
            # ňu krok "Záväzok" prišiel.
            if phase["key"] == "vysvietenie" and acorn_lit:
                instruction = phase.get("instruction_after")
            else:
                instruction = phase.get("instruction")
        elif step.get("instruction"):
            instruction = step["instruction"]

        button_label = None
        if show_button:
            if is_phase_list and phase.get("action") == "deal" and not dealt:
                button_label = "Rozdať karty →"
            elif kind == "result":
                button_label = "Dokončiť"
            else:
                button_label = "Ďalej →"

        return {
            "labels": labels,
            "title": step.get("title"),
            "paragraphs": paragraphs,
            "bullets": bullets,
            "instruction": instruction,
            "button_label": button_label,
        }

    def _trick_text_after(self, step: dict) -> str:
        """Text po hráčovom ťahu. Scenár ho vyberá tromi spôsobmi —
        podľa konkrétnej zahranej karty, dynamickou funkciou, alebo
        staticky."""
        by_card = step.get("text_after_by_card")
        text_after_fn = step.get("text_after_fn")
        card = self.trick_human_played_card
        fallback = step.get("text_after", "")

        if by_card is not None and card is not None:
            return by_card.get((card.suit, card.rank), fallback)
        if text_after_fn is not None:
            # Dynamický text je len výklad, nie herná logika — keby sa v
            # ňom čokoľvek pokazilo, nesmie to zhodiť rozohratú lekciu.
            try:
                return text_after_fn(self)
            except Exception:
                if not self._text_error_logged:
                    self._text_error_logged = True
                    import traceback
                    traceback.print_exc()
                return fallback
        return fallback

    # ------------------------------------------------------------------
    # Atribúty, na ktoré sa spoliehajú dynamické texty v scenári
    # ------------------------------------------------------------------
    # text_after_fn / text_fn v tutorial_steps.py dostávajú ako argument
    # "screen" — pôvodne to bola TutorialScreen. Teraz dostávajú režiséra,
    # takže musí ponúkať tie isté tri veci. Rozdiel je, že sa už nečítajú
    # z vlastných pomocných polí, ale priamo z herného stavu.

    @property
    def players(self) -> list:
        return self.screen.game_state.players if self.screen else []

    @property
    def illuminated_cards(self) -> list:
        """Horníci, ktorých vysvietil ĽUDSKÝ hráč. Počas prípravy je to
        jeho rozpracovaný výber, po potvrdení už skutočný stav hráča."""
        if self.screen is None:
            return []
        game_state = self.screen.game_state
        player = game_state.players[game_state.human_index]
        cards = list(self.screen.selected_illumination)
        if player.illuminated_leaf:
            cards.append(Card("leaf", "over"))
        if player.illuminated_acorn:
            cards.append(Card("acorn", "over"))
        return cards

    @property
    def trick_human_played_card(self):
        """Karta, ktorú hráč zahral v práve prebiehajúcom štichu; ak už
        bol štich uzavretý, tak v tom poslednom odohranom."""
        rnd = self._round()
        if rnd is None:
            return None
        human = self.screen.game_state.human_index
        candidates = []
        if rnd.current_trick is not None:
            candidates.append(rnd.current_trick)
        if rnd.tricks:
            candidates.append(rnd.tricks[-1])
        for trick in candidates:
            for index, card in trick.played_cards:
                if index == human:
                    return card
        return None

    def restrict_playable(self, playable: list) -> list:
        """
        Zúži hráčovi voľbu na to, čo scenár v danom štichu ponúka.

        step["human_card"] je NADMNOŽINA možností, nie konkrétna karta —
        v neskorších štichoch sú v zozname aj karty, ktoré hráč už zahral
        ("zahraj ktorúkoľvek zo zvyšných"). Skutočnú voľbu teda dáva až
        prienik s tým, čo hráč naozaj môže zahrať podľa pravidiel.

        Prienik nikdy nič nepovoľuje navyše — a ak by vyšiel prázdny
        (chyba v scenári), radšej necháme pôvodné povolené karty, než aby
        hráč ostal zaseknutý bez možnosti ťahu.

        Kým lekcia čaká na "Ďalej", nehrá sa vôbec — inak by hráč mohol
        vybehnúť dopredu do štichu, o ktorom sa ešte len ide hovoriť.
        """
        if self.is_paused():
            return []
        step = self.current_step()
        if step is None or step["kind"] != "trick":
            return playable
        options = step.get("human_card")
        if options is None:
            return playable
        if not isinstance(options, (list, tuple)):
            options = [options]
        narrowed = [card for card in playable if card in options]
        if narrowed:
            return narrowed

        # Sem sa dostaneme len pri chybe v scenári (is_paused() stráži, aby
        # sa krok a štich nerozišli). Radšej povolíme pôvodné karty, než
        # aby hráč ostal zaseknutý bez možnosti ťahu — ale nahlas o tom
        # povieme, nech sa chyba nestratí.
        if not self._playable_error_logged:
            self._playable_error_logged = True
            print(
                f"[tutoriál] VAROVANIE: krok {step.get('key')} ponúka "
                f"{[str(c) for c in options]}, ale hráč môže zahrať len "
                f"{[str(c) for c in playable]}. Povoľujem všetko."
            )
        return playable

    # ------------------------------------------------------------------
    # Scenár
    # ------------------------------------------------------------------

    def scripted_card(self, player_index: int, trick_number: int):
        """Karta, ktorú má daný počítač zahrať v danom štichu. Volá
        tutorial/scripted_ai.py::ScriptedAI.decide_card()."""
        step = self.step_for_trick(trick_number)
        if step is None:
            return None
        auto_plays = (list(step.get("pre_human") or [])
                      + list(step.get("post_human") or []))
        for index, card in auto_plays:
            if index == player_index:
                return card
        return None

    def step_for_trick(self, trick_number: int):
        """
        Krok scenára pre daný štich, vrátane vetvenia.

        Vetva B: ak hráč v trick6 prebil horníka Počítača 1 a vyhral štich
        sám, vedie odvtedy ON, nie Počítač 1 — pôvodný (autentický)
        priebeh trick7/trick8 by už nesedel, takže sa nahradia variantom
        z BRANCH_B_STEPS. V tejto vetve navyše hráč v trick7 sám vedie, a
        farbou, ktorou vyjde, rozhodne, či trick7 vyhrá Počítač 1 alebo
        Počítač 2 — podľa toho sa pre trick8 vyberá "trick8_p1" alebo
        "trick8_p2".

        Víťazov čítame priamo z odohraných štichov (Round.tricks), nie z
        vlastných pomocných polí ako doteraz — herný stav to vie sám.
        """
        if not 0 <= trick_number < len(TRICK_KEYS):
            return None
        key = TRICK_KEYS[trick_number]

        if key in ("trick7", "trick8") and self._trick_winner(5) == 0:
            if key == "trick7":
                return BRANCH_B_STEPS.get("trick7")
            winner7 = self._trick_winner(6)
            return BRANCH_B_STEPS.get(
                "trick8_p1" if winner7 == 1 else "trick8_p2"
            )

        return self._steps_by_key.get(key)

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _round(self):
        if self.screen is None:
            return None
        return self.screen.game_state.current_round

    def _human_has_played(self) -> bool:
        """Zahral už hráč v prebiehajúcom štichu? Text sa prepína hneď —
        nečaká sa, kým dolietajú karty počítačov po ňom, nech výklad
        nezaostáva za tým, čo sa práve deje."""
        rnd = self._round()
        if rnd is None or rnd.current_trick is None:
            return False
        human = self.screen.game_state.human_index
        return any(index == human
                   for index, _ in rnd.current_trick.played_cards)

    def _chujogram_offset(self) -> int:
        """Chujogram je vysúvací pás cez celú výšku vľavo — ak je čo i len
        čiastočne vysunutý, panel posunieme doprava za jeho pravý okraj.
        Rovnaký výpočet ako pre panel s tipom v gui/screen.py::_draw."""
        chujogram = getattr(self.screen, "chujogram", None)
        if chujogram is None:
            return 0
        right = chujogram.panel_x + chujogram.panel_w
        return max(0, int(right + 20 - PANEL_LEFT))

    def _trick_winner(self, index: int):
        """Víťaz už UZAVRETÉHO štichu, alebo None ak ešte neskončil."""
        rnd = self._round()
        if rnd is None or index >= len(rnd.tricks):
            return None
        return rnd.tricks[index].get_winner_index()

    def __repr__(self) -> str:
        rnd = self._round()
        where = f"štich {rnd.trick_number + 1}" if rnd else "pred rozdaním"
        return f"TutorialDirector({where})"
