import pygame
from config import NUM_PLAYERS


class PreparationHandler:
    """Logika prípravnej fázy: záväzky, vysvietenie, AI príprava."""

    def __init__(self, screen_ref):
        self.s = screen_ref  # referencia na Screen

    # ------------------------------------------------------------------
    # Klikanie
    # ------------------------------------------------------------------

    def handle_preparation_click(self, pos: tuple[int, int]):
        """Spracuje klik počas prípravy."""
        pr = self.s.phase_renderer
        player = self.s.game_state.players[self.s.game_state.human_index]

        if pr._button_ok_rect().collidepoint(pos):
            self.confirm_preparation()
            return

        if pr._button_decl_all_rect().collidepoint(pos):
            self.s.active_declaration = (
                None if self.s.active_declaration == "all" else "all"
            )
            return

        if pr._button_decl_none_rect().collidepoint(pos):
            self.s.active_declaration = (
                None if self.s.active_declaration == "none" else "none"
            )
            return

        # Klik na kartu — vysvietenie horníka
        clicked_card = self.s.card_renderer.get_clicked_card(
            pos, player.hand.cards, self.s.game_state.human_index
        )
        if clicked_card:
            if clicked_card.is_leaf_over or clicked_card.is_acorn_over:
                if clicked_card in self.s.selected_illumination:
                    self.s.selected_illumination.remove(clicked_card)
                else:
                    self.s.selected_illumination.append(clicked_card)

    def handle_declaration_click(self, pos: tuple[int, int]):
        """Spracuje klik počas záväzku."""
        pr = self.s.phase_renderer
        current_round = self.s.game_state.current_round
        player_index = self.s.game_state.human_index

        if self.s.declaration_index != player_index:
            return

        if pr._button_decl_all_rect().collidepoint(pos):
            current_round.process_declaration(player_index, "all")
            self._advance_declaration()
        elif pr._button_decl_none_rect().collidepoint(pos):
            current_round.process_declaration(player_index, "none")
            self._advance_declaration()
        elif pr._button_decl_pass_rect().collidepoint(pos):
            current_round.process_declaration(player_index, None)
            self._advance_declaration()

    def handle_revealing_click(self, pos: tuple[int, int]):
        """Spracuje klik počas vysvietenia."""
        pr = self.s.phase_renderer
        current_round = self.s.game_state.current_round
        player_index = self.s.game_state.human_index

        if self.s.revealing_index != player_index:
            return

        player = self.s.game_state.players[player_index]

        if pr._button_reveal_leaf_rect().collidepoint(pos):
            if player.hand.has_leaf_over() and not player.illuminated_leaf:
                current_round.process_revealing(player_index, True, False)
            return

        if pr._button_reveal_acorn_rect().collidepoint(pos):
            if player.hand.has_acorn_over() and not player.illuminated_acorn:
                current_round.process_revealing(player_index, False, True)
            return

        if pr._button_reveal_pass_rect().collidepoint(pos):
            self._advance_revealing()

    # ------------------------------------------------------------------
    # Potvrdenie prípravy
    # ------------------------------------------------------------------

    def confirm_preparation(self):
        """Potvrdí prípravu ľudského hráča a spustí AI prípravu."""
        current_round = self.s.game_state.current_round
        player_index = self.s.game_state.human_index
        player = self.s.game_state.players[player_index]

        # Záväzok
        current_round.process_declaration(player_index, self.s.active_declaration)
        for ai in self.s.ai_players:
            if ai is not None:
                ai.record_declaration(player_index, self.s.active_declaration)

        # Vysvietenie
        illuminate_leaf = any(c.is_leaf_over for c in self.s.selected_illumination)
        illuminate_acorn = any(c.is_acorn_over for c in self.s.selected_illumination)
        current_round.process_revealing(player_index, illuminate_leaf, illuminate_acorn)

        if illuminate_leaf or illuminate_acorn:
            self.s.game_state.logger.log_illumination(
                player.name, illuminate_leaf, illuminate_acorn
            )

        for ai in self.s.ai_players:
            if ai is not None:
                ai.record_illumination(player_index, illuminate_leaf, illuminate_acorn)

        # Bubliny
        if illuminate_leaf and illuminate_acorn:
            self.s.speech_bubble.show_bid(player_index, "Svietim oboch!")
        elif illuminate_leaf:
            self.s.speech_bubble.show_bid(player_index, "Svietim zeleného!")
        elif illuminate_acorn:
            self.s.speech_bubble.show_bid(player_index, "Svietim žaluďového!")

        if self.s.active_declaration:
            text = ("Beriem všetko!" if self.s.active_declaration == "all"
                    else "Nechytím nič!")
            self.s.speech_bubble.show_bid(player_index, text)

        # Reset
        self.s.active_declaration = None
        self.s.selected_illumination = []

        # AI príprava
        self._process_ai_preparation()

        # Začni štichy
        current_round.finish_preparation()

    # ------------------------------------------------------------------
    # AI príprava
    # ------------------------------------------------------------------

    def _process_ai_preparation(self):
        """Spracuje záväzky a vysvietenie všetkých AI hráčov."""
        current_round = self.s.game_state.current_round

        for i, player in enumerate(self.s.game_state.players):
            if player.is_human:
                continue
            ai = self.s.ai_players[i]
            if ai is None:
                continue

            # Záväzok
            declaration = ai.decide_declaration()
            current_round.process_declaration(i, declaration)

            for other_ai in self.s.ai_players:
                if other_ai is not None:
                    other_ai.record_declaration(i, declaration)

            if declaration:
                text = "Beriem všetko!" if declaration == "all" else "Nechytím nič!"
                self.s.speech_bubble.show_bid(i, text)
            self.s.game_state.logger.log_declaration(player.name, declaration)

            # Vysvietenie
            scores = [p.total_score for p in self.s.game_state.players]
            illuminate_leaf, illuminate_acorn = ai.decide_illumination(
                current_round.first_player_index, scores
            )
            current_round.process_revealing(i, illuminate_leaf, illuminate_acorn)

            for other_ai in self.s.ai_players:
                if other_ai is not None:
                    other_ai.record_illumination(i, illuminate_leaf, illuminate_acorn)

            if illuminate_leaf and illuminate_acorn:
                self.s.speech_bubble.show_bid(i, "Svietim oboch!")
            elif illuminate_leaf:
                self.s.speech_bubble.show_bid(i, "Svietim zeleného!")
            elif illuminate_acorn:
                self.s.speech_bubble.show_bid(i, "Svietim žaluďového!")

    # ------------------------------------------------------------------
    # Postup fázami
    # ------------------------------------------------------------------

    def _advance_declaration(self):
        """Posunie záväzok na ďalšieho hráča."""
        current_round = self.s.game_state.current_round
        self.s.declaration_index += 1
        if self.s.declaration_index >= NUM_PLAYERS:
            current_round.finish_declarations()
            self.s.revealing_index = 0

    def _advance_revealing(self):
        """Posunie vysvietenie na ďalšieho hráča."""
        current_round = self.s.game_state.current_round
        self.s.revealing_index += 1
        if self.s.revealing_index >= NUM_PLAYERS:
            current_round.finish_revealing()

    # ------------------------------------------------------------------
    # AI záväzok / vysvietenie (standalone volania)
    # ------------------------------------------------------------------

    def ai_declaration(self):
        """AI vyhlási záväzok."""
        current_round = self.s.game_state.current_round
        current_index = self.s.declaration_index
        player = self.s.game_state.players[current_index]

        if player.is_human:
            return

        ai = self.s.ai_players[current_index]
        pygame.time.delay(300)
        declaration = ai.decide_declaration()
        current_round.process_declaration(current_index, declaration)

        if declaration:
            self.s.speech_bubble.show_bid(
                current_index,
                "Beriem všetko!" if declaration == "all" else "Nechytím nič!"
            )
        self._advance_declaration()

    def ai_revealing(self):
        """AI vysvietí horníkov."""
        current_round = self.s.game_state.current_round
        current_index = self.s.revealing_index
        player = self.s.game_state.players[current_index]

        if player.is_human:
            return

        ai = self.s.ai_players[current_index]
        pygame.time.delay(300)
        illuminate_leaf, illuminate_acorn = ai.decide_illumination(
            current_round.first_player_index
        )
        current_round.process_revealing(current_index, illuminate_leaf, illuminate_acorn)

        for other_ai in self.s.ai_players:
            if other_ai is not None:
                other_ai.record_illumination(current_index, illuminate_leaf, illuminate_acorn)

        if illuminate_leaf and illuminate_acorn:
            self.s.speech_bubble.show_bid(current_index, "Svietim oboch!")
        elif illuminate_leaf:
            self.s.speech_bubble.show_bid(current_index, "Svietim zeleného!")
        elif illuminate_acorn:
            self.s.speech_bubble.show_bid(current_index, "Svietim žaluďového!")

        self.s.game_state.logger.log_illumination(
            player.name, illuminate_leaf, illuminate_acorn
        )
        self._advance_revealing()