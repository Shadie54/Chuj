import pygame, os
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_WHITE, COLOR_GOLD, COLOR_YELLOW,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE,
    TABLE_CENTER_X, TABLE_CENTER_Y,
    BUTTON_HEIGHT, BUTTON_RADIUS, BUTTON_Y,
    BUTTON_SORT_X, BUTTON_SORT_Y, BUTTON_SORT_WIDTH, BUTTON_SORT_HEIGHT,
    BUTTON_INFO_X, BUTTON_INFO_Y, BUTTON_INFO_WIDTH, BUTTON_INFO_HEIGHT,
    BUTTON_MENU_X, BUTTON_MENU_Y, BUTTON_MENU_WIDTH, BUTTON_MENU_HEIGHT,
    BUTTON_LAST_TRICK_X, BUTTON_LAST_TRICK_Y, BUTTON_LAST_TRICK_WIDTH, BUTTON_LAST_TRICK_HEIGHT,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    get_font, BUTTON_CHUJOGRAM_X, BUTTON_CHUJOGRAM_Y, BUTTON_CHUJOGRAM_W, BUTTON_CHUJOGRAM_H
)


class PhaseRenderer:
    """Kreslenie UI overlayov, tlačidiel a správ pre Screen."""

    def __init__(self, surface: pygame.Surface, screen_ref):
        self.surface = surface
        self.s = screen_ref

        self.font_medium = get_font(FONT_SIZE_MEDIUM)
        self.font_large = get_font(FONT_SIZE_LARGE)

        # Chuj ikonka
        chuj_path = os.path.join("assets", "graphics", "chuj.png")
        try:
            img = pygame.image.load(chuj_path).convert_alpha()
            self._chuj_icon = pygame.transform.scale(img, (100, 100))
        except FileNotFoundError:
            self._chuj_icon = None

        # Declaration badges
        self._declaration_badges = {}
        for key in ("all", "none"):
            path = os.path.join("assets", "graphics", f"{key}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                self._declaration_badges[key] = pygame.transform.scale(img, (100, 100))
            except FileNotFoundError:
                self._declaration_badges[key] = None
    # ------------------------------------------------------------------
    # Hlavné draw metódy (volané z Screen._draw)
    # ------------------------------------------------------------------

    def draw_player_labels(self):
        """Nakreslí menovky hráčov."""
        font = get_font(28)
        label_positions = {
            0: (TABLE_CENTER_X, SCREEN_HEIGHT - 60),
            1: (SCREEN_WIDTH - 170, TABLE_CENTER_Y),
            2: (TABLE_CENTER_X, 60),
            3: (170, TABLE_CENTER_Y),
        }
        for i, player in enumerate(self.s.game_state.players):
            pos = label_positions[i]
            surf = font.render(player.name, True, COLOR_WHITE)
            rect = surf.get_rect(center=pos)

            bg_rect = rect.inflate(16, 8)
            bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            self.surface.blit(bg, bg_rect.topleft)
            pygame.draw.rect(self.surface, COLOR_GOLD, bg_rect, width=1, border_radius=6)
            self.surface.blit(surf, rect)

            # Ikony napravo/naľavo od menovky — zoradené za sebou
            right_x = bg_rect.right + 6  # pre hráčov 0, 1, 2
            left_x = bg_rect.left - 6  # pre hráča 3

            def place_icon(icon_surf):
                nonlocal right_x, left_x
                ir = icon_surf.get_rect()
                if i == 1:  # PC1 vpravo — ikonky naľavo
                    ir.midright = (left_x, bg_rect.centery)
                    left_x -= ir.width + 4
                else:  # všetci ostatní vrátane PC3 — ikonky napravo
                    ir.midleft = (right_x, bg_rect.centery)
                    right_x += ir.width + 4
                self.surface.blit(icon_surf, ir)

            # Chuj ikonka — hráč s najvyšším skóre
            if self._chuj_icon:
                scores = [p.total_score for p in self.s.game_state.players]
                max_score = max(scores)
                if scores.count(max_score) < len(scores) and player.total_score == max_score:
                    place_icon(self._chuj_icon)

            # Declaration badge
            current_round = self.s.game_state.current_round
            if current_round and current_round.declaration_player == i:
                decl_type = current_round.declaration_type
                badge = self._declaration_badges.get(decl_type)
                if badge:
                    place_icon(badge)

    def draw_buttons(self):
        """Nakreslí vždy viditeľné tlačidlá + preparation tlačidlá."""
        if (self.s.game_state.current_round and
                self.s.game_state.current_round.trick_number > 0):
            self.draw_button(
                self._button_last_trick_rect(), "Posledný štich",
                COLOR_BUTTON_SECONDARY
            )
        self.draw_button(self._button_chujogram_rect(), "Chujogram", COLOR_BUTTON_SECONDARY)
        self.draw_button(self._button_sort_rect(), "Zoradiť", COLOR_BUTTON_SECONDARY)
        self.draw_button(self._button_info_rect(), "Pravidlá", COLOR_BUTTON_SECONDARY)
        self.draw_button(self._button_menu_rect(), "Menu", COLOR_BUTTON_SECONDARY)

        phase = (self.s.game_state.current_round.phase
                 if self.s.game_state.current_round else None)

        if phase == "preparation" and self.s.game_state.is_human_turn:
            color_all = (COLOR_BUTTON_PRIMARY if self.s.active_declaration == "all"
                         else COLOR_BUTTON_SECONDARY)
            self.draw_button(
                self._button_decl_all_rect(), "Beriem všetko  [-20b]", color_all
            )
            color_none = (COLOR_BUTTON_PRIMARY if self.s.active_declaration == "none"
                          else COLOR_BUTTON_SECONDARY)
            self.draw_button(
                self._button_decl_none_rect(), "Nechytím nič  [-10b]", color_none
            )
            self.draw_button(self._button_ok_rect(), "OK", COLOR_BUTTON_PRIMARY)

    def draw_phase_overlay(self):
        """Nakreslí overlay pre fázy záväzku a vysvietenia."""
        if not self.s.game_state.current_round:
            return
        phase = self.s.game_state.current_round.phase
        if phase == "game_declaration":
            self._draw_declaration_overlay()
        elif phase == "revealing":
            self._draw_revealing_overlay()

    def draw_message(self):
        """Zobrazí dočasnú správu v strede obrazovky."""
        if not self.s.message or pygame.time.get_ticks() >= self.s.message_timer:
            return

        surf = self.font_large.render(self.s.message, True, COLOR_YELLOW)
        msg_w = surf.get_width() + 60
        msg_h = surf.get_height() + 20
        msg_x = TABLE_CENTER_X - msg_w // 2
        msg_y = 790 - msg_h // 2

        overlay = pygame.Surface((msg_w, msg_h), pygame.SRCALPHA)
        overlay.fill((25, 15, 8, 200))
        self.surface.blit(overlay, (msg_x, msg_y))
        pygame.draw.rect(
            self.surface, COLOR_GOLD,
            (msg_x, msg_y, msg_w, msg_h),
            width=2, border_radius=8
        )
        text_rect = surf.get_rect(center=(TABLE_CENTER_X, msg_y + msg_h // 2))
        self.surface.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Interné overlay metódy
    # ------------------------------------------------------------------

    def _draw_declaration_overlay(self):
        current_index = self.s.declaration_index
        player = self.s.game_state.players[current_index]

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.surface.blit(overlay, (0, 0))

        panel_w, panel_h = 500, 250
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = SCREEN_HEIGHT // 2 - panel_h // 2

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 12, 5, 230))
        self.surface.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(
            self.surface, COLOR_GOLD,
            (panel_x, panel_y, panel_w, panel_h),
            width=2, border_radius=10
        )

        title = self.font_large.render(
            f"{player.name} — záväzok?", True, COLOR_GOLD
        )
        title_rect = title.get_rect(centerx=SCREEN_WIDTH // 2, top=panel_y + 20)
        self.surface.blit(title, title_rect)

        if player.is_human:
            self.draw_button(
                self._button_decl_all_rect(), "Všetky štichy -20b", COLOR_BUTTON_PRIMARY
            )
            self.draw_button(
                self._button_decl_none_rect(), "Žiadny trestný bod -10b", COLOR_BUTTON_PRIMARY
            )
            self.draw_button(
                self._button_decl_pass_rect(), "Bez záväzku", COLOR_BUTTON_SECONDARY
            )

    def _draw_revealing_overlay(self):
        current_index = self.s.revealing_index
        player = self.s.game_state.players[current_index]

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.surface.blit(overlay, (0, 0))

        panel_w, panel_h = 500, 220
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = SCREEN_HEIGHT // 2 - panel_h // 2 - 50

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 12, 5, 230))
        self.surface.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(
            self.surface, COLOR_GOLD,
            (panel_x, panel_y, panel_w, panel_h),
            width=2, border_radius=10
        )

        title = self.font_large.render(
            f"{player.name} — vysvietenie?", True, COLOR_GOLD
        )
        title_rect = title.get_rect(centerx=SCREEN_WIDTH // 2, top=panel_y + 15)
        self.surface.blit(title, title_rect)

        if player.is_human:
            if player.hand.has_leaf_over() and not player.illuminated_leaf:
                self.draw_button(
                    self._button_reveal_leaf_rect(), "Zelený horník (16b)", COLOR_BUTTON_PRIMARY
                )
            if player.hand.has_acorn_over() and not player.illuminated_acorn:
                self.draw_button(
                    self._button_reveal_acorn_rect(), "Žaluďový horník (8b)", COLOR_BUTTON_PRIMARY
                )
            self.draw_button(
                self._button_reveal_pass_rect(), "Hotovo", COLOR_BUTTON_SECONDARY
            )

    # ------------------------------------------------------------------
    # Primitív tlačidla
    # ------------------------------------------------------------------

    def draw_button(self, rect: pygame.Rect, text: str, color: tuple):
        """Nakreslí jedno tlačidlo s hover efektom."""
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)
        alpha = 240 if is_hover else 200

        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        self.surface.blit(overlay, (rect.x, rect.y))

        if is_hover:
            hover_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            hover_surf.fill((255, 255, 255, 25))
            self.surface.blit(hover_surf, (rect.x, rect.y))

        border_color = COLOR_WHITE if is_hover else COLOR_GOLD
        pygame.draw.rect(self.surface, border_color, rect, width=2, border_radius=BUTTON_RADIUS)

        surf = self.font_medium.render(text, True, COLOR_WHITE)
        text_rect = surf.get_rect(center=rect.center)
        self.surface.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Button rects
    # ------------------------------------------------------------------
    @staticmethod
    def _button_last_trick_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_LAST_TRICK_X, BUTTON_LAST_TRICK_Y,
                           BUTTON_LAST_TRICK_WIDTH, BUTTON_LAST_TRICK_HEIGHT)

    @staticmethod
    def _button_chujogram_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_CHUJOGRAM_X, BUTTON_CHUJOGRAM_Y,
                           BUTTON_CHUJOGRAM_W, BUTTON_CHUJOGRAM_H)

    @staticmethod
    def _button_sort_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_SORT_X, BUTTON_SORT_Y, BUTTON_SORT_WIDTH, BUTTON_SORT_HEIGHT)

    @staticmethod
    def _button_info_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_INFO_X, BUTTON_INFO_Y, BUTTON_INFO_WIDTH, BUTTON_INFO_HEIGHT)

    @staticmethod
    def _button_menu_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_MENU_X, BUTTON_MENU_Y, BUTTON_MENU_WIDTH, BUTTON_MENU_HEIGHT)

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