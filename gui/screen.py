# gui/screen.py

import pygame
from game.game_state import GameState
from game.ai import AI
from game.ai_strategies_const import Strategy
from gui.card_renderer import CardRenderer
from gui.scoreboard import Scoreboard
from gui.deal_animation import DealAnimation
from gui.trick_animation import TrickAnimation
from gui.speech_bubble import SpeechBubble
from gui.info_overlay import InfoOverlay
from gui.chujogram_panel import ChujogramPanel
from gui.round_status import RoundStatus
from gui.phase_renderer import PhaseRenderer
from gui.preparation_handler import PreparationHandler
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, DEBUG_MODE,
    COLOR_BG,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE, FONT_SIZE_SMALL,
    get_font, CARD_SIZE_MEDIUM, COLOR_GOLD, COLOR_GRAY, COLOR_WHITE
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
                self._handle_ai_turn()
                self._draw()

            pygame.display.flip()
        if self.game_state.phase == "game_over":
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

        # Reset stavov
        self.declaration_index = 0
        self.revealing_index = 0
        self.trick_waiting = False
        self._trick_anim_started = False

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
            current_round.current_trick.lead_suit,current_round.trick_number
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

        success = current_round.play_card(player_index, clicked_card)
        if success:
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

        current_round = self.game_state.current_round
        if not current_round:
            return

        phase = current_round.phase

        # preparation spracuje _confirm_preparation() nie AI turn
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
            current_round.trick_number  # ← pridané
        )

        scores = [p.total_score for p in self.game_state.players]
        card = ai.decide_card(
            playable,
            current_round.current_trick,
            current_round.trick_number,
            scores
        )
        current_round.play_card(player_index, card)

        # Bublina pre risk
        if ai.last_strategy in (Strategy.RISK_TRAP, Strategy.RISK_SPECIAL):
            texts = ["Risknem!", "Skúsim...", "Má ho?"]
            self.speech_bubble.show_bid(player_index, random.choice(texts), duration_ms=2000)

        if current_round.current_trick.is_complete:
            self.trick_waiting = True
            self.trick_display_timer = pygame.time.get_ticks() + 1500

        self.waiting_for_ai = False

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

        winner_index = current_round.finish_trick()
        winner_name = self.game_state.players[winner_index].name
        self._show_message(f"{winner_name} vyhral štich!")

        # Skontroluj zlyhanie záväzku
        if current_round.check_declaration_failed():
            decl_idx = current_round.declaration_player
            if current_round.declaration_type == "none":
                msg = "Nevyšlo! Chytil som trestný bod."
            else:
                msg = "Nevyšlo! Niekto mi zobral štich."
            self.speech_bubble.show_bid(decl_idx, msg)
            self.declaration_failed_timer = pygame.time.get_ticks() + 2000
            current_round.phase = "scoring"  # ← zastav ďalšie štichy
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
        self.trick_animation.draw()
        self.phase_renderer.draw_player_labels()
        self.chujogram.draw(self.game_state.bullet_history,self.game_state.round_scores_history)
        self.round_status.draw(self.game_state.players,self.game_state.current_round)
        self.phase_renderer.draw_buttons()
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
                trick_number=current_round.trick_number if current_round else 0
            )



    def _draw_current_trick(self):
        """Nakreslí karty aktuálneho štichu."""
        current_round = self.game_state.current_round
        if current_round and current_round.current_trick:
            self.card_renderer.draw_trick(current_round.current_trick)

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
            name_surf = self.font_small.render(
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
            msg = "Nevyšlo! Chytil som trestný bod."
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
        self.waiting_for_ai = False

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
        self.waiting_for_ai = False

        if (current_round and current_round.phase == "tricks"
                and current_round.current_trick is None):
            current_round.start_trick()

    def __repr__(self) -> str:
        return f"Screen({SCREEN_WIDTH}x{SCREEN_HEIGHT}, debug={self.debug})"