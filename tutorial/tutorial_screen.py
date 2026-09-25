# tutorial/tutorial_screen.py

import pygame
import sys
from game.card import Card
from game.player import Player
from game.trick import Trick
from gui.card_renderer import CardRenderer
from gui.card_throw_animation import CardThrowAnimation
from gui.deal_animation import DealAnimation
from gui.trick_animation import TrickAnimation
from gui.phase_renderer import PhaseRenderer
from gui.round_status import RoundStatus
from gui.speech_bubble import SpeechBubble
from gui.chujogram_panel import ChujogramPanel
from tutorial.tutorial_steps import STEPS, build_tutorial_hands, BRANCH_B_STEPS
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_BG, COLOR_WHITE, COLOR_GOLD, COLOR_GRAY,
    COLOR_PANEL_BG, COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_LARGE,
    BUTTON_RADIUS, get_font,
    TABLE_CENTER_X, TABLE_CENTER_Y, CARD_SIZE_MEDIUM, CARD_SIZE_SMALL, HAND_CONFIGS,
)


class TutorialScreen:
    """
    Samostatná, naskriptovaná obrazovka — ukážkový štich s krokovaním a
    vysvetľujúcimi bublinami. Nezávislá od gui/screen.py::Screen (podobne
    ako tester/tester_screen.py), aby sa neriskovalo zasahovanie do
    reálnej hry. Spustiteľná samostatne cez tutorial_main.py, neskôr
    zapojiteľná aj z hlavného menu.
    """

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Chuj — Tutoriál")
        self.clock = pygame.time.Clock()

        self.font_small = get_font(FONT_SIZE_SMALL)
        self.font_medium = get_font(FONT_SIZE_MEDIUM)
        self.font_large = get_font(FONT_SIZE_LARGE)

        try:
            self.bg = pygame.image.load("assets/graphics/table3.jpg").convert()
            self.bg = pygame.transform.scale(self.bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except FileNotFoundError:
            self.bg = None

        self.players = self._build_players()
        # Počítač 1 má zeleného horníka vysvietený po celý zvyšok kola
        # (naskriptované — v reálnej hre, z ktorej seed pochádza, sa
        # skutočné AI rozhodlo nevysvietiť, tu to preprogramujeme). Karta
        # sa mu vďaka tomu bude v ruke kresliť lícom, presne rovnakým
        # mechanizmom ako v ostrej hre (gui/screen.py) — nastavíme to
        # rovno tu, aby to platilo od úplného začiatku.
        self.players[1].illuminated_leaf = True

        # Sériu bez trestných bodov (no_penalty_streak) v tomto tutoriáli
        # zámerne NEnastavujeme umelo — bonus −10 za 5 čistých kôl v rade
        # je koncept, ktorý si vyžaduje vysvetliť aj históriu kôl a guličky
        # v Chujograme, a to sme sa rozhodli nechať na neskôr (plánovaná
        # krátka precvičovacia hra hneď po tutoriáli). Streak teda ostáva
        # na predvolenej hodnote (Player.__init__) a po tomto čistom kole
        # jednoducho stúpne na 1 — žiadny bonus sa nespustí.

        # Chujogram v tomto tutoriáli ukazuje LEN toto jedno (skutočné)
        # odohrané kolo — žiadnu fiktívnu predošlú históriu. Jediný riadok
        # pridá _finalize_round() po odohraní všetkých 8 štichov, hráči
        # začínajú na total_score=0 (predvolené v Player.__init__).
        self.round_scores_history: list[list[int]] = []
        self.bullet_history: list[list[int]] = []

        self.card_renderer = CardRenderer(self.screen, debug=False)
        self.card_throw_animation = CardThrowAnimation(self.screen, self.card_renderer)
        self.trick_animation = TrickAnimation(self.screen, self.card_renderer)
        self.round_status = RoundStatus(self.screen)
        self.speech_bubble = SpeechBubble(self.screen)
        self.chujogram = ChujogramPanel(self.screen, [p.name for p in self.players])
        self.trick = Trick(self.players, leader_index=1)

        self.step_index = 0
        self.phase_index = 0
        self.finished = False
        # Dôvod ukončenia run() slučky — rozlišuje, či má orchestrátor
        # kapitol (tutorial_main.py) pokračovať ďalšou kapitolou
        # ("advance": Preskočiť alebo prirodzený koniec cez Dokončiť),
        # alebo ukončiť celý tutoriál ("quit": Esc). Zavretie okna
        # (pygame.QUIT) je vždy tvrdý sys.exit(), tam sa exit_action
        # nevyhodnocuje.
        self.exit_action: str = "quit"

        self.skip_button = pygame.Rect(SCREEN_WIDTH - 190, 24, 150, 44)
        self.next_button = pygame.Rect(0, 0, 0, 0)  # dopočíta sa pri kreslení

        # Panel s textom dávame na ĽAVÚ stranu obrazovky, nie navrch —
        # voľný priestor NAD stolom je (kvôli veľkosti kariet) príliš
        # tesný na dlhší text bez zásahu do stola. Vľavo panel smie
        # prekryť iba ruku Počítača 3 (karty rubom, na priebeh ukážky to
        # nemá vplyv) — nesmie však zasiahnuť ani do stredu stola (karty
        # štichu), ani do vlastnej ruky hráča dole. Obe hranice počítame
        # z reálnej geometrie stola/ruky (config konštanty), takže to
        # funguje pri akomkoľvek rozlíšení obrazovky.
        table_left_x = TABLE_CENTER_X - 150 - CARD_SIZE_MEDIUM[0] // 2
        self.panel_max_right = table_left_x - 40
        self.panel_max_bottom = HAND_CONFIGS[0]["y"] - 30

        # Stav rozdania — počas neho kreslenie/udalosti preberá DealAnimation
        self.dealing = False
        self.deal_animation: DealAnimation | None = None

        # Kým karty ešte neboli rozdané (animáciou), ruky hráčov sa
        # nekreslia — obrazovka na začiatku ukazuje prázdny stôl, nie
        # karty "už rozdané" ešte pred spustením animácie rozdania.
        self.cards_dealt = False

        # Stav zberu štichu — počas neho kreslenie/udalosti preberá
        # TrickAnimation (bez možnosti preskočiť, rovnako ako v ostrej hre).
        self.collecting_trick = False

        # Panel KOLO sa zapne pri vstupe do kroku "trick2_collect" (pozri
        # _enter_step) — presne v momente, keď naň text prvýkrát odkazuje
        # (a keď už bežia pripísané body, nie skôr — pozri komentár tam).
        self.show_round_status = False

        # Stav kroku kind="trick". Dva samostatné príznaky:
        # - trick_human_card_played: hráč už klikol svoju kartu (text sa
        #   prepne na "text_after", tlačidlo Ďalej ale ešte nie).
        # - trick_step_human_played: CELÝ štich je hotový (aj automatické
        #   ťahy počítačov po hráčovi doleteli) — až potom sa ukáže Ďalej.
        self.trick_human_card_played = False
        self.trick_step_human_played = False
        # Ktorú konkrétnu kartu hráč naozaj klikol (dôležité pri krokoch,
        # kde "human_card" je zoznam viacerých rovnocenných možností —
        # napr. trick4, kde si hráč vyberá medzi K● a 8●) — používa sa na
        # výber správneho textu po zahraní (pozri "text_after_by_card").
        self.trick_human_played_card: Card | None = None

        # Kto vyhral trick6 (nastaví sa v _finish_trick_collect). V
        # bežnom (autentickom) priebehu je to vždy Počítač 1 (index 1) —
        # ak si však hráč pri trick4 nechal guľového kráľa na trick6,
        # prebije ním horníka Počítača 1 a vyhráva trick6 sám (index 0).
        # V tom prípade sa trick7/trick8 nahrádzajú alternatívnou vetvou
        # (pozri BRANCH_B_STEPS a _current_step nižšie), lebo hráč
        # odvtedy vedie ďalší štich namiesto Počítača 1.
        self.trick6_winner: int | None = None

        # Kto vyhral trick7 v alternatívnej vetve (nastaví sa v
        # _finish_trick_collect, len keď trick6_winner == 0). V tejto
        # vetve hráč pri trick7 skutočne vedie a jeho voľba farby (list
        # vs. žaluď) rozhoduje, či štich vyhrá Počítač 1 (index 1) alebo
        # Počítač 2 (index 2) — a teda kto povedie posledný, 8. štich
        # (pozri BRANCH_B_STEPS["trick8_p1"]/["trick8_p2"]).
        self.branch_b_trick7_winner: int | None = None

        # Fronta automatických ťahov (počítačové karty, ktoré sa majú
        # zahrať jedna po druhej pri vstupe do kroku "trick", alebo hneď
        # po hráčovom ťahu) — každá ďalšia odletí až keď doletí predošlá,
        # aby sa viac kariet nehádzalo na stôl naraz (pozri
        # _advance_auto_plays).
        self.pending_auto_plays: list[tuple[int, Card]] = []

        # Tlačidlo Chujogramu sa odhalí až pri bodovaní na konci kola.
        self.chujogram_revealed = False

        # História odohraných štichov (pozri _finish_trick_collect) —
        # každý záznam je (played_cards, winner_index) tesne pred tým,
        # než sa štich vyprázdni. Slúži rovnakému tlačidlu "Posledný
        # štich" ako v ostrej hre (gui/screen.py) — tu sa objaví, len čo
        # existuje aspoň jeden odohraný štich, teda od trick2.
        self.completed_tricks: list[tuple[list[tuple[int, Card]], int]] = []
        self.show_last_trick = False
        # True, len čo hráč aspoň raz otvoril "Posledný štich" — používa sa
        # ako brána pre kroky s "requires_last_trick_view" (napr. pred
        # trick2, kde ho na to vyzveme).
        self.last_trick_viewed = False

        # Karty, ktoré hráč sám vysvietil klikom (krok "Vysvietenie")
        self.illuminated_cards: list[Card] = []
        # True, len čo hráč aspoň raz klikol na svojho horníka v kroku
        # "Vysvietenie" — tlačidlo Ďalej sa dovtedy neukazuje (pozri
        # hide_button v _draw_panel), aby hráč inštrukciu naozaj vyskúšal.
        # Zámerne sa NEresetuje pri opätovnom zrušení vysvietenia — stačí
        # to vyskúšať raz.
        self.illumination_interacted = False

        # Klikateľný náhľad záväzku (kroky "Vysvietenie" a "Záväzok") —
        # bez reálneho dopadu na priebeh ukážky, len aby si hráč vyskúšal
        # tlačidlá skôr, než mu záväzok podrobne vysvetlíme.
        self.active_declaration: str | None = None

        # Po potvrdení kroku Záväzok (tlačidlo OK) — rovnako ako v ostrej
        # hre (gui/preparation_handler.py::confirm_preparation) sa
        # "vysunutá" karta zasunie späť do ruky a namiesto toho sa ukáže
        # bublina "Svietim...".
        self.declaration_confirmed = False

        self._enter_step(0)

    # ------------------------------------------------------------------
    # Zostavenie hráčov a rúk
    # ------------------------------------------------------------------

    def _build_players(self) -> list[Player]:
        names = ["Hráč", "Počítač 1", "Počítač 2", "Počítač 3"]
        players = [
            Player(name, is_human=(i == 0), index=i)
            for i, name in enumerate(names)
        ]
        hands = build_tutorial_hands()
        for i, player in enumerate(players):
            player.receive_cards(hands[i])
        return players

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Vráti exit_action ("advance" alebo "quit") — pozri __init__ a
        tutorial_main.py::CHAPTERS, ktorý podľa toho rozhoduje, či
        pokračovať ďalšou kapitolou."""
        while not self.finished:
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.finished = True

                if self.dealing:
                    # Počas rozdávania preberá klik/medzerník DealAnimation
                    # (jej vlastné "preskočiť" správanie).
                    self.deal_animation.handle_event(event)
                    continue

                if self.collecting_trick:
                    # Počas zberu štichu k víťazovi sa neklika (rovnako ako
                    # v ostrej hre — TrickAnimation nemá "preskočiť").
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            if self.dealing:
                self.deal_animation.update()
                if self.deal_animation.done:
                    self.dealing = False
                    self.cards_dealt = True
                    self._advance_phase()
            elif self.collecting_trick:
                self.trick_animation.update()
                if self.trick_animation.is_done:
                    self._finish_trick_collect()
            else:
                self.card_throw_animation.update()
                self._advance_auto_plays()

            self._draw()
            pygame.display.flip()

        return self.exit_action

    # ------------------------------------------------------------------
    # Kroky
    # ------------------------------------------------------------------

    def _current_step(self) -> dict | None:
        if self.step_index >= len(STEPS):
            return None
        step = STEPS[self.step_index]
        # Ak hráč pri trick6 nečakane prebil horníka Počítača 1 (pozri
        # trick6_winner v __init__), nahradíme trick7/trick8 alternatívnou
        # vetvou — v tejto vetve totiž vedie ďalší štich hráč, nie
        # Počítač 1, takže ich pôvodný (autentický) obsah by už nesedel.
        if self.trick6_winner == 0:
            key = step.get("key")
            if key == "trick8":
                # V trick7 hráč sám vedie a jeho voľba farby rozhodne, či
                # štich (a teda aj vedenie trick8) získa Počítač 1 alebo
                # Počítač 2 — pozri branch_b_trick7_winner v __init__.
                key = (
                    "trick8_p1" if self.branch_b_trick7_winner == 1
                    else "trick8_p2"
                )
            alt = BRANCH_B_STEPS.get(key)
            if alt is not None:
                return alt
        return step

    def _enter_step(self, index: int):
        self.step_index = index
        self.phase_index = 0
        self.dealing = False
        step = self._current_step()
        if step is not None and step["kind"] == "ai_play":
            self._play_card(step["player_index"], step["card"])
        if step is not None and step["kind"] == "trick":
            self.trick_human_card_played = False
            self.trick_step_human_played = False
            self.trick_human_played_card = None
            self._queue_auto_plays(step.get("pre_human", []))
        if step is not None and step.get("key") == "chujogram_wait":
            self.chujogram_revealed = True
        # Panel KOLO sa prvýkrát zobrazí hneď pri vstupe do "trick2_collect"
        # — presne v momente, keď text prvýkrát spomína, že si ho máš
        # všimnúť. Tento krok nasleduje AŽ PO doletení kariet k víťazovi
        # (_finish_trick_collect body pripíše skôr, než sem vstúpime), takže
        # panel vtedy už ukazuje aktuálne, pripísané skóre.
        if step is not None and step.get("key") == "trick2_collect":
            self.show_round_status = True

    def _play_card(self, player_index: int, card):
        player = self.players[player_index]
        throw_start = self.card_renderer.hand_card_center(
            player_index, player.hand.cards, card
        )
        player.play_card(card)
        self.trick.play_card(player_index, card)
        self.card_throw_animation.start(player_index, card, throw_start)

    def _queue_auto_plays(self, pairs):
        """Nastaví frontu automatických (počítačových) ťahov, ktoré sa
        majú postupne odohrať — pozri _advance_auto_plays."""
        self.pending_auto_plays = list(pairs)
        self._advance_auto_plays()

    def _advance_auto_plays(self):
        """Zavolané každú snímku (pozri run()). Kým je vo fronte
        automatický ťah a žiadna karta práve nelieta, zahrá ďalší — vďaka
        tomu karty odlietavajú na stôl jedna po druhej, nie všetky naraz.
        Keď fronta pre aktuálny krok "trick" doletí celá (vrátane
        automatických ťahov PO hráčovej karte), sprístupní tlačidlo
        Ďalej."""
        if self.pending_auto_plays and not self.card_throw_animation.in_flight:
            player_index, card = self.pending_auto_plays.pop(0)
            self._play_card(player_index, card)

        step = self._current_step()
        if (step is not None and step["kind"] == "trick"
                and self.trick_human_card_played
                and not self.trick_step_human_played
                and not self.pending_auto_plays
                and not self.card_throw_animation.in_flight):
            self.trick_step_human_played = True

    def _advance_phase(self):
        """Posunie na ďalší bod v phase_list kroku, alebo (na poslednom
        bode) prejde na nasledujúci hlavný krok tutoriálu."""
        step = self._current_step()
        phases = step["phases"]
        if self.phase_index + 1 < len(phases):
            self.phase_index += 1
        else:
            self._enter_step(self.step_index + 1)

    def _confirm_preparation(self):
        """Tlačidlo OK v kroku Záväzok — presne ako v ostrej hre
        (gui/preparation_handler.py::confirm_preparation): "vysunutá"
        karta sa zasunie späť do ruky a namiesto nej sa ukáže bublina
        "Svietim zeleného/žaluďového" pre každého, kto v tomto kole
        vysvietil (hráč aj Počítač 1, ktorý má svojho zeleného horníka
        vysvieteného od začiatku — pozri __init__)."""
        self.declaration_confirmed = True
        if Card("acorn", "over") in self.illuminated_cards:
            self.speech_bubble.show_bid(0, "Svietim žaluďového!")
        if self.players[1].illuminated_leaf:
            self.speech_bubble.show_bid(1, "Svietim zeleného!")
        self._advance_phase()

    def _start_deal(self):
        """Spustí skutočnú DealAnimation pre bod 'Rozdanie'."""
        if self.deal_animation is None:
            self.deal_animation = DealAnimation(self.screen, self.card_renderer)
        self.deal_animation.start(1)  # Počítač 1 rozdáva ako prvému (rovnaký líder ako v ukážke štichu)
        self.dealing = True

    def _start_trick_collect(self):
        """Spustí animáciu zberu štichu k skutočnému víťazovi (podľa
        pravidiel — najvyššia karta v hranej farbe)."""
        winner = self.trick.get_winner_index()
        self.trick_animation.start(self.trick.played_cards, winner)
        self.collecting_trick = True

    def _finish_trick_collect(self):
        """Po doletení kariet k víťazovi pripíše body, prípadne oznámi
        bublinou koľko bodov víťaz práve získal, a posunie tutoriál ďalej."""
        # Zeleného horníka má Počítač 1 vysvieteného vždy (pozri __init__).
        # Žaluďového horníka vysvieti hráč sám, interaktívne.
        leaf_illuminated = self.players[1].illuminated_leaf
        acorn_illuminated = Card("acorn", "over") in self.illuminated_cards
        winner = self.trick.get_winner_index()
        points_this_trick = sum(
            card.get_points(leaf_illuminated, acorn_illuminated)
            for _, card in self.trick.played_cards
        )
        self.players[winner].add_trick(
            self.trick.get_all_cards(),
            leaf_illuminated=leaf_illuminated,
            acorn_illuminated=acorn_illuminated,
        )
        self.completed_tricks.append((list(self.trick.played_cards), winner))
        self.trick.played_cards = []
        self.collecting_trick = False
        if points_this_trick > 0:
            self.speech_bubble.show_round_result(
                winner, points_this_trick, is_bidder=False
            )

        step = self._current_step()
        # (show_round_status sa zapína pri vstupe do "trick2_collect" —
        # pozri _enter_step — až po tomto pripísaní bodov, nie skôr.)
        if step is not None and step.get("key") == "trick6":
            self.trick6_winner = winner
        if (step is not None and step.get("key") == "trick7"
                and self.trick6_winner == 0):
            self.branch_b_trick7_winner = winner
        if step is not None and step.get("round_end"):
            self._finalize_round()
        self._enter_step(self.step_index + 1)

    def _finalize_round(self):
        """Uzavrie odohrané kolo (rovnako ako Round.score_round v reálnej
        hre) — pripíše skóre, aktualizuje sériu bez trestných bodov a
        zapíše nový riadok do Chujogramu."""
        leaf_illuminated = self.players[1].illuminated_leaf
        acorn_illuminated = Card("acorn", "over") in self.illuminated_cards
        for player in self.players:
            points = player.finalize_round(
                all_penalty_taken=False,
                leaf_illuminated=leaf_illuminated,
                acorn_illuminated=acorn_illuminated,
            )
            player.update_streak(actual_points=max(0, points))

        self.round_scores_history.append([p.total_score for p in self.players])
        scores = [p.total_score for p in self.players]
        max_score = max(scores)
        if all(s == max_score for s in scores):
            self.bullet_history.append([0] * len(self.players))
        else:
            self.bullet_history.append(
                [1 if s == max_score else 0 for s in scores]
            )

    # ------------------------------------------------------------------
    # Udalosti
    # ------------------------------------------------------------------

    def _handle_click(self, pos: tuple[int, int]):
        # Overlay "Posledný štich" (rovnaké správanie ako v ostrej hre —
        # gui/screen.py): kým je otvorený, ktorýkoľvek klik ho len zavrie
        # a nič iné nevykoná.
        if self.show_last_trick:
            self.show_last_trick = False
            return

        if self.skip_button.collidepoint(pos):
            # Preskočí len TÚTO kapitolu — orchestrátor (tutorial_main.py)
            # podľa exit_action == "advance" pokračuje ďalšou kapitolou.
            self.finished = True
            self.exit_action = "advance"
            return

        if (self.completed_tricks
                and PhaseRenderer._button_last_trick_rect().collidepoint(pos)):
            self.show_last_trick = True
            self.last_trick_viewed = True
            return

        if (self.chujogram_revealed
                and PhaseRenderer._button_chujogram_rect().collidepoint(pos)):
            self.chujogram.toggle()
            step = self._current_step()
            if (self.chujogram.visible
                    and step is not None
                    and step.get("key") == "chujogram_wait"):
                self._enter_step(self.step_index + 1)
            return

        step = self._current_step()
        if step is None:
            return

        if step["kind"] == "trick":
            if not self.trick_human_card_played:
                # Kým ešte dobiehajú karty počítačov PRED hráčom
                # (pre_human), klik na ruku sa neprijíma.
                if self.pending_auto_plays or self.card_throw_animation.in_flight:
                    return
                clicked = self.card_renderer.get_clicked_card(
                    pos, self.players[0].hand.cards, 0
                )
                choices = step["human_card"]
                if not isinstance(choices, list):
                    choices = [choices]
                if clicked is not None and clicked in choices:
                    self._play_card(0, clicked)
                    self.trick_human_played_card = clicked
                    self.trick_human_card_played = True
                    self._queue_auto_plays(step.get("post_human", []))
                return
            if not self.trick_step_human_played:
                # Karty počítačov PO hráčovi ešte dolietavajú na stôl.
                return
            if self.next_button.collidepoint(pos):
                # Žiadny samostatný "_collect" krok medzi štichmi
                # neexistuje — Ďalej po odohratí štichu rovno spustí
                # jeho zber k víťazovi.
                self._start_trick_collect()
            return

        if step["kind"] == "human_play":
            clicked = self.card_renderer.get_clicked_card(
                pos, self.players[0].hand.cards, 0
            )
            if clicked == step["card"]:
                self._play_card(0, step["card"])
                self._enter_step(self.step_index + 1)
            return

        if step["kind"] == "phase_list":
            phase = step["phases"][self.phase_index]

            if phase["key"] == "zavazok":
                if PhaseRenderer._button_decl_all_rect().collidepoint(pos):
                    self.active_declaration = (
                        None if self.active_declaration == "all" else "all"
                    )
                    return
                if PhaseRenderer._button_decl_none_rect().collidepoint(pos):
                    self.active_declaration = (
                        None if self.active_declaration == "none" else "none"
                    )
                    return
                if PhaseRenderer._button_ok_rect().collidepoint(pos):
                    self._confirm_preparation()
                    return

            if phase["key"] == "vysvietenie":
                clicked_card = self.card_renderer.get_clicked_card(
                    pos, self.players[0].hand.cards, 0
                )
                if clicked_card is not None and (
                        clicked_card.is_leaf_over or clicked_card.is_acorn_over):
                    if clicked_card in self.illuminated_cards:
                        self.illuminated_cards.remove(clicked_card)
                    else:
                        self.illuminated_cards.append(clicked_card)
                    self.illumination_interacted = True
                    return

            if self.next_button.collidepoint(pos):
                if phase.get("action") == "deal":
                    self._start_deal()
                else:
                    self._advance_phase()
            return

        # "text" / "ai_play" / "result" — pokračuje sa tlačidlom Ďalej
        if self.next_button.collidepoint(pos):
            if step.get("action") == "collect_trick":
                self._start_trick_collect()
                return
            if self.step_index + 1 >= len(STEPS):
                # Prirodzený koniec (Dokončiť na poslednom kroku) —
                # rovnako ako Preskočiť posunie orchestrátora na ďalšiu
                # kapitolu (pozri exit_action v __init__).
                self.finished = True
                self.exit_action = "advance"
            else:
                self._enter_step(self.step_index + 1)

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        if self.dealing:
            # Kým prebieha rozdanie, kreslenie plne preberá DealAnimation
            # (vlastné pozadie aj karty rubom).
            self.deal_animation.draw(self.bg)
            return

        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill(COLOR_BG)

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 90))
        self.screen.blit(overlay, (0, 0))

        step = self._current_step()
        trick_ready_for_human = (
            step is not None and step["kind"] == "trick"
            and not self.trick_human_card_played
            and not self.pending_auto_plays
            and not self.card_throw_animation.in_flight
        )
        is_human_turn = step is not None and (
            step["kind"] == "human_play" or trick_ready_for_human
        )
        current_phase = (
            step["phases"][self.phase_index]
            if step is not None and step["kind"] == "phase_list" else None
        )

        if self.cards_dealt:
            for i, player in enumerate(self.players):
                # Rovnaký mechanizmus ako v ostrej hre (gui/screen.py):
                # vysvietená karta v ruke ktoréhokoľvek hráča (nielen
                # človeka) sa kreslí lícom namiesto rubom, kým ju
                # nezahrá — nie iba počas kroku "Vysvietenie".
                if player.is_human:
                    # Kým sa vysvietenie/záväzok nepotvrdí tlačidlom OK
                    # (krok Záväzok), karta je "vysunutá" z ruky — presne
                    # ako v ostrej hre (gui/screen.py::_draw_hands,
                    # self.selected_illumination). Po potvrdení sa
                    # _confirm_preparation() postará o zasunutie späť.
                    illumination = [] if self.declaration_confirmed else self.illuminated_cards
                else:
                    illumination = []
                    if player.illuminated_leaf:
                        illumination += [c for c in player.hand.cards if c.is_leaf_over]
                    if player.illuminated_acorn:
                        illumination += [c for c in player.hand.cards if c.is_acorn_over]
                self.card_renderer.draw_hand(
                    cards=player.hand.cards,
                    player_index=i,
                    is_human=player.is_human,
                    selected_cards=[],
                    highlight_playable=(is_human_turn and i == 0),
                    lead_suit=self.trick.lead_suit if (is_human_turn and i == 0) else None,
                    trick_number=1,
                    selected_illumination=illumination,
                )

        if not self.collecting_trick:
            self.card_renderer.draw_trick(
                self.trick,
                exclude_players=set(self.card_throw_animation.in_flight.keys())
            )
        self.card_throw_animation.draw()
        self.trick_animation.draw()

        # Tlačidlá záväzku + OK — presne na pozíciách z reálnej hry
        # (PhaseRenderer). Ukazujeme ich pri Vysvietení aj Záväzku, lebo v
        # ostrej hre sú súčasťou tej istej obrazovky — počas Vysvietenia sú
        # však len zašednuté (nie ešte klikateľné), aby nepôsobili ako
        # skratka predbiehajúca vlastný krok Záväzok.
        if current_phase is not None and current_phase["key"] in ("vysvietenie", "zavazok"):
            self._draw_prep_buttons(disabled=(current_phase["key"] == "vysvietenie"))

        if step is not None and step["kind"] == "penalty_overview":
            self._draw_penalty_overview_cards()

        if self.show_round_status:
            self.round_status.draw(self.players, None)

        if self.completed_tricks:
            self._draw_last_trick_button()

        if self.chujogram_revealed:
            self._draw_chujogram_button()
            self.chujogram.draw(self.bullet_history, self.round_scores_history)

        self.speech_bubble.draw()

        self._draw_title_bar()
        self._draw_panel()

        if self.show_last_trick:
            self._draw_last_trick_overlay()

    def _draw_chujogram_button(self):
        """Nakreslí skutočne klikateľné tlačidlo Chujogramu, presne na
        rovnakej pozícii ako v reálnej hre (gui/phase_renderer.py)."""
        rect = PhaseRenderer._button_chujogram_rect()
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*COLOR_BUTTON_SECONDARY, 240 if is_hover else 200))
        self.screen.blit(overlay, rect.topleft)
        border_color = COLOR_WHITE if is_hover else COLOR_GOLD
        pygame.draw.rect(
            self.screen, border_color, rect, width=2, border_radius=BUTTON_RADIUS
        )
        text_surf = self.font_medium.render("Chujogram", True, COLOR_WHITE)
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def _draw_last_trick_button(self):
        """Nakreslí skutočne klikateľné tlačidlo Posledný štich, presne
        na rovnakej pozícii ako v reálnej hre (gui/phase_renderer.py) —
        objaví sa, len čo existuje aspoň jeden odohraný štich (teda od
        trick2 ďalej)."""
        rect = PhaseRenderer._button_last_trick_rect()
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*COLOR_BUTTON_SECONDARY, 240 if is_hover else 200))
        self.screen.blit(overlay, rect.topleft)
        border_color = COLOR_WHITE if is_hover else COLOR_GOLD
        pygame.draw.rect(
            self.screen, border_color, rect, width=2, border_radius=BUTTON_RADIUS
        )
        text_surf = self.font_medium.render("Posledný štich", True, COLOR_WHITE)
        self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def _draw_last_trick_overlay(self):
        """Nakreslí overlay s posledným odohraným štichom — rovnaká
        mechanika ako v ostrej hre (gui/screen.py::_draw_last_trick_overlay),
        len nad self.completed_tricks namiesto game_state.current_round.tricks."""
        if not self.completed_tricks:
            self.show_last_trick = False
            return

        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 200))
        self.screen.blit(dark, (0, 0))

        played, winner_index = self.completed_tricks[-1]

        card_w, card_h = CARD_SIZE_MEDIUM
        gap = 30
        total_w = len(played) * (card_w + gap) - gap
        x0 = SCREEN_WIDTH // 2 - total_w // 2
        y0 = SCREEN_HEIGHT // 2 - card_h // 2 - 40

        title = self.font_large.render("POSLEDNÝ ŠTICH", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(
            centerx=SCREEN_WIDTH // 2, top=y0 - 60
        ))

        for player_idx, card in played:
            i = [p for p, _ in played].index(player_idx)
            cx = x0 + i * (card_w + gap)
            is_winner = (player_idx == winner_index)

            img = self.card_renderer._get_card_image(card)
            self.screen.blit(img, (cx, y0))

            border_color = COLOR_GOLD if is_winner else COLOR_GRAY
            border_width = 3 if is_winner else 1
            pygame.draw.rect(
                self.screen, border_color, (cx, y0, card_w, card_h),
                width=border_width, border_radius=6
            )

            name = self.players[player_idx].name
            name_surf = self.font_medium.render(
                name, True, COLOR_GOLD if is_winner else COLOR_WHITE
            )
            self.screen.blit(name_surf, name_surf.get_rect(
                centerx=cx + card_w // 2, top=y0 + card_h + 8
            ))

        hint = self.font_small.render(
            "Klikni kdekoľvek pre zatvorenie", True, COLOR_GRAY
        )
        self.screen.blit(hint, hint.get_rect(
            centerx=SCREEN_WIDTH // 2, top=y0 + card_h + 50
        ))

    def _draw_penalty_overview_cards(self):
        """Nakreslí riadok trestných kariet (s bodovou hodnotou) pre úvodný
        krok "penalty_overview" — v strede stola, ktorý je v tejto chvíli
        (pred rozdaním) úplne prázdny. Karty centrujeme na TABLE_CENTER_X
        vo veľkosti CARD_SIZE_MEDIUM (rovnaká veľkosť ako karty v ruke),
        aby boli dobre čitateľné. Zvislo sa riadok drží pod spodným
        okrajom bočného panelu (self.last_panel_bottom — dopočítaný pri
        predošlom vykreslení panelu pre tento krok), takže sa s ním
        nemôže prekryť pri žiadnom rozlíšení obrazovky ani dĺžke textu."""
        step = self._current_step()
        if step is None or "cards" not in step:
            return
        cards = step["cards"]
        if not cards:
            return

        card_w, card_h = CARD_SIZE_MEDIUM
        gap = 50
        total_w = len(cards) * card_w + (len(cards) - 1) * gap
        x0 = TABLE_CENTER_X - total_w // 2

        # Tmavý polopriehľadný podklad za celým riadkom kariet (rovnaký
        # štýl ako bočný panel) — na drevenej textúre stola by inak
        # popisy pod kartami takmer zanikli, presne ako na pripomienkovanom
        # screenshote. Podklad (nie len samotné karty) musí zostať pod
        # spodným okrajom bočného panelu — preto sa medzera počíta k
        # bg_rect.top, nie k y0 kariet.
        #
        # Zámerne NEukazujeme hodnotu pri vysvietení (napr. "16b
        # vysvietený") — v tomto úvodnom prehľade by hráča mýlila skôr,
        # než by pomohla; vysvietenie sa vysvetľuje až vo vlastnom kroku
        # neskôr.
        block_h = card_h + 10 + 22 + 30  # karta + popis + body
        pad_x, pad_top, pad_bottom = 40, 50, 20
        panel_bottom_hint = getattr(self, "last_panel_bottom", 90 + 260)
        min_y0 = panel_bottom_hint + pad_top + 30
        y0 = max(TABLE_CENTER_Y - card_h // 2 - 20, min_y0, 130 + pad_top)
        y0 = min(y0, self.panel_max_bottom - block_h)

        bg_rect = pygame.Rect(
            x0 - pad_x, y0 - pad_top,
            total_w + 2 * pad_x, block_h + pad_top + pad_bottom
        )
        backdrop = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        backdrop.fill((*COLOR_PANEL_BG, 235))
        self.screen.blit(backdrop, bg_rect.topleft)
        pygame.draw.rect(
            self.screen, COLOR_GOLD, bg_rect, width=2, border_radius=14
        )
        heading = self.font_small.render("TRESTNÉ KARTY", True, COLOR_GOLD)
        self.screen.blit(heading, heading.get_rect(
            centerx=bg_rect.centerx, top=bg_rect.top + 14
        ))

        for i, (card, label, points) in enumerate(cards):
            cx = x0 + i * (card_w + gap)
            img = self.card_renderer._get_card_image(card, size="medium")
            self.screen.blit(img, (cx, y0))
            pygame.draw.rect(
                self.screen, COLOR_GOLD, (cx, y0, card_w, card_h),
                width=2, border_radius=6
            )

            ty = y0 + card_h + 10
            for line in self._wrap_text(label, self.font_small, card_w + 30):
                surf = self.font_small.render(line, True, COLOR_WHITE)
                self.screen.blit(surf, surf.get_rect(centerx=cx + card_w // 2, top=ty))
                ty += 22

            points_surf = self.font_medium.render(points, True, COLOR_GOLD)
            self.screen.blit(
                points_surf, points_surf.get_rect(centerx=cx + card_w // 2, top=ty)
            )

    def _draw_prep_buttons(self, disabled: bool = False):
        """Nakreslí tlačidlá záväzku + OK, presne na rovnakých pozíciách a
        so správaním ako v reálnej hre (gui/phase_renderer.py). Keď
        "disabled" je True (krok Vysvietenie, pred krokom Záväzok), tlačidlá
        sa vykreslia viditeľne zašednuté a neklikateľné — zodpovedajúci
        _handle_click ich klik v tomto kroku ignoruje."""
        mouse_pos = pygame.mouse.get_pos()

        def draw_one(rect, label, color):
            is_hover = (not disabled) and rect.collidepoint(mouse_pos)
            overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            if disabled:
                overlay.fill((*COLOR_BUTTON_SECONDARY, 90))
            else:
                overlay.fill((*color, 240 if is_hover else 200))
            self.screen.blit(overlay, rect.topleft)
            if disabled:
                border_color = COLOR_GRAY
            else:
                border_color = COLOR_WHITE if is_hover else COLOR_GOLD
            pygame.draw.rect(
                self.screen, border_color, rect, width=2, border_radius=BUTTON_RADIUS
            )
            text_color = COLOR_GRAY if disabled else COLOR_WHITE
            text_surf = self.font_medium.render(label, True, text_color)
            self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

        color_all = (COLOR_BUTTON_PRIMARY if self.active_declaration == "all"
                     else COLOR_BUTTON_SECONDARY)
        draw_one(PhaseRenderer._button_decl_all_rect(), "Beriem všetko  [-20b]", color_all)

        color_none = (COLOR_BUTTON_PRIMARY if self.active_declaration == "none"
                      else COLOR_BUTTON_SECONDARY)
        draw_one(PhaseRenderer._button_decl_none_rect(), "Nechytím nič  [-10b]", color_none)

        draw_one(PhaseRenderer._button_ok_rect(), "OK", COLOR_BUTTON_PRIMARY)

    def _draw_title_bar(self):
        banner_h = 80
        banner = pygame.Surface((SCREEN_WIDTH, banner_h), pygame.SRCALPHA)
        banner.fill((0, 0, 0, 190))
        self.screen.blit(banner, (0, 0))
        pygame.draw.line(
            self.screen, COLOR_GOLD, (0, banner_h), (SCREEN_WIDTH, banner_h), width=1
        )

        title = self.font_large.render("TUTORIÁL — PRIEBEH KOLA", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(centerx=SCREEN_WIDTH // 2, top=24))

        overlay = pygame.Surface(
            (self.skip_button.width, self.skip_button.height), pygame.SRCALPHA
        )
        overlay.fill((*COLOR_BUTTON_SECONDARY, 220))
        self.screen.blit(overlay, self.skip_button.topleft)
        pygame.draw.rect(
            self.screen, COLOR_GOLD, self.skip_button,
            width=2, border_radius=BUTTON_RADIUS
        )
        label = self.font_small.render("Preskočiť", True, COLOR_WHITE)
        self.screen.blit(label, label.get_rect(center=self.skip_button.center))

    def _draw_panel(self):
        step = self._current_step()
        if step is None:
            return

        # Panel je pri ľavom okraji (pozri self.panel_max_right/_bottom v
        # __init__ — dôvod, prečo nie je navrchu). Keď je odhalený
        # Chujogram (ten zaberá vlastný pás naľavo), panel s textom
        # posunieme až za neho.
        px = (self.chujogram.panel_w + 20) if self.chujogram_revealed else 20
        py = 90
        panel_w = max(400, min(650, self.panel_max_right - px))
        inner_w = panel_w - 60

        is_phase_list = step["kind"] == "phase_list"
        is_trick = step["kind"] == "trick"
        is_bullets = step["kind"] == "bullets"
        phase = step["phases"][self.phase_index] if is_phase_list else None

        # Pri kroku "trick" sa text prepne na "text_after" hneď ako hráč
        # zahrá svoju kartu (trick_human_card_played) — nečaká sa, kým
        # dolietajú aj karty počítačov PO ňom (trick_step_human_played),
        # aby text nezaostával za tým, čo sa práve deje.
        trick_played = self.trick_human_card_played if is_trick else False

        if is_phase_list:
            phase_text = phase["text"]
            if (phase["key"] == "vysvietenie"
                    and Card("acorn", "over") in self.illuminated_cards):
                phase_text = phase.get("text_after", phase["text"])
        elif is_trick:
            if trick_played:
                by_card = step.get("text_after_by_card")
                text_after_fn = step.get("text_after_fn")
                if by_card is not None and self.trick_human_played_card is not None:
                    key = (
                        self.trick_human_played_card.suit,
                        self.trick_human_played_card.rank,
                    )
                    phase_text = by_card.get(key, step["text_after"])
                elif text_after_fn is not None:
                    phase_text = text_after_fn(self)
                else:
                    phase_text = step["text_after"]
            else:
                phase_text = step["text_before"]
        elif is_bullets:
            phase_text = ""
        else:
            text_fn = step.get("text_fn")
            phase_text = text_fn(self) if text_fn is not None else step["text"]

        instruction_text = None
        if step["kind"] == "human_play":
            instruction_text = step["instruction"]
        elif is_trick and not trick_played:
            instruction_text = step["human_instruction"]
        elif is_phase_list:
            if phase["key"] == "vysvietenie" and Card("acorn", "over") in self.illuminated_cards:
                # Karta je už vysvietená — ponúkni dobrovoľnú inštrukciu
                # (zrušiť/pokračovať), tiež zlatou farbou.
                instruction_text = phase.get("instruction_after")
            else:
                instruction_text = phase.get("instruction")
        elif step.get("instruction"):
            instruction_text = step["instruction"]

        # Tlačidlo Ďalej sa neukazuje, kým hráč nevykoná skutočnú akciu,
        # ktorú mu zlatá inštrukcia práve prikazuje: klik na kartu
        # (human_play/trick), klik na horníka (vysvietenie), klik na
        # Chujogram (chujogram_wait), otvorenie Posledného štichu
        # (requires_last_trick_view), alebo v kroku Záväzok, kde sa má
        # pokračovať výhradne tlačidlom OK (nie Ďalej — nech sa hráč
        # naučí, že práve OK potvrdzuje rozhodnutie). Pri "trick" navyše
        # čaká aj na doletenie kariet počítačov po hráčovi
        # (trick_step_human_played).
        hide_button = (
            step["kind"] == "human_play"
            or (is_trick and not self.trick_step_human_played)
            or step.get("key") == "chujogram_wait"
            or (is_phase_list and phase["key"] == "zavazok")
            or (is_phase_list and phase["key"] == "vysvietenie"
                and not self.illumination_interacted)
            or (step.get("requires_last_trick_view") and not self.last_trick_viewed)
        )

        label_count = len(step["phases"]) if is_phase_list else 0

        title_text = step.get("title")

        def layout(font, line_h, label_line_h):
            if is_bullets:
                lines = self._wrap_bullet_lines(step["bullets"], font, inner_w)
            else:
                lines = self._wrap_paragraphs(phase_text, font, inner_w)
            instruction_lines = (
                self._wrap_text(instruction_text, font, inner_w)
                if instruction_text else []
            )
            content_h = label_count * label_line_h
            if label_count:
                content_h += 14  # medzera medzi zoznamom bodov a textom
            if title_text:
                content_h += line_h + 10  # nadpis + medzera pred obsahom
            content_h += (len(lines) + len(instruction_lines)) * line_h
            # Text vždy začína na py+46. Keď je tlačidlo, treba preň
            # vyhradiť extra miesto POD textom (medzera + výška tlačidla +
            # spodný okraj).
            panel_h = 46 + content_h + (20 + 46 + 16 if not hide_button else 24)
            return lines, instruction_lines, content_h, panel_h

        # Panel nesmie nikdy zasiahnuť ani do stredu stola, ani do ruky
        # hráča dole (pozri self.panel_max_bottom v __init__) — ak sa
        # text pri bežnom (stredne veľkom) písme nezmestí, prepneme na
        # menšie písmo namiesto toho, aby panel rástol ďalej dole. Bez
        # umelého spodného stropu na available_h — inak by táto hranica
        # kontrolu nižšie (panel_h > available_h) obišla.
        available_h = self.panel_max_bottom - py
        lines, instruction_lines, content_h, panel_h = layout(
            self.font_medium, 32, 30
        )
        body_font, line_h = self.font_medium, 32
        if panel_h > available_h:
            lines, instruction_lines, content_h, panel_h = layout(
                self.font_small, 24, 24
            )
            body_font, line_h = self.font_small, 24
        panel_h = min(panel_h, available_h)
        self.last_panel_bottom = py + panel_h  # pre diagnostiku/testy

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*COLOR_PANEL_BG, 235))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(
            self.screen, COLOR_GOLD, (px, py, panel_w, panel_h),
            width=2, border_radius=14
        )

        step_no = min(self.step_index + 1, len(STEPS))
        counter = self.font_small.render(
            f"Krok {step_no}/{len(STEPS)}", True, COLOR_GRAY
        )
        self.screen.blit(counter, (px + 20, py + 14))

        ty = py + 46

        if is_phase_list:
            label_line_h = 30 if body_font is self.font_medium else 24
            for p in step["phases"]:
                color = COLOR_GOLD if p is phase else COLOR_GRAY
                surf = body_font.render(p["label"], True, color)
                self.screen.blit(surf, (px + 30, ty))
                ty += label_line_h
            ty += 14

        if title_text:
            title_surf = body_font.render(title_text, True, COLOR_GOLD)
            self.screen.blit(title_surf, (px + 30, ty))
            ty += line_h + 10

        for line in lines:
            surf = body_font.render(line, True, COLOR_WHITE)
            self.screen.blit(surf, (px + 30, ty))
            ty += line_h

        for line in instruction_lines:
            surf = body_font.render(line, True, COLOR_GOLD)
            self.screen.blit(surf, (px + 30, ty))
            ty += line_h

        if hide_button:
            self.next_button = pygame.Rect(0, 0, 0, 0)  # neaktívne v tomto kroku
        else:
            if is_phase_list and phase.get("action") == "deal":
                label_text = "Rozdať karty →"
            elif step["kind"] == "result":
                label_text = "Dokončiť"
            else:
                label_text = "Ďalej →"
            text_surf = self.font_medium.render(label_text, True, COLOR_WHITE)
            btn_w = text_surf.get_width() + 50
            btn_h = 46
            self.next_button = pygame.Rect(
                px + panel_w - btn_w - 20, py + panel_h - btn_h - 16, btn_w, btn_h
            )
            overlay = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
            overlay.fill((*COLOR_BUTTON_PRIMARY, 230))
            self.screen.blit(overlay, self.next_button.topleft)
            pygame.draw.rect(
                self.screen, COLOR_GOLD, self.next_button,
                width=2, border_radius=BUTTON_RADIUS
            )
            self.screen.blit(
                text_surf, text_surf.get_rect(center=self.next_button.center)
            )

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split(" ")
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _wrap_paragraphs(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """Ako _wrap_text, ale rešpektuje odstavce oddelené dvojitým novým
        riadkom ("\\n\\n") v zdrojovom texte — medzi odstavcami vloží
        prázdny riadok. Vďaka tomu texty s viacerými udalosťami za sebou
        (napr. "Počítač 2 hrá...", "Počítač 3 hrá...") pôsobia prehľadnejšie
        než jeden súvislý blok."""
        paragraphs = text.split("\n\n")
        lines: list[str] = []
        for i, para in enumerate(paragraphs):
            if i > 0:
                lines.append("")
            lines.extend(TutorialScreen._wrap_text(para, font, max_width))
        return lines

    def _wrap_bullet_lines(
        self, bullets: list[str], font: pygame.font.Font, max_width: int
    ) -> list[str]:
        """Rozdelí zoznam krátkych viet na riadky s odrážkou na začiatku
        každej vety a odsadením na pokračovacích riadkoch — výsledok sa dá
        vykresliť tou istou slučkou ako riadky z _wrap_text."""
        marker, indent = "•  ", "   "
        marker_w = font.size(marker)[0]
        lines: list[str] = []
        for bullet in bullets:
            wrapped = self._wrap_text(bullet, font, max_width - marker_w)
            for i, line in enumerate(wrapped):
                prefix = marker if i == 0 else indent
                lines.append(f"{prefix}{line}")
        return lines

    def __repr__(self) -> str:
        return f"TutorialScreen(step={self.step_index}/{len(STEPS)})"
