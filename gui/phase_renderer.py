import pygame, os
from gui import display, layout
from config import (
    COLOR_WHITE, COLOR_GOLD, COLOR_YELLOW,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE,
    BUTTON_RADIUS,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
)


class PhaseRenderer:
    """Kreslenie UI overlayov, tlačidiel a správ pre Screen."""

    def __init__(self, canvas, screen_ref):
        # canvas = gui/canvas.py::Canvas nad oknom (rework rozlíšení, krok 5)
        self.canvas = canvas
        self.s = screen_ref

        self.font_medium = self.canvas.font(FONT_SIZE_MEDIUM)
        self.font_large = self.canvas.font(FONT_SIZE_LARGE)

        # Chuj ikonka
        chuj_path = os.path.join("assets", "graphics", "chuj.png")
        try:
            self._chuj_icon = self.canvas.image(chuj_path, (100, 100))
        except (FileNotFoundError, pygame.error):
            self._chuj_icon = None

        # Declaration badges
        self._declaration_badges = {}
        for key in ("all", "none"):
            path = os.path.join("assets", "graphics", f"{key}.png")
            try:
                self._declaration_badges[key] = self.canvas.image(path, (200, 200))
            except (FileNotFoundError, pygame.error):
                self._declaration_badges[key] = None
    # ------------------------------------------------------------------
    # Hlavné draw metódy (volané z Screen._draw)
    # ------------------------------------------------------------------

    def draw_player_labels(self):
        """Nakreslí menovky hráčov."""
        font = self.canvas.font(28)
        label_positions = layout.game().label_positions
        for i, player in enumerate(self.s.game_state.players):
            pos = label_positions[i]
            surf = font.render(player.name, True, COLOR_WHITE)
            rect = surf.get_rect(center=pos)

            bg_rect = rect.inflate(16, 8)
            self.canvas.overlay(pygame.Rect(bg_rect.topleft, (bg_rect.width, bg_rect.height)), (0, 0, 0, 160))
            self.canvas.rect(COLOR_GOLD, bg_rect, width=1, border_radius=6)
            self.canvas.blit(surf, rect)

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
                self.canvas.blit(icon_surf, ir)

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
        """Nakreslí vždy viditeľné tlačidlá + preparation tlačidlá.

        Každé tlačidlo sa najprv spýta Screen._shows() — v ostrej hre to je
        vždy True (teda bez zmeny), naskriptovaná lekcia tým UI postupne
        odhaľuje. Spracovanie klikov v Screen._handle_click a
        PreparationHandler sa pýta ROVNAKO, nech sa nedá kliknúť na
        neviditeľné tlačidlo.
        """
        shows = self.s._shows

        if (shows("last_trick") and self.s.game_state.current_round and
                self.s.game_state.current_round.trick_number > 0):
            self.draw_button(
                self._button_last_trick_rect(), "Posledný štich",
                COLOR_BUTTON_SECONDARY
            )
        if shows("tips"):
            tips_on = getattr(self.s, "tips_enabled", False)
            self.draw_button(
                self._button_tips_rect(),
                "Tipy: ZAP" if tips_on else "Tipy: VYP",
                COLOR_BUTTON_PRIMARY if tips_on else COLOR_BUTTON_SECONDARY
            )
        if shows("chujogram"):
            self.draw_button(self._button_chujogram_rect(), "Chujogram", COLOR_BUTTON_SECONDARY)
        if shows("info"):
            self.draw_button(self._button_info_rect(), "Pravidlá", COLOR_BUTTON_SECONDARY)
        if shows("menu"):
            self.draw_button(self._button_menu_rect(), "Menu", COLOR_BUTTON_SECONDARY)

        phase = (self.s.game_state.current_round.phase
                 if self.s.game_state.current_round else None)

        if phase == "preparation" and self.s.game_state.is_human_turn:
            if shows("declaration"):
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
            if shows("ok"):
                self.draw_button(self._button_ok_rect(), "OK", COLOR_BUTTON_PRIMARY)
    def draw_message(self):
        """Zobrazí dočasnú správu v strede obrazovky."""
        if not self.s.message or pygame.time.get_ticks() >= self.s.message_timer:
            return

        surf = self.font_large.render(self.s.message, True, COLOR_YELLOW)
        msg_w = surf.get_width() + 60
        msg_h = surf.get_height() + 20
        tcx = layout.game().table_center[0]
        msg_x = tcx - msg_w // 2
        msg_y = layout.game().message_center_y - msg_h // 2

        self.canvas.overlay(pygame.Rect((msg_x, msg_y), (msg_w, msg_h)), (25, 15, 8, 200))
        self.canvas.rect(COLOR_GOLD,
            (msg_x, msg_y, msg_w, msg_h),
            width=2, border_radius=8
        )
        text_rect = surf.get_rect(center=(tcx, msg_y + msg_h // 2))
        self.canvas.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Interné overlay metódy
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Primitív tlačidla
    # ------------------------------------------------------------------

    def draw_button(self, rect: pygame.Rect, text: str, color: tuple):
        """Nakreslí jedno tlačidlo s hover efektom."""
        mouse_pos = display.mouse_pos()
        is_hover = rect.collidepoint(mouse_pos)
        alpha = 240 if is_hover else 200

        self.canvas.overlay(pygame.Rect((rect.x, rect.y), (rect.width, rect.height)), (*color, alpha))

        if is_hover:
            self.canvas.overlay(pygame.Rect((rect.x, rect.y), (rect.width, rect.height)), (255, 255, 255, 25))

        border_color = COLOR_WHITE if is_hover else COLOR_GOLD
        self.canvas.rect(border_color, rect, width=2, border_radius=BUTTON_RADIUS)

        surf = self.font_medium.render(text, True, COLOR_WHITE)
        text_rect = surf.get_rect(center=rect.center)
        self.canvas.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Button rects
    # ------------------------------------------------------------------
    @staticmethod
    def _button_last_trick_rect() -> pygame.Rect:
        return layout.game().column_rect(layout.COLUMN_SLOTS["last_trick"])

    @staticmethod
    def _button_tips_rect() -> pygame.Rect:
        return layout.game().column_rect(layout.COLUMN_SLOTS["tips"])

    @staticmethod
    def _button_chujogram_rect() -> pygame.Rect:
        return layout.game().column_rect(layout.COLUMN_SLOTS["chujogram"])

    @staticmethod
    def _button_info_rect() -> pygame.Rect:
        return layout.game().column_rect(layout.COLUMN_SLOTS["info"])

    @staticmethod
    def _button_menu_rect() -> pygame.Rect:
        return layout.game().column_rect(layout.COLUMN_SLOTS["menu"])

    @staticmethod
    def _button_decl_all_rect() -> pygame.Rect:
        return layout.game().decl_all_rect()

    @staticmethod
    def _button_decl_none_rect() -> pygame.Rect:
        return layout.game().decl_none_rect()

    @staticmethod
    def _button_ok_rect() -> pygame.Rect:
        return layout.game().ok_rect()
