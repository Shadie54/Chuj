import pygame, os, math
from gui import display, layout, ui_style
from config import (
    COLOR_WHITE,
    FONT_SIZE_MEDIUM, FONT_SIZE_LARGE,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
)


# Stĺpec tlačidiel vpravo dole — tlačidlo s okrúhlym medailónom a ikonkou
# vľavo (grafický rework 2026-10-28, štýl gui/ui_style.py).
COLUMN_ICON_FILES = {
    "tips": "tips.png",
    "last_trick": "last_trick.png",
    "chujogram": "chujogram.png",
    "info": "rules.png",
    "menu": "menu.png",
}
COLUMN_MEDALLION_R = 27        # polomer medailónu (tlačidlo je vysoké 46)
COLUMN_ICON_SIZE = 37          # ikonka vnútri medailónu
COLUMN_RADIUS = 12            # zaoblenie rohov tlačidla
COLUMN_TEXT_X = 64             # začiatok textu od ľavého okraja tlačidla


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

        # Ikonky stĺpca tlačidiel vpravo dole (assets/graphics, 512×512 —
        # Canvas ich zmenší z plného rozlíšenia, takže sú ostré aj pri 4K).
        self._column_icons = {}
        for key in COLUMN_ICON_FILES:
            path = os.path.join("assets", "graphics", COLUMN_ICON_FILES[key])
            try:
                self._column_icons[key] = self.canvas.image(
                    path, (COLUMN_ICON_SIZE, COLUMN_ICON_SIZE))
            except (FileNotFoundError, pygame.error):
                self._column_icons[key] = None
    # ------------------------------------------------------------------
    # Hlavné draw metódy (volané z Screen._draw)
    # ------------------------------------------------------------------

    def draw_player_labels(self):
        """Nakreslí menovky hráčov."""
        font = self.canvas.font(28)
        label_positions = layout.game().label_positions
        current_round = self.s.game_state.current_round
        on_turn = (current_round.get_current_player_index()
                   if current_round and current_round.phase == "tricks" else None)
        for i, player in enumerate(self.s.game_state.players):
            pos = label_positions[i]
            # Štýl gui/ui_style.py (rework 2026-10-28): tmavý štítok so
            # zlatohnedým rámom; hráč na ťahu má zlatý rám a zlaté meno
            # (rovnako ako v paneli KOLO).
            active = i == on_turn
            surf = font.render(player.name, True,
                               ui_style.BTN_TEXT_HOVER if active else ui_style.TEXT)
            rect = surf.get_rect(center=pos)

            bg_rect = rect.inflate(24, 10)
            self.canvas.overlay(bg_rect.move(0, 3), (0, 0, 0, 90), border_radius=8)
            self.canvas.overlay(bg_rect, (17, 11, 7, 225), border_radius=8)
            self.canvas.rect(ui_style.GOLD if active else ui_style.GOLD_SOFT, bg_rect,
                             width=2, border_radius=8)
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
            self.draw_column_button(
                self._button_last_trick_rect(), "Posledný štich", "last_trick",
                blink=self._blink("last_trick")
            )
        if shows("tips"):
            tips_on = getattr(self.s, "tips_enabled", False)
            self.draw_column_button(
                self._button_tips_rect(),
                "Tipy: ZAP" if tips_on else "Tipy: VYP", "tips",
                active=tips_on
            )
        if shows("chujogram"):
            self.draw_column_button(
                self._button_chujogram_rect(), "Chujogram", "chujogram",
                blink=self._blink("chujogram")
            )
        if shows("info"):
            self.draw_column_button(
                self._button_info_rect(), "Pravidlá", "info",
                blink=self._blink("info")
            )
        if shows("menu"):
            self.draw_column_button(self._button_menu_rect(), "Menu", "menu")

        phase = (self.s.game_state.current_round.phase
                 if self.s.game_state.current_round else None)

        if phase == "preparation" and self.s.game_state.is_human_turn:
            if shows("declaration"):
                color_all = (COLOR_BUTTON_PRIMARY if self.s.active_declaration == "all"
                             else COLOR_BUTTON_SECONDARY)
                self.draw_button(
                    self._button_decl_all_rect(), "Beriem všetko  [-20b]", color_all,
                    blink=self._blink("decl_all")
                )
                color_none = (COLOR_BUTTON_PRIMARY if self.s.active_declaration == "none"
                              else COLOR_BUTTON_SECONDARY)
                self.draw_button(
                    self._button_decl_none_rect(), "Nechytím nič  [-10b]", color_none,
                    blink=self._blink("decl_none")
                )
            if shows("ok"):
                self.draw_button(
                    self._button_ok_rect(), "OK", COLOR_BUTTON_PRIMARY,
                    blink=self._blink("ok")
                )

    def _blink(self, element: str) -> bool:
        """Má tlačidlo pulzovať — pripomienka, že na neho treba kliknúť?

        Voliteľný hák directora, analogický k Screen._shows() (napr.
        tutorial/tutorial_director.py, tutorial/zavazok_director.py).
        V ostrej hre director blink() nemá, getattr vráti None a nič
        sa nemení. Kľúče: "decl_all", "decl_none", "ok", "last_trick",
        "chujogram", "info".
        """
        hint = getattr(self.s.director, "blink", None)
        return bool(hint and hint(element))

    def draw_message(self):
        """Zobrazí dočasnú správu v strede obrazovky."""
        if not self.s.message or pygame.time.get_ticks() >= self.s.message_timer:
            return

        surf = self.font_large.render(self.s.message, True, ui_style.BTN_TEXT_HOVER)
        msg_w = surf.get_width() + 60
        msg_h = surf.get_height() + 20
        tcx = layout.game().table_center[0]
        msg_x = tcx - msg_w // 2
        msg_y = layout.game().message_center_y - msg_h // 2

        # Štýl panelov gui/ui_style.py (rework 2026-10-28)
        ui_style.draw_panel(self.canvas, (msg_x, msg_y, msg_w, msg_h))
        text_rect = surf.get_rect(center=(tcx, msg_y + msg_h // 2))
        self.canvas.blit(surf, text_rect)

    # ------------------------------------------------------------------
    # Interné overlay metódy
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Primitív tlačidla
    # ------------------------------------------------------------------

    def draw_button(self, rect: pygame.Rect, text: str, color: tuple, blink: bool = False):
        """Tlačidlá záväzku a OK v štýle gui/ui_style.py (rework 2026-10-28):
        COLOR_BUTTON_PRIMARY (zvolený záväzok, OK) = úroveň 1 (zlatohnedá),
        inak úroveň 3 (tmavá). blink = pulzovanie z tutoriálu navrch."""
        is_hover = rect.collidepoint(display.mouse_pos())
        tier = 1 if color == COLOR_BUTTON_PRIMARY else 3
        ui_style.draw_button(self.canvas, rect, text, self.font_medium, tier,
                             is_hover)
        if blink:
            pulse = abs(math.sin(math.pi * (pygame.time.get_ticks() % 1200) / 1200))
            self.canvas.overlay(rect, (255, 255, 255, int(30 + 70 * pulse)),
                                border_radius=ui_style.BTN_RADIUS)
            self.canvas.rect(COLOR_WHITE, rect, width=2 + round(2 * pulse),
                             border_radius=ui_style.BTN_RADIUS)

    def draw_column_button(self, rect: pygame.Rect, text: str, icon_key: str,
                           active: bool = False, blink: bool = False):
        """Tlačidlo stĺpca vpravo dole: tmavé zaoblené tlačidlo so zlatohnedým
        rámom, vľavo okrúhly medailón so zlatou ikonkou, text zarovnaný
        za ním. active=True (Tipy: ZAP) = zlatohnedá výplň (úroveň 1).
        blink = pulzujúce zvýraznenie z tutoriálu (pozri _blink)."""
        c = self.canvas
        is_hover = rect.collidepoint(display.mouse_pos())
        radius = COLUMN_RADIUS
        fill, highlight, border, text_color = ui_style.BTN_TIERS[1 if active else 3]

        c.overlay(rect.move(0, 3), (0, 0, 0, 100), border_radius=radius)
        c.overlay(rect, fill, border_radius=radius)
        top = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4, rect.height // 2 - 2)
        c.overlay(top, (255, 214, 140, highlight), border_radius=radius - 2)
        if is_hover:
            c.overlay(rect, (255, 214, 140, 24), border_radius=radius)
            border, text_color = ui_style.BTN_BORDER_HOVER, ui_style.BTN_TEXT_HOVER

        border_width = 2
        if blink:
            pulse = abs(math.sin(math.pi * (pygame.time.get_ticks() % 1200) / 1200))
            c.overlay(rect, (255, 255, 255, int(30 + 70 * pulse)),
                      border_radius=radius)
            border = COLOR_WHITE
            border_width = 2 + round(2 * pulse)
        c.rect(border, rect, width=border_width, border_radius=radius)

        # Medailón s ikonkou (presahuje výšku tlačidla, ako v návrhu)
        mx, my = rect.x + rect.height // 2, rect.centery
        r = COLUMN_MEDALLION_R
        c.circle((0, 0, 0), (mx + 1, my + 3), r)                 # tieň
        c.circle((22, 14, 8), (mx, my), r)
        ring = (ui_style.BTN_BORDER_HOVER if is_hover or blink
                else ui_style.GOLD)
        c.circle(ring, (mx, my), r, width=2)
        c.circle((96, 70, 34), (mx, my), r - 4, width=1)
        icon = self._column_icons.get(icon_key)
        if icon is not None:
            c.blit(icon, icon.get_rect(center=(mx, my)))

        surf = self.font_medium.render(text, True, text_color)
        c.blit(surf, surf.get_rect(midleft=(rect.x + COLUMN_TEXT_X, rect.centery)))

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
