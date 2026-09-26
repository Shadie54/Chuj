# gui/screen.py

import pygame, random
from game.game_state import GameState
from game.ai import AI
from gui.card_renderer import CardRenderer
from gui.scoreboard import Scoreboard
from gui.deal_animation import DealAnimation
from gui.trick_animation import TrickAnimation
from gui.card_throw_animation import CardThrowAnimation
from gui.speech_bubble import SpeechBubble
from gui.info_overlay import InfoOverlay
from gui.chujogram_panel import ChujogramPanel
from gui.round_status import RoundStatus
from gui.phase_renderer import PhaseRenderer
from gui.preparation_handler import PreparationHandler
from gui.tip_panel import TipPanel
from game.advisor import Advisor
from game.stats_collector import StatsCollector
from game import profile as profile_store
from game import savegame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, DEBUG_MODE,
    COLOR_BG,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE, FONT_SIZE_SMALL,
    get_font, CARD_SIZE_MEDIUM, COLOR_GOLD, COLOR_GRAY, COLOR_WHITE,
    TIP_PANEL_X
)


class Screen:
    def __init__(self, game_state: GameState, ai_players: list,
                 debug: bool = DEBUG_MODE, new_game: bool = True, settings=None):
        pygame.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Chuj")

        self.settings = settings or {}
        bg_file = self.settings.get("table_bg", "table.jpg")
        try:
            self.table_bg = pygame.image.load(
                f"assets/graphics/{bg_file}"
            ).convert()
            self.table_bg = pygame.transform.scale(
                self.table_bg, (SCREEN_WIDTH, SCREEN_HEIGHT)
            )
        except FileNotFoundError:
            self.table_bg = None

        self.pending_risk_play: tuple | None = None  # (player_index, card, ai)
        self.risk_bubble_timer: int = 0

        self.clock = pygame.time.Clock()
        self.debug = debug
        self.new_game = new_game

        self.game_state = game_state
        self.ai_players = ai_players

        self.card_renderer = CardRenderer(self.screen, debug)
        self.scoreboard = Scoreboard(self.screen)
        self.speech_bubble = SpeechBubble(self.screen)
        self.info_overlay = InfoOverlay(self.screen)

        self.phase_renderer = PhaseRenderer(self.screen, self)
        self.preparation_handler = PreparationHandler(self)

        self.font_small = get_font( FONT_SIZE_SMALL)
        self.font_medium = get_font( FONT_SIZE_MEDIUM)
        self.font_large = get_font( FONT_SIZE_LARGE)

        # štich stav
        self.trick_waiting: bool = False
        self.trick_display_timer: int = 0
        self._trick_anim_started: bool = False
        self.trick_animation = TrickAnimation(self.screen, self.card_renderer)
        self.card_throw_animation = CardThrowAnimation(self.screen, self.card_renderer)

        # Rýchlosť animácií — spoločný násobok z nastavení (nastavuje sa
        # v SettingsScreen), aplikovaný na základnú card_speed oboch tried.
        # DealAnimation zámerne nie je ovplyvnená.
        # TrickAnimation (zber štichu k víťazovi) sa smie zrýchliť nad 1.0x,
        # ale nikdy sa nespomalí pod základnú (1.0x) rýchlosť — pri nižšej
        # hodnote slidera by bola cesta ku vzdialenejším súperom nepríjemne
        # pomalá. CardThrowAnimation reaguje na celý rozsah 0.5x–2.0x.
        anim_speed_mult = self.settings.get("animation_speed", 1.0)
        trick_speed_mult = max(anim_speed_mult, 1.0)
        self.trick_animation.card_speed *= trick_speed_mult
        self.card_throw_animation.card_speed *= anim_speed_mult

        # Deal animácia
        self.deal_animation: DealAnimation | None = None
        self.dealing: bool = False

        # Game over
        self.game_over_timer: int = 0
        self.next_round_timer: int = 0

        # Správy
        self.message: str = ""
        self.message_timer: int = 0

        # Fáza záväzku a vysvietenia
        self.declaration_index: int = 0     # kto práve vyhlasuje záväzok
        self.revealing_index: int = 0       # kto práve vysvecuje

        # Karta pre tromf — nie je v Chuji
        self.selected_card = None

        self.waiting_for_ai: bool = False
        self.running: bool = True

        # Preparation fáza
        self.selected_illumination: list = []  # vybrané karty na vysvietenie
        self.active_declaration: str | None = None  # "all" / "none" / None
        self.preparation_done: bool = False

        self.chujogram = ChujogramPanel(
            self.screen,
            [p.name for p in game_state.players]
        )

        self.round_status = RoundStatus(self.screen)

        self.sort_ascending = False
        self.declaration_failed_timer: int = 0
        self.show_last_trick = False

        # ------------------------------------------------------------------
        # Tipy od AI (game/advisor.py)
        # ------------------------------------------------------------------
        # Advisor je zámerne MIMO self.ai_players — ten zoznam znamená
        # "kto hrá sám za seba" a hráč tam patriť nemá. Advisor sa preto
        # kŕmi vlastnými volaniami record_* na tých istých miestach, kde
        # sa kŕmia súperi (_start_round, _process_waiting_trick,
        # _reset_trick_state, preparation_handler).
        # Radca žije na GameState (pozri komentár tam) — pri návrate do
        # rozohratej hry musí mať pamäť toho, čo už v kole padlo, inak by
        # radil naslepo. Nový zakladáme len ak ešte žiadny nie je.
        if game_state.human_index >= 0 and game_state.advisor is None:
            game_state.advisor = Advisor(
                game_state.players[game_state.human_index],
                logger=None,   # tipy nezahlcujú herný log
            )
        self.advisor = game_state.advisor
        self.tips_enabled: bool = bool(self.settings.get("tips_enabled", False))
        self.tip_panel = TipPanel(self.screen)
        self.current_tip = None

        # ------------------------------------------------------------------
        # Štatistiky profilu (game/profile.py, game/stats_collector.py)
        # ------------------------------------------------------------------
        # Zberač žije na GameState, nie tu — pozri komentár tam. Ak už
        # existuje (návrat do rozohratej hry cez "Pokračovať"), necháme
        # ho, inak založíme nový.
        if game_state.human_index >= 0 and game_state.stats_collector is None:
            game_state.stats_collector = StatsCollector(game_state.human_index)
        # Aby sa tá istá hra nezapísala dvakrát (koniec hry sa v kóde
        # vyhodnocuje na viacerých miestach) ani sa nezapísala ako
        # nedohratá potom, čo už riadne skončila.
        self._game_recorded = False
        # Kľúč situácie, pre ktorú je current_tip spočítaný — tip sa
        # neprepočítava každú snímku, ale len keď sa zmení štich/ruka.
        self._tip_key = None
        # Chybu v tipoch vypíšeme do konzoly len raz za hru, nech
        # nezaplaví výstup 60× za sekundu (pozri _safe_update_tip).
        self._tip_error_logged = False

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Hlavná herná slučka."""
        pygame.event.clear()
        self.running = True
        self.chujogram.update()
        if self.new_game:
            self._start_round()

        while self.running:
            self.clock.tick(FPS)

            if (self.game_over_timer and
                    pygame.time.get_ticks() >= self.game_over_timer):
                self.running = False
                break

            if (self.next_round_timer and
                    pygame.time.get_ticks() >= self.next_round_timer):
                self.next_round_timer = 0
                self._start_round()

            self._handle_events()

            if self.dealing and self.deal_animation:
                self.deal_animation.update()
                self.deal_animation.draw(self.table_bg)
                self.speech_bubble.draw()
                if self.deal_animation.done:
                    self.dealing = False
                    self.deal_animation = None
                    # Automatické zoradenie po rozdaní
                    self.sort_ascending = False
                    self.game_state.players[
                        self.game_state.human_index
                    ].hand.sort_hand()
            else:
                self._process_waiting_trick()
                self.trick_animation.update()
                self.card_throw_animation.update()
                self._handle_ai_turn()
                self._safe_update_tip()
                self._draw()

            pygame.display.flip()

        # Jediné miesto, kde sa hra uzatvára — slučka sa končí buď
        # dohratou hrou, alebo odchodom hráča (Menu/zavretie okna).
        finished = self.game_state.phase == "game_over"
        if finished:
            self._record_game_result()
            savegame.delete_save()
        else:
            # Rozohratú hru uložíme, nech sa dá dohrať aj po zatvorení
            # programu. Do štatistík ako "nedohratá" sa zapíše až vtedy,
            # keď ju hráč naozaj zahodí novou hrou (pozri main.py) —
            # samotný odchod do menu ešte nič nevzdáva.
            savegame.save_game(self.game_state, self.ai_players)

        if finished:
            return "game_over"
        return "menu"

    # ------------------------------------------------------------------
    # Štart kola
    # ------------------------------------------------------------------

    def _start_round(self):
        """Začne nové kolo."""
        self.game_state.start_new_round()

        # Reset AI pamäte
        for i, ai in enumerate(self.ai_players):
            if ai is not None:
                ai.reset_memory()
                ai.memory.init_with_hand(
                    self.game_state.players[ai.player.index].hand.cards
                )

        # Obtiažnosti sa čítajú z bežiacich AI, nie z nastavení — hráč ich
        # smie prepnúť aj počas hry a zberač si tak všimne, že sa menili.
        if self.game_state.stats_collector is not None:
            self.game_state.stats_collector.note_difficulties(
                self._current_difficulties()
            )

        # Rovnaký reset pre radcu hráča (tipy) — vidí len vlastnú ruku,
        # nič navyše oproti tomu, čo vidí hráč.
        if self.advisor is not None:
            self.advisor.reset_memory()
            self.advisor.init_with_hand(
                self.game_state.players[self.game_state.human_index].hand.cards
            )
            self.current_tip = None
            self._tip_key = None

        # Reset stavov
        self.declaration_index = 0
        self.revealing_index = 0
        self.trick_waiting = False
        self._trick_anim_started = False
        self.card_throw_animation.in_flight = {}

        # Log
        current_round = self.game_state.current_round
        hands = {p.name: p.hand.cards for p in self.game_state.players}
        self.game_state.logger.new_round(
            self.game_state.round_number,
            self.game_state.players[current_round.first_player_index].name,
            hands
        )
        # Deal animácia
        self.deal_animation = DealAnimation(self.screen, self.card_renderer)
        self.deal_animation.start(current_round.first_player_index)
        self.dealing = True

    # ------------------------------------------------------------------
    # Spracovanie udalostí
    # ------------------------------------------------------------------

    def _handle_events(self):
        """Spracuje pygame udalosti."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    self.debug = not self.debug
                    self.card_renderer.debug = self.debug
                if event.key == pygame.K_ESCAPE:
                    if self.show_last_trick:
                        self.show_last_trick = False
                        continue

            if self.dealing and self.deal_animation:
                self.deal_animation.handle_event(event)
                continue

            if self.info_overlay.visible:
                if self.info_overlay.handle_event(event):
                    continue

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self._handle_click(event.pos)

            if self.chujogram.handle_event(event):
                continue

    def _handle_click(self, pos: tuple[int, int]):
        """Spracuje klik myši."""
        # Vždy dostupné tlačidlá
        if self.show_last_trick:
            self.show_last_trick = False
            return
        if self.phase_renderer._button_chujogram_rect().collidepoint(pos):
            self.chujogram.toggle()
            return

        if (self.phase_renderer._button_last_trick_rect().collidepoint(pos) and
                self.game_state.current_round and
                self.game_state.current_round.trick_number > 0):
            self.show_last_trick = not self.show_last_trick
            return

        if self.phase_renderer._button_sort_rect().collidepoint(pos):
            self.sort_ascending = not self.sort_ascending
            self.game_state.players[
                self.game_state.human_index
            ].hand.sort_hand(self.sort_ascending)
            return

        if self.phase_renderer._button_info_rect().collidepoint(pos):
            self.info_overlay.toggle()
            return

        if self.phase_renderer._button_tips_rect().collidepoint(pos):
            self.tips_enabled = not self.tips_enabled
            self.settings["tips_enabled"] = self.tips_enabled
            self._save_tips_setting()
            if not self.tips_enabled:
                self.current_tip = None
                self._tip_key = None
            return

        if self.phase_renderer._button_menu_rect().collidepoint(pos):
            self._reset_trick_state()
            self.running = False
            return

        phase = self.game_state.current_round.phase \
            if self.game_state.current_round else None

        if phase == "preparation":
            self._handle_preparation_click(pos)
        elif phase == "tricks":
            self._handle_tricks_click(pos)

    # ------------------------------------------------------------------
    # Klikanie v jednotlivých fázach
    # ------------------------------------------------------------------
    def _handle_preparation_click(self, pos):
        self.preparation_handler.handle_preparation_click(pos)

    def _handle_tricks_click(self, pos: tuple[int, int]):
        """Spracuje klik počas štichov."""
        if self.trick_waiting:
            return

        current_round = self.game_state.current_round
        player_index = self.game_state.human_index

        if current_round.current_trick is None:
            return

        if current_round.get_current_player_index() != player_index:
            return

        playable = self.game_state.players[player_index].hand.get_playable_cards(
            current_round.current_trick.lead_suit,
            current_round.trick_number,
            declaration_active=current_round.declaration_type is not None
        )

        clicked_card = self.card_renderer.get_clicked_card(
            pos,
            self.game_state.players[player_index].hand.cards,
            player_index
        )

        if not clicked_card:
            return
        if clicked_card not in playable:
            self._show_message("Túto kartu nemôžeš zahrať!")
            return

        throw_start = self.card_renderer.hand_card_center(
            player_index,
            self.game_state.players[player_index].hand.cards,
            clicked_card
        )
        success = current_round.play_card(player_index, clicked_card)
        if success:
            self.card_throw_animation.start(player_index, clicked_card, throw_start)
            if current_round.current_trick.is_complete:
                self.trick_waiting = True
                self.trick_display_timer = pygame.time.get_ticks() + 1500

    # ------------------------------------------------------------------
    # AI ťahy
    # ------------------------------------------------------------------

    def _handle_ai_turn(self):
        if self.dealing:
            return
        if self.trick_waiting:
            return
        if self.card_throw_animation.in_flight:
            # Nechaj doletieť kartu vo vzduchu — inak ďalšie AI (a jeho
            # blokujúci delay() nižšie) zamrazí slučku skôr, než sa táto
            # animácia stihne prehrať cez viac snímok.
            return

        current_round = self.game_state.current_round
        if not current_round:
            return

        # Čakáme na vypršanie risk bubliny
        if self.pending_risk_play:
            if pygame.time.get_ticks() >= self.risk_bubble_timer:
                player_index, card, ai = self.pending_risk_play
                self.pending_risk_play = None
                self._commit_ai_card(player_index, card)
            return

        phase = current_round.phase
        if phase == "tricks":
            if not self.game_state.is_human_turn:
                current_index = current_round.get_current_player_index()
                ai = self.ai_players[current_index]
                if ai:
                    pygame.time.delay(500)
                    self._ai_play_card(current_index, ai)

    def _ai_play_card(self, player_index: int, ai: AI):
        """AI zahrá kartu."""
        self.waiting_for_ai = True
        current_round = self.game_state.current_round
        player = self.game_state.players[player_index]

        playable = player.hand.get_playable_cards(
            current_round.current_trick.lead_suit,
            current_round.trick_number,
            declaration_active=current_round.declaration_type is not None
        )

        scores = [p.total_score for p in self.game_state.players]
        card = ai.decide_card(
            playable,
            current_round.current_trick,
            current_round.trick_number,
            scores
        )

        # Bublina pre risk — zahranie odložíme o 2 sekundy
        if ai.last_strategy in ("RISK_TRAP", "RISK"):
            texts = ["Risknem to!", "Skúsim šťastie...", "Dúfam že ho nemá..."]
            self.speech_bubble.show_bid(player_index, random.choice(texts), duration_ms=4000)
            self.pending_risk_play = (player_index, card, ai)
            self.risk_bubble_timer = pygame.time.get_ticks() + 2000
            self.waiting_for_ai = False
            return

        self._commit_ai_card(player_index, card)
        self.waiting_for_ai = False

    def _commit_ai_card(self, player_index: int, card):
        """Fyzicky zahrá AI kartu a spracuje koniec štichu."""
        current_round = self.game_state.current_round
        player = self.game_state.players[player_index]
        throw_start = self.card_renderer.hand_card_center(
            player_index, player.hand.cards, card
        )
        current_round.play_card(player_index, card)
        self.card_throw_animation.start(player_index, card, throw_start)

        if current_round.current_trick.is_complete:
            self.trick_waiting = True
            self.trick_display_timer = pygame.time.get_ticks() + 1500

    # ------------------------------------------------------------------
    # Spracovanie štichu
    # ------------------------------------------------------------------

    def _process_waiting_trick(self):
        """Spracuje štich po uplynutí zobrazovacieho času."""

        # Declaration failed timer — ÚPLNE PRVÝ check
        if self.declaration_failed_timer > 0:
            if pygame.time.get_ticks() >= self.declaration_failed_timer:
                self.declaration_failed_timer = 0

                round_points_snapshot = {
                    p.name: p.round_points for p in self.game_state.players
                }
                self.game_state.finish_round()
                sweep_player = self.game_state.last_sweep_player
                results = {}
                for i, player in enumerate(self.game_state.players):
                    results[player.name] = {
                        "round_points": round_points_snapshot[player.name],
                        "total_score": player.total_score,
                        "bullet": player.bullets > 0,
                        "sweep": sweep_player == i
                    }
                self.game_state.logger.log_round_result(results)
                self.game_state.logger.save_round()

                if self.game_state.phase == "game_over":
                    self._show_message(
                        f"{self.game_state.loser.name} prehral!", 5000
                    )
                    self.game_over_timer = pygame.time.get_ticks() + 3000
                else:
                    self.next_round_timer = pygame.time.get_ticks() + 2500
            return  # čakáme alebo sme práve spustili nové kolo

        if not self.trick_waiting:
            return


        current_round = self.game_state.current_round
        if not current_round or not current_round.current_trick:
            self.trick_waiting = False
            return
        if not current_round.current_trick.is_complete:
            self.trick_waiting = False
            return

        if pygame.time.get_ticks() < self.trick_display_timer:
            return

        # Spusti animáciu
        if not self._trick_anim_started:
            winner_index = current_round.current_trick.get_winner_index()
            self.trick_animation.start(
                current_round.current_trick.played_cards,
                winner_index
            )
            self._trick_anim_started = True
            return

        if not self.trick_animation.is_done:
            return

        # Uzavri štich
        self._trick_anim_started = False
        self.trick_waiting = False

        trick = current_round.current_trick
        played = [
            (self.game_state.players[idx].name, card)
            for idx, card in trick.played_cards
        ]
        self.game_state.logger.log_trick(
            current_round.trick_number + 1,
            played,
            self.game_state.players[trick.get_winner_index()].name,
            trick.total_base_points
        )
        winner_index = trick.get_winner_index()

        # Zaznamená do AI pamäte
        for ai in self.ai_players:
            if ai is not None:
                ai.record_trick(
                    trick.played_cards,
                    winner_index,
                    current_round.trick_number
                )
        if self.advisor is not None:
            self.advisor.record_trick(
                trick.played_cards, winner_index, current_round.trick_number
            )

        winner_index = current_round.finish_trick()
        winner_name = self.game_state.players[winner_index].name
        self._show_message(f"{winner_name} vyhral štich!")

        # TODO (nápad z tutoriálu, páčil sa): ukázať tu aj malú červenú
        # bublinu s počtom trestných bodov, ktoré víťaz práve štichom
        # získal (trick.total_base_points), rovnako ako
        # tutorial/tutorial_screen.py::_finish_trick_collect robí cez
        # self.speech_bubble.show_round_result(winner_index,
        # trick.total_base_points, is_bidder=False) — ale len keď
        # trick.total_base_points > 0.

        # Skontroluj zlyhanie záväzku
        if current_round.check_declaration_failed():

            decl_idx = current_round.declaration_player
            if current_round.declaration_type == "none":
                msg = "Nevyšlo! Zobral som štich."
            else:
                msg = "Nevyšlo! Niekto mi zobral štich."
            self.speech_bubble.show_bid(decl_idx, msg)
            self.declaration_failed_timer = pygame.time.get_ticks() + 2000
            current_round.phase = "scoring"  # ← zastav ďalšie štichy

            current_round.phase = "scoring"
            self._handle_declaration_failed()

            return

        if current_round.phase == "scoring":

            # Ulož body PRED finish_round() — len pre log
            round_points_snapshot = {
                p.name: p.round_points for p in self.game_state.players
            }

            self.game_state.finish_round()

            # Log s uloženými hodnotami
            sweep_player = self.game_state.last_sweep_player
            results = {}
            for i, player in enumerate(self.game_state.players):
                results[player.name] = {
                    "round_points": round_points_snapshot[player.name],
                    "total_score": player.total_score,
                    "bullet": player.bullets > 0,
                    "sweep": sweep_player == i
                }
            self.game_state.logger.log_round_result(results)
            self.game_state.logger.save_round()

            if self.game_state.phase == "game_over":
                self._show_message(
                    f"{self.game_state.loser.name} prehral!", 5000
                )
                self.game_over_timer = pygame.time.get_ticks() + 3000
            else:
                self.next_round_timer = pygame.time.get_ticks() + 2500

        else:
            current_round.start_trick()

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        """Nakreslí celú obrazovku."""
        self._draw_table()
        self._draw_hands()
        if not self._trick_anim_started:
            self._draw_current_trick()
        self.card_throw_animation.draw()
        self.trick_animation.draw()
        self.phase_renderer.draw_player_labels()
        self.chujogram.draw(self.game_state.bullet_history,self.game_state.round_scores_history)
        self.round_status.draw(self.game_state.players,self.game_state.current_round)
        self.phase_renderer.draw_buttons()
        # Tip vľavo dole. Chujogram je vysúvací pás cez celú výšku vľavo —
        # ak je (čo i len čiastočne) vysunutý, posunieme panel doprava za
        # jeho pravý okraj, nech sa neprekrývajú.
        if self.current_tip is not None:
            chuj_right = self.chujogram.panel_x + self.chujogram.panel_w
            offset = max(0, int(chuj_right + 20 - TIP_PANEL_X))
            self.tip_panel.draw(self.current_tip, x_offset=offset)
        self.phase_renderer.draw_phase_overlay()
        self.speech_bubble.draw()
        self.phase_renderer.draw_message()
        self.info_overlay.draw()
        if self.show_last_trick:
            self._draw_last_trick_overlay()

    def _draw_table(self):
        """Nakreslí stôl."""
        if self.table_bg:
            self.screen.blit(self.table_bg, (0, 0))
        else:
            self.screen.fill(COLOR_BG)

    def _draw_hands(self):
        """Nakreslí karty všetkých hráčov."""
        current_round = self.game_state.current_round

        for i, player in enumerate(self.game_state.players):
            is_current = (
                    current_round and
                    current_round.phase == "tricks" and
                    current_round.get_current_player_index() == i
            )

            lead_suit = (
                current_round.current_trick.lead_suit
                if current_round and current_round.current_trick
                else None
            )

            # Získaj vysvietené karty pre daného hráča
            if not player.is_human:
                illuminated = []
                if player.illuminated_leaf:
                    illuminated += [c for c in player.hand.cards if c.is_leaf_over]
                if player.illuminated_acorn:
                    illuminated += [c for c in player.hand.cards if c.is_acorn_over]
            else:
                illuminated = self.selected_illumination

            self.card_renderer.draw_hand(
                player.hand.cards,
                player_index=i,
                is_human=player.is_human,
                selected_cards=[],
                highlight_playable=is_current and player.is_human,
                lead_suit=lead_suit,
                selected_illumination=illuminated,
                trick_number=current_round.trick_number if current_round else 0,
                declaration_active=current_round.declaration_type is not None if current_round else False
            )



    def _draw_current_trick(self):
        """Nakreslí karty aktuálneho štichu."""
        current_round = self.game_state.current_round
        if current_round and current_round.current_trick:
            self.card_renderer.draw_trick(
                current_round.current_trick,
                exclude_players=set(self.card_throw_animation.in_flight.keys())
            )

    def _draw_last_trick_overlay(self):
        """Nakreslí overlay s posledným štichom."""
        import os
        from config import CARDS_MEDIUM_PATH, CARD_SIZE_MEDIUM

        tricks = self.game_state.current_round.tricks
        if not tricks:
            self.show_last_trick = False
            return

        # Tmavé pozadie
        dark = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 200))
        self.screen.blit(dark, (0, 0))

        last_trick = tricks[-1]
        winner_index = last_trick.get_winner_index()
        played = last_trick.played_cards  # [(player_idx, card), ...]

        card_w, card_h = CARD_SIZE_MEDIUM
        gap = 30
        total_w = len(played) * (card_w + gap) - gap
        x0 = SCREEN_WIDTH // 2 - total_w // 2
        y0 = SCREEN_HEIGHT // 2 - card_h // 2 - 40

        # Nadpis
        title = self.font_large.render("POSLEDNÝ ŠTICH", True, COLOR_GOLD)
        self.screen.blit(title, title.get_rect(
            centerx=SCREEN_WIDTH // 2, top=y0 - 60
        ))

        for player_idx, card in played:
            i = [p for p, _ in played].index(player_idx)
            cx = x0 + i * (card_w + gap)
            is_winner = (player_idx == winner_index)

            # Karta
            path = os.path.join(CARDS_MEDIUM_PATH, f"{card.suit}-{card.rank}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, CARD_SIZE_MEDIUM)
                self.screen.blit(img, (cx, y0))
            except FileNotFoundError:
                pass

            # Border
            border_color = COLOR_GOLD if is_winner else COLOR_GRAY
            border_width = 3 if is_winner else 1
            pygame.draw.rect(self.screen, border_color,
                             (cx, y0, card_w, card_h),
                             width=border_width, border_radius=6)

            # Meno hráča
            name = self.game_state.players[player_idx].name
            name_surf = self.font_medium.render(
                name, True, COLOR_GOLD if is_winner else COLOR_WHITE
            )
            self.screen.blit(name_surf, name_surf.get_rect(
                centerx=cx + card_w // 2, top=y0 + card_h + 8
            ))

        # Hint
        hint = self.font_small.render("Klikni pre zavretie", True, COLOR_GRAY)
        self.screen.blit(hint, hint.get_rect(
            centerx=SCREEN_WIDTH // 2, top=y0 + card_h + 50
        ))

    # ------------------------------------------------------------------
    # Pomocné metódy
    # ------------------------------------------------------------------

    def _show_message(self, text: str, duration_ms: int = 2000):
        self.message = text
        self.message_timer = pygame.time.get_ticks() + duration_ms

    def _handle_declaration_failed(self):
        """
        Záväzok zlyhal — zobraz hlásenie a nastav timer na ukončenie kola.
        """
        current_round = self.game_state.current_round


        if current_round.declaration_type == "none":
            msg = "Nevyšlo! Zobral som štich."
        else:
            msg = "Nevyšlo! Niekto mi zobral štich."
        self.speech_bubble.show_bid(current_round.declaration_player, msg)


        # Timer — po 2s ukončí kolo
        self.declaration_failed_timer = pygame.time.get_ticks() + 2000

        # Reset trick stavu
        self.trick_waiting = False
        self.trick_display_timer = 0
        self._trick_anim_started = False
        self.trick_animation.done = True
        self.trick_animation.cards_in_flight = []
        self.card_throw_animation.in_flight = {}
        self.waiting_for_ai = False

    # ------------------------------------------------------------------
    # Tipy od AI
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Štatistiky profilu
    # ------------------------------------------------------------------

    def _current_difficulties(self) -> list[str]:
        """Obtiažnosti súperov v poradí, ako sedia za stolom. Číta sa z
        bežiacich AI, lebo tie odrážajú aj zmenu počas hry."""
        return [
            getattr(ai, "difficulty", "?")
            for ai in self.ai_players if ai is not None
        ]

    def _record_game_result(self):
        """
        Zapíše DOHRATÚ hru do profilu.

        Nedohraté hry sa sem nedostanú — tie sa ukladajú na disk a do
        štatistík pribudnú až vtedy, keď ich hráč zahodí novou hrou
        (main.py volá profile.record_abandoned()). Odchod do menu sa dá
        vrátiť, takže sám o sebe ešte nič nevzdáva.

        Zlyhanie zápisu nesmie zhodiť hru — štatistika je bonus, nie
        herná logika.
        """
        if self._game_recorded:
            return
        collector = self.game_state.stats_collector
        if collector is None:
            return
        self._game_recorded = True
        try:
            prof = profile_store.load_active_profile()
            prof.add_game(
                collector.to_record(
                    self.game_state, self._current_difficulties()
                )
            )
            profile_store.save_active_profile(prof)
        except Exception:
            pass

    def _save_tips_setting(self):
        """Zapamätá voľbu tipov do settings.json (rovnaký súbor ako
        ostatné nastavenia hry). Zlyhanie zápisu nesmie zhodiť hru —
        tip je pomôcka, nie herná logika."""
        try:
            from game_setup import load_settings, save_settings
            stored = load_settings()
            stored["tips_enabled"] = self.tips_enabled
            save_settings(stored)
        except Exception:
            pass

    def _safe_update_tip(self):
        """
        Obal okolo _update_tip pre hernú slučku.

        Tip je pomôcka, nie herná logika — nech sa v ňom pokazí čokoľvek
        (chybne prepísaný text, nová AI stratégia, hocičo), nesmie to
        zhodiť rozohratú hru. Pri chybe sa tip len skryje a pokračuje sa
        ďalej; hráč nanajvýš príde o radu, nie o rozohratú partiu.
        """
        try:
            self._update_tip()
        except Exception:
            self.current_tip = None
            self._tip_key = None
            if not self._tip_error_logged:
                self._tip_error_logged = True
                import traceback
                traceback.print_exc()

    def _update_tip(self):
        """
        Prepočíta tip, keď je hráč na ťahu a zmenila sa situácia.
        Volá sa každú snímku, ale AI sa pýtame len pri zmene štichu/ruky
        (rozhodnutie trvá ~0,1 ms, no nemá zmysel ho opakovať 60× za
        sekundu pre tú istú pozíciu).
        """
        if not self.tips_enabled or self.advisor is None:
            self.current_tip = None
            return

        current_round = self.game_state.current_round
        if current_round is None:
            self.current_tip = None
            self._tip_key = None
            return

        # Príprava kola — radíme, či vysvietiť horníka/horníkov.
        if current_round.phase == "preparation":
            self._update_illumination_tip(current_round)
            return

        if (current_round.phase != "tricks"
                or current_round.current_trick is None
                or not self.game_state.is_human_turn
                or self.trick_waiting
                or self.card_throw_animation.in_flight
                or self.trick_animation.cards_in_flight):
            self.current_tip = None
            self._tip_key = None
            return

        human_index = self.game_state.human_index
        player = self.game_state.players[human_index]
        trick = current_round.current_trick

        key = (
            current_round.trick_number,
            len(trick.played_cards),
            len(player.hand.cards),
        )
        if key == self._tip_key and self.current_tip is not None:
            return

        playable = player.hand.get_playable_cards(
            trick.lead_suit,
            current_round.trick_number,
            declaration_active=current_round.declaration_type is not None,
        )
        scores = [p.total_score for p in self.game_state.players]
        self.current_tip = self.advisor.tip_card(
            playable, trick, current_round.trick_number, scores
        )
        self._tip_key = key

    def _update_illumination_tip(self, current_round):
        """Tip pre prípravnú fázu — vysvietiť horníka, či nie. Hráč sa
        rozhoduje len raz za kolo, takže stačí spočítať raz (kľúč drží aj
        počet kariet v ruke, nech to sedí aj po rozdaní)."""
        human_index = self.game_state.human_index
        player = self.game_state.players[human_index]
        key = ("illum", self.game_state.round_number, len(player.hand.cards))
        if key == self._tip_key and self.current_tip is not None:
            return
        scores = [p.total_score for p in self.game_state.players]
        tip = self.advisor.tip_illumination(
            current_round.first_player_index, scores
        )
        # Bez horníka v ruke niet čo radiť — panel sa vôbec neukáže.
        self.current_tip = None if tip.is_empty else tip
        self._tip_key = key

    def _reset_trick_state(self):
        """Resetuje stav štichu pri odchode."""
        current_round = self.game_state.current_round
        if (current_round and current_round.current_trick and
                current_round.current_trick.is_complete):
            trick = current_round.current_trick
            winner_index = trick.get_winner_index()
            for ai in self.ai_players:
                if ai is not None:
                    ai.record_trick(
                        trick.played_cards,
                        winner_index,
                        current_round.trick_number
                    )
            if self.advisor is not None:
                self.advisor.record_trick(
                    trick.played_cards, winner_index, current_round.trick_number
                )
            current_round.finish_trick()

            # Skontroluj zlyhanie záväzku
            if current_round.check_declaration_failed():
                self._handle_declaration_failed()
                return

            if current_round.phase == "scoring":
                self.game_state.finish_round()

        self.trick_waiting = False
        self.trick_display_timer = 0
        self._trick_anim_started = False
        self.trick_animation.done = True
        self.trick_animation.cards_in_flight = []
        self.card_throw_animation.in_flight = {}
        self.waiting_for_ai = False

        if (current_round and current_round.phase == "tricks"
                and current_round.current_trick is None):
            current_round.start_trick()

    def __repr__(self) -> str:
        return f"Screen({SCREEN_WIDTH}x{SCREEN_HEIGHT}, debug={self.debug})"