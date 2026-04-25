# gui/screen.py

import pygame
from game.game_state import GameState
from game.ai import AI
from gui.card_renderer import CardRenderer
from gui.scoreboard import Scoreboard
from gui.deal_animation import DealAnimation
from gui.trick_animation import TrickAnimation
from gui.speech_bubble import SpeechBubble
from gui.info_overlay import InfoOverlay
from gui.chujogram_panel import ChujogramPanel
from gui.round_status import RoundStatus
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, DEBUG_MODE,
    COLOR_BG, COLOR_YELLOW,
    COLOR_WHITE, COLOR_GOLD,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE, FONT_SIZE_SMALL,
    TABLE_CENTER_X, TABLE_CENTER_Y,
    BUTTON_HEIGHT, BUTTON_RADIUS, BUTTON_Y,
    BUTTON_SORT_X, BUTTON_SORT_Y, BUTTON_SORT_WIDTH, BUTTON_SORT_HEIGHT,
    BUTTON_INFO_X, BUTTON_INFO_Y, BUTTON_INFO_WIDTH, BUTTON_INFO_HEIGHT,
    BUTTON_MENU_X, BUTTON_MENU_Y, BUTTON_MENU_WIDTH, BUTTON_MENU_HEIGHT,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    NUM_PLAYERS
)


class Screen:
    def __init__(self, game_state: GameState, ai_players: list,
                 debug: bool = DEBUG_MODE, new_game: bool = True):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Chuj")

        try:
            self.table_bg = pygame.image.load(
                "assets/graphics/table.jpg"
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

        self.font_small = pygame.font.SysFont(None, FONT_SIZE_SMALL)
        self.font_medium = pygame.font.SysFont(None, FONT_SIZE_MEDIUM)
        self.font_large = pygame.font.SysFont(None, FONT_SIZE_LARGE)

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
        # História bodov pre chujogram
        self.round_scores_history: list[list[int]] = []

        self.round_status = RoundStatus(self.screen)

        self.sort_ascending = False

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
        first_player = self.game_state.players[
            current_round.first_player_index
        ].name

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
                    self._reset_trick_state()
                    self.running = False

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

        if self._button_sort_rect().collidepoint(pos):
            self.sort_ascending = not self.sort_ascending
            self.game_state.players[
                self.game_state.human_index
            ].hand.sort_hand(self.sort_ascending)
            return

        if self._button_info_rect().collidepoint(pos):
            self.info_overlay.toggle()
            return

        if self._button_menu_rect().collidepoint(pos):
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
    def _handle_preparation_click(self, pos: tuple[int, int]):
        """Spracuje klik počas prípravy."""
        current_round = self.game_state.current_round
        player_index = self.game_state.human_index
        player = self.game_state.players[player_index]

        # Tlačidlo OK
        if self._button_ok_rect().collidepoint(pos):
            self._confirm_preparation()
            return

        # Tlačidlo Beriem všetko
        if self._button_decl_all_rect().collidepoint(pos):
            if self.active_declaration == "all":
                self.active_declaration = None  # zruš
            else:
                self.active_declaration = "all"
            return

        # Tlačidlo Nechytím nič
        if self._button_decl_none_rect().collidepoint(pos):
            if self.active_declaration == "none":
                self.active_declaration = None  # zruš
            else:
                self.active_declaration = "none"
            return

        # Klik na kartu — vysvietenie horníka
        clicked_card = self.card_renderer.get_clicked_card(
            pos, player.hand.cards, player_index
        )
        if clicked_card:
            if clicked_card.is_leaf_over or clicked_card.is_acorn_over:
                if clicked_card in self.selected_illumination:
                    self.selected_illumination.remove(clicked_card)
                else:
                    self.selected_illumination.append(clicked_card)

    def _handle_declaration_click(self, pos: tuple[int, int]):
        """Spracuje klik počas záväzku."""
        current_round = self.game_state.current_round
        player_index = self.game_state.human_index

        # Len ak je na rade ľudský hráč
        if self.declaration_index != player_index:
            return

        if self._button_decl_all_rect().collidepoint(pos):
            current_round.process_declaration(player_index, "all")
            self._advance_declaration()

        elif self._button_decl_none_rect().collidepoint(pos):
            current_round.process_declaration(player_index, "none")
            self._advance_declaration()

        elif self._button_decl_pass_rect().collidepoint(pos):
            current_round.process_declaration(player_index, None)
            self._advance_declaration()

    def _handle_revealing_click(self, pos: tuple[int, int]):
        current_round = self.game_state.current_round
        player_index = self.game_state.human_index

        if self.revealing_index != player_index:
            return

        player = self.game_state.players[player_index]

        if self._button_reveal_leaf_rect().collidepoint(pos):
            if player.hand.has_leaf_over() and not player.illuminated_leaf:
                current_round.process_revealing(player_index, True, False)
            return  # Neskončíme — hráč môže vysvietiť aj druhého

        if self._button_reveal_acorn_rect().collidepoint(pos):
            if player.hand.has_acorn_over() and not player.illuminated_acorn:
                current_round.process_revealing(player_index, False, True)
            return  # Neskončíme

        if self._button_reveal_pass_rect().collidepoint(pos):
            self._advance_revealing()  # ← len "Hotovo" posúva ďalej

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

    def _confirm_preparation(self):
        """Potvrdí prípravu a začne štichy."""
        current_round = self.game_state.current_round
        player_index = self.game_state.human_index
        player = self.game_state.players[player_index]

        # Aplikuj záväzok
        current_round.process_declaration(
            player_index, self.active_declaration
        )

        # Zaznamená záväzok do pamäte všetkých AI
        for ai in self.ai_players:
            if ai is not None:
                ai.record_declaration(player_index, self.active_declaration)

        # Aplikuj vysvietenie
        illuminate_leaf = any(
            c.is_leaf_over for c in self.selected_illumination
        )
        illuminate_acorn = any(
            c.is_acorn_over for c in self.selected_illumination
        )
        current_round.process_revealing(
            player_index, illuminate_leaf, illuminate_acorn
        )
        # Log vysvietenia hráča ← hneď tu
        if illuminate_leaf or illuminate_acorn:
            self.game_state.logger.log_illumination(
                player.name, illuminate_leaf, illuminate_acorn
            )

        # Zaznamená vysvietenie do pamäte všetkých AI
        for ai in self.ai_players:
            if ai is not None:
                ai.record_illumination(player_index, illuminate_leaf, illuminate_acorn)

        # Bublina pre vysvietenie
        if illuminate_leaf and illuminate_acorn:
            self.speech_bubble.show_bid(player_index, "Svietim oboch!")
        elif illuminate_leaf:
            self.speech_bubble.show_bid(player_index, "Svietim zeleného!")
        elif illuminate_acorn:
            self.speech_bubble.show_bid(player_index, "Svietim žaluďového!")

        # Bublina pre záväzok — prepíše vysvietenie
        if self.active_declaration:
            text = "Beriem všetko!" if self.active_declaration == "all" \
                else "Nechytím nič!"
            self.speech_bubble.show_bid(player_index, text)

        # Reset
        self.active_declaration = None
        self.selected_illumination = []

        # AI hráči spracovania
        self._process_ai_preparation()

        # Začni štichy
        current_round.finish_preparation()

    def _process_ai_preparation(self):
        current_round = self.game_state.current_round
        for i, player in enumerate(self.game_state.players):
            if player.is_human:
                continue
            ai = self.ai_players[i]
            if ai is None:
                continue

            # Záväzok
            declaration = ai.decide_declaration()
            current_round.process_declaration(i, declaration)

            # Zaznamená záväzok
            for other_ai in self.ai_players:
                if other_ai is not None:
                    other_ai.record_declaration(i, declaration)

            if declaration:
                self.speech_bubble.show_bid(
                    i, "Beriem všetko!" if declaration == "all"
                    else "Nechytím nič!"
                )
            self.game_state.logger.log_declaration(player.name, declaration)

            # Vysvietenie
            illuminate_leaf, illuminate_acorn = ai.decide_illumination(
                current_round.first_player_index
            )
            current_round.process_revealing(i, illuminate_leaf, illuminate_acorn)

            # Zaznamená vysvietenie ← až tu, po definícii
            for other_ai in self.ai_players:
                if other_ai is not None:
                    other_ai.record_illumination(i, illuminate_leaf, illuminate_acorn)

            if illuminate_leaf and illuminate_acorn:
                self.speech_bubble.show_bid(i, "Svietim oboch!")
            elif illuminate_leaf:
                self.speech_bubble.show_bid(i, "Svietim zeleného!")
            elif illuminate_acorn:
                self.speech_bubble.show_bid(i, "Svietim žaluďového!")

    # ------------------------------------------------------------------
    # Postup fázami
    # ------------------------------------------------------------------

    def _advance_declaration(self):
        """Posunie záväzok na ďalšieho hráča."""
        current_round = self.game_state.current_round
        self.declaration_index += 1

        if self.declaration_index >= NUM_PLAYERS:
            current_round.finish_declarations()
            self.revealing_index = 0

    def _advance_revealing(self):
        """Posunie vysvietenie na ďalšieho hráča."""
        current_round = self.game_state.current_round
        self.revealing_index += 1

        if self.revealing_index >= NUM_PLAYERS:
            current_round.finish_revealing()

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

    def _ai_declaration(self):
        """AI vyhlási záväzok."""
        current_round = self.game_state.current_round
        current_index = self.declaration_index

        player = self.game_state.players[current_index]
        if player.is_human:
            return

        ai = self.ai_players[current_index]
        pygame.time.delay(300)
        declaration = ai.decide_declaration()
        current_round.process_declaration(current_index, declaration)

        if declaration:
            self.speech_bubble.show_bid(
                current_index,
                declaration.upper()
            )

        self._advance_declaration()

    def _ai_revealing(self):
        """AI vysvietí horníkov."""
        current_round = self.game_state.current_round
        current_index = self.revealing_index

        player = self.game_state.players[current_index]
        if player.is_human:
            return

        ai = self.ai_players[current_index]
        pygame.time.delay(300)
        illuminate_leaf, illuminate_acorn = ai.decide_illumination(
            current_round.first_player_index
        )
        current_round.process_revealing(
            current_index, illuminate_leaf, illuminate_acorn
        )

        for other_ai in self.ai_players:
            if other_ai is not None:
                other_ai.record_illumination(
                    current_index, illuminate_leaf, illuminate_acorn
                )

        if illuminate_leaf and illuminate_acorn:
            self.speech_bubble.show_bid(current_index, "Svietim oboch!")
        elif illuminate_leaf:
            self.speech_bubble.show_bid(current_index, "Svietim zeleného!")
        elif illuminate_acorn:
            self.speech_bubble.show_bid(current_index, "Svietim žaluďového!")

        self.game_state.logger.log_illumination(
            player.name, illuminate_leaf, illuminate_acorn
        )

        self._advance_revealing()

    def _ai_play_card(self, player_index: int, ai: AI):
        """AI zahrá kartu."""
        self.waiting_for_ai = True
        current_round = self.game_state.current_round
        player = self.game_state.players[player_index]

        playable = player.hand.get_playable_cards(
            current_round.current_trick.lead_suit,
            current_round.trick_number  # ← pridané
        )

        card = ai.decide_card(
            playable,
            current_round.current_trick,
            current_round.trick_number
        )
        current_round.play_card(player_index, card)

        if current_round.current_trick.is_complete:
            self.trick_waiting = True
            self.trick_display_timer = pygame.time.get_ticks() + 1500

        self.waiting_for_ai = False

    # ------------------------------------------------------------------
    # Spracovanie štichu
    # ------------------------------------------------------------------

    def _process_waiting_trick(self):
        """Spracuje štich po uplynutí zobrazovacieho času."""
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

        if current_round.phase == "scoring":

            # Ulož body PRED finish_round() — len pre log
            round_points_snapshot = {
                p.name: p.round_points for p in self.game_state.players
            }

            self.game_state.finish_round()

            # Ulož CELKOVÉ skóre pre chujogram
            self.round_scores_history.append([
                p.total_score for p in self.game_state.players
            ])

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
        self._draw_player_labels()

        self.chujogram.draw(self.game_state.bullet_history,self.round_scores_history)
        self.round_status.draw(self.game_state.players,self.game_state.current_round)
        self._draw_buttons()
        self._draw_phase_overlay()
        self.speech_bubble.draw()
        self._draw_message()
        self.info_overlay.draw()

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

    def _draw_player_labels(self):
        """Nakreslí menovky hráčov."""
        font = pygame.font.SysFont(None, 28)

        label_positions = {
            0: (TABLE_CENTER_X, SCREEN_HEIGHT - 30),
            1: (SCREEN_WIDTH - 120, TABLE_CENTER_Y),
            2: (TABLE_CENTER_X, 60),
            3: (120, TABLE_CENTER_Y),
        }

        for i, player in enumerate(self.game_state.players):
            pos = label_positions[i]
            surf = font.render(player.name, True, COLOR_WHITE)
            rect = surf.get_rect(center=pos)

            bg_rect = rect.inflate(16, 8)
            bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            self.screen.blit(bg, bg_rect.topleft)
            pygame.draw.rect(self.screen, COLOR_GOLD, bg_rect, width=1, border_radius=6)

            self.screen.blit(surf, rect)

    def _draw_current_trick(self):
        """Nakreslí karty aktuálneho štichu."""
        current_round = self.game_state.current_round
        if current_round and current_round.current_trick:
            self.card_renderer.draw_trick(current_round.current_trick)

    def _draw_phase_overlay(self):
        """Nakreslí overlay pre fázy záväzku a vysvietenia."""
        if not self.game_state.current_round:
            return

        phase = self.game_state.current_round.phase

        if phase == "game_declaration":
            self._draw_declaration_overlay()
        elif phase == "revealing":
            self._draw_revealing_overlay()

    def _draw_declaration_overlay(self):
        """Nakreslí overlay pre záväzok."""
        current_index = self.declaration_index
        player = self.game_state.players[current_index]

        # Tmavý overlay
        overlay = pygame.Surface(
            (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        # Panel
        panel_w, panel_h = 500, 250
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = SCREEN_HEIGHT // 2 - panel_h // 2

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 12, 5, 230))
        self.screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (panel_x, panel_y, panel_w, panel_h),
            width=2, border_radius=10
        )

        # Nadpis
        title = self.font_large.render(
            f"{player.name} — záväzok?", True, COLOR_GOLD
        )
        title_rect = title.get_rect(
            centerx=SCREEN_WIDTH // 2, top=panel_y + 20
        )
        self.screen.blit(title, title_rect)

        # Tlačidlá len ak je ľudský hráč na rade
        if player.is_human:
            self._draw_button(
                self._button_decl_all_rect(),
                "Všetky štichy -20b",
                COLOR_BUTTON_PRIMARY
            )
            self._draw_button(
                self._button_decl_none_rect(),
                "Žiadny trestný bod -10b",
                COLOR_BUTTON_PRIMARY
            )
            self._draw_button(
                self._button_decl_pass_rect(),
                "Bez záväzku",
                COLOR_BUTTON_SECONDARY
            )

    def _draw_revealing_overlay(self):
        current_index = self.revealing_index
        player = self.game_state.players[current_index]
        current_round = self.game_state.current_round

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        panel_w, panel_h = 500, 220
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = SCREEN_HEIGHT // 2 - panel_h // 2 - 50

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 12, 5, 230))
        self.screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (panel_x, panel_y, panel_w, panel_h),
            width=2, border_radius=10
        )

        title = self.font_large.render(
            f"{player.name} — vysvietenie?", True, COLOR_GOLD
        )
        title_rect = title.get_rect(
            centerx=SCREEN_WIDTH // 2, top=panel_y + 15
        )
        self.screen.blit(title, title_rect)

        if player.is_human:
            has_leaf = player.hand.has_leaf_over()
            has_acorn = player.hand.has_acorn_over()

            # Zobraz len tlačidlá pre karty ktoré hráč má
            # a ešte nevysvietil
            if has_leaf and not player.illuminated_leaf:
                self._draw_button(
                    self._button_reveal_leaf_rect(),
                    "Zelený horník (16b)",
                    COLOR_BUTTON_PRIMARY
                )
            if has_acorn and not player.illuminated_acorn:
                self._draw_button(
                    self._button_reveal_acorn_rect(),
                    "Žaluďový horník (8b)",
                    COLOR_BUTTON_PRIMARY
                )
            self._draw_button(
                self._button_reveal_pass_rect(),
                "Hotovo",
                COLOR_BUTTON_SECONDARY
            )

    def _draw_buttons(self):
        # Vždy viditeľné
        self._draw_button(self._button_sort_rect(), "Zoradiť", COLOR_BUTTON_SECONDARY)
        self._draw_button(self._button_info_rect(), "Pravidlá", COLOR_BUTTON_SECONDARY)
        self._draw_button(self._button_menu_rect(), "Menu", COLOR_BUTTON_SECONDARY)

        # Preparation tlačidlá
        phase = self.game_state.current_round.phase \
            if self.game_state.current_round else None

        if phase == "preparation" and self.game_state.is_human_turn:
            # Beriem všetko
            color_all = COLOR_BUTTON_PRIMARY if self.active_declaration == "all" \
                else COLOR_BUTTON_SECONDARY
            self._draw_button(
                self._button_decl_all_rect(),
                "Beriem všetko  [-20b]",
                color_all
            )

            # Nechytím nič
            color_none = COLOR_BUTTON_PRIMARY if self.active_declaration == "none" \
                else COLOR_BUTTON_SECONDARY
            self._draw_button(
                self._button_decl_none_rect(),
                "Nechytím nič  [-10b]",
                color_none
            )

            # OK
            self._draw_button(
                self._button_ok_rect(),
                "OK",
                COLOR_BUTTON_PRIMARY
            )

    def _draw_button(self, rect: pygame.Rect, text: str, color: tuple):
        """Nakreslí jedno tlačidlo s hover efektom."""
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)
        alpha = 240 if is_hover else 200

        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.screen.blit(overlay, (rect.x, rect.y))

        if is_hover:
            hover_surf = pygame.Surface(
                (rect.width, rect.height), pygame.SRCALPHA
            )
            hover_surf.fill((255, 255, 255, 25))
            self.screen.blit(hover_surf, (rect.x, rect.y))

        border_color = COLOR_WHITE if is_hover else COLOR_GOLD
        pygame.draw.rect(
            self.screen, border_color,
            rect, width=2, border_radius=BUTTON_RADIUS
        )

        surf = self.font_medium.render(text, True, COLOR_WHITE)
        text_rect = surf.get_rect(center=rect.center)
        self.screen.blit(surf, text_rect)

    def _draw_message(self):
        """Zobrazí správu."""
        if not self.message or pygame.time.get_ticks() >= self.message_timer:
            return

        surf = self.font_large.render(self.message, True, COLOR_YELLOW)
        msg_w = surf.get_width() + 60
        msg_h = surf.get_height() + 20
        msg_x = TABLE_CENTER_X - msg_w // 2
        msg_y = 790 - msg_h // 2

        overlay = pygame.Surface((msg_w, msg_h), pygame.SRCALPHA)
        overlay.fill((25, 15, 8, 200))
        self.screen.blit(overlay, (msg_x, msg_y))
        pygame.draw.rect(
            self.screen, COLOR_GOLD,
            (msg_x, msg_y, msg_w, msg_h),
            width=2, border_radius=8
        )
        text_rect = surf.get_rect(
            center=(TABLE_CENTER_X, msg_y + msg_h // 2)
        )
        self.screen.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Button rects
    # ------------------------------------------------------------------
    @staticmethod
    def _button_sort_rect() -> pygame.Rect:
        return pygame.Rect(
            BUTTON_SORT_X, BUTTON_SORT_Y,
            BUTTON_SORT_WIDTH, BUTTON_SORT_HEIGHT
        )

    @staticmethod
    def _button_info_rect() -> pygame.Rect:
        return pygame.Rect(
            BUTTON_INFO_X, BUTTON_INFO_Y,
            BUTTON_INFO_WIDTH, BUTTON_INFO_HEIGHT
        )

    @staticmethod
    def _button_menu_rect() -> pygame.Rect:
        return pygame.Rect(
            BUTTON_MENU_X, BUTTON_MENU_Y,
            BUTTON_MENU_WIDTH, BUTTON_MENU_HEIGHT
        )

    @staticmethod
    def _button_decl_all_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 420, BUTTON_Y, 260, BUTTON_HEIGHT)

    @staticmethod
    def _button_decl_none_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 140, BUTTON_Y, 260, BUTTON_HEIGHT)

    @staticmethod
    def _button_ok_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X + 140, BUTTON_Y, 120, BUTTON_HEIGHT)

    @staticmethod
    def _button_decl_pass_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 220, SCREEN_HEIGHT // 2 + 40, 420, 50)

    @staticmethod
    def _button_reveal_leaf_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 220, SCREEN_HEIGHT // 2 - 80, 420, 50)

    @staticmethod
    def _button_reveal_acorn_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 220, SCREEN_HEIGHT // 2 - 20, 420, 50)

    @staticmethod
    def _button_reveal_pass_rect() -> pygame.Rect:
        return pygame.Rect(TABLE_CENTER_X - 220, SCREEN_HEIGHT // 2 + 40, 420, 50)

    # ------------------------------------------------------------------
    # Pomocné metódy
    # ------------------------------------------------------------------

    def _show_message(self, text: str, duration_ms: int = 2000):
        self.message = text
        self.message_timer = pygame.time.get_ticks() + duration_ms

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