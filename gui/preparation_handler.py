# gui/preparation_handler.py


class PreparationHandler:
    """Logika prípravnej fázy: záväzky, vysvietenie, AI príprava."""

    def __init__(self, screen_ref):
        self.s = screen_ref  # referencia na Screen

    def _record_advisor(self, kind: str, player_index: int, *args):
        """
        Dokŕmi radcu hráča (tipy, game/advisor.py) tou istou verejnou
        informáciou, akú práve dostali AI súperi. Advisor zámerne nie je
        v self.s.ai_players (ten zoznam znamená "kto hrá sám za seba"),
        preto tieto explicitné volania.
        """
        advisor = getattr(self.s, "advisor", None)
        if advisor is None:
            return
        if kind == "declaration":
            advisor.record_declaration(player_index, *args)
        elif kind == "illumination":
            advisor.record_illumination(player_index, *args)

    # ------------------------------------------------------------------
    # Klikanie
    # ------------------------------------------------------------------

    def handle_preparation_click(self, pos: tuple[int, int]):
        """Spracuje klik počas prípravy."""
        pr = self.s.phase_renderer
        player = self.s.game_state.players[self.s.game_state.human_index]

        # Viditeľnosť tlačidiel rieši Screen._shows() — v ostrej hre vždy
        # True, naskriptovaná lekcia ich odhaľuje postupne. Pýtame sa tu
        # rovnako ako pri kreslení (PhaseRenderer.draw_buttons), inak by sa
        # dalo kliknúť na tlačidlo, ktoré ešte nie je na obrazovke.
        if (self.s._shows("ok")
                and pr._button_ok_rect().collidepoint(pos)):
            self.confirm_preparation()
            return

        if self.s._shows("declaration"):
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
    # ------------------------------------------------------------------
    # Potvrdenie prípravy
    # ------------------------------------------------------------------

    def confirm_preparation(self):
        """Potvrdí prípravu ľudského hráča a spustí AI prípravu."""
        current_round = self.s.game_state.current_round
        player_index = self.s.game_state.human_index
        player = self.s.game_state.players[player_index]

        # Záväzok
        #
        # V naskriptovanej lekcii (kapitola 1 tutoriálu) je krok "Záväzok"
        # zámerne NANEČISTO: tlačidlá sa dajú kliknúť a zvýraznia sa, ale
        # záväzok sa reálne nevyhlási. Skutočný záväzok by naskriptované
        # kolo rozbil — deklarant by viedol prvý štich, AI by prepli na inú
        # stratégiu a check_declaration_failed() by kolo mohol ukončiť
        # predčasne. Hráč si záväzok s reálnym efektom vyskúša v kapitole 2
        # (tréningová hra). Rozhodnutie:
        # claude/08_TUTORIAL_REFACTOR_DESIGN.md §9 č. 1.
        declaration = self.s.active_declaration
        if (self.s.director is not None
                and self.s.director.suppress_declaration()):
            declaration = None

        current_round.process_declaration(player_index, declaration)
        for ai in self.s.ai_players:
            if ai is not None:
                ai.record_declaration(player_index, declaration)
        self._record_advisor("declaration", player_index, declaration)

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
        self._record_advisor(
            "illumination", player_index, illuminate_leaf, illuminate_acorn
        )

        # Bubliny
        if illuminate_leaf and illuminate_acorn:
            self.s.speech_bubble.show_bid(player_index, "Svietim oboch!")
        elif illuminate_leaf:
            self.s.speech_bubble.show_bid(player_index, "Svietim zeleného!")
        elif illuminate_acorn:
            self.s.speech_bubble.show_bid(player_index, "Svietim žaluďového!")

        if declaration:
            text = ("Beriem všetko!" if declaration == "all"
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
        current_round = self.s.game_state.current_round
        # Ak človek už vyhlásil záväzok, AI nemôžu vyhlásiť
        declaration_made = current_round.declaration_type is not None

        for i, player in enumerate(self.s.game_state.players):
            if player.is_human:
                continue
            ai = self.s.ai_players[i]
            if ai is None:
                continue

            declaration = ai.decide_declaration()

            if declaration and declaration_made:
                declaration = None
                self.s.speech_bubble.show_bid(i, "Ja som chcel tiež! #%*@!!")

            current_round.process_declaration(i, declaration)

            for other_ai in self.s.ai_players:
                if other_ai is not None:
                    other_ai.record_declaration(i, declaration)
            self._record_advisor("declaration", i, declaration)

            if declaration and not declaration_made:
                declaration_made = True
                text = "Beriem všetko!" if declaration == "all" else "Nechytím nič!"
                self.s.speech_bubble.show_bid(i, text)
            elif declaration and declaration_made:
                text = "Ja som chcel tiež! #%*@!!"
                self.s.speech_bubble.show_bid(i, text)
            self.s.game_state.logger.log_declaration(player.name, declaration)

            # Vysvietenie — ostáva nezmenené
            scores = [p.total_score for p in self.s.game_state.players]
            illuminate_leaf, illuminate_acorn = ai.decide_illumination(
                current_round.first_player_index, scores
            )
            current_round.process_revealing(i, illuminate_leaf, illuminate_acorn)

            for other_ai in self.s.ai_players:
                if other_ai is not None:
                    other_ai.record_illumination(i, illuminate_leaf, illuminate_acorn)
            self._record_advisor(
                "illumination", i, illuminate_leaf, illuminate_acorn
            )

            if illuminate_leaf and illuminate_acorn:
                self.s.speech_bubble.show_bid(i, "Svietim oboch!")
            elif illuminate_leaf:
                self.s.speech_bubble.show_bid(i, "Svietim zeleného!")
            elif illuminate_acorn:
                self.s.speech_bubble.show_bid(i, "Svietim žaluďového!")

    # ------------------------------------------------------------------
    # Postup fázami
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # AI záväzok / vysvietenie (standalone volania)
    # ------------------------------------------------------------------
