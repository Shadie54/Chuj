import sys
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
import os
import pygame

from game.card import Card
from tester.scenario import Scenario
from tester.tester_engine import TesterEngine, StepResult
from tester.tester_logger import TesterLogger, LogEntry
from tester.random_scenario import random_scenario, save_last_seed
from config import (
    CARDS_SMALL_PATH, CARD_SIZE_SMALL, CARD_BACK_IMAGE,
    NUM_PLAYERS,
    BUTTON_RADIUS,
)

# ------------------------------------------------------------------
# Lokálne farby
# ------------------------------------------------------------------

T_BG = (245, 245, 245)
T_PANEL_BG = (255, 255, 255)
T_HEADER_BG = (230, 230, 230)
T_SIDEBAR_BG = (220, 222, 228)
T_TEXT = (20, 20, 20)
T_TEXT_DIM = (100, 100, 100)
T_BORDER = (180, 180, 180)
T_HIGHLIGHT = (200, 140, 30)
T_BUTTON_BG = (220, 220, 220)
T_BUTTON_PRIMARY = (180, 200, 230)
T_BUTTON_DANGER = (230, 180, 180)
T_BUTTON_SUCCESS = (180, 230, 180)
T_SUCCESS = (40, 130, 40)
T_WARNING = (180, 40, 40)

# ------------------------------------------------------------------
# Konštanty layoutu
# ------------------------------------------------------------------

WIN_WIDTH = 1800
WIN_HEIGHT = 980

SIDEBAR_WIDTH = 260
STATUS_HEIGHT = 40

TABLE_X = SIDEBAR_WIDTH
TABLE_WIDTH = 1000
TABLE_HEIGHT = WIN_HEIGHT - STATUS_HEIGHT
TABLE_Y = 0

LOG_X = SIDEBAR_WIDTH + TABLE_WIDTH
LOG_Y = 0
LOG_WIDTH = WIN_WIDTH - SIDEBAR_WIDTH - TABLE_WIDTH
LOG_HEIGHT = WIN_HEIGHT - STATUS_HEIGHT

TABLE_CENTER_X = TABLE_X + TABLE_WIDTH // 2
TABLE_CENTER_Y = TABLE_Y + TABLE_HEIGHT // 2

CARD_W, CARD_H = CARD_SIZE_SMALL
HAND_H_OVERLAP = 25
HAND_V_OVERLAP = 100

HAND_POS = {
    0: (TABLE_CENTER_X, TABLE_Y + TABLE_HEIGHT - CARD_H // 2 - 20, "horizontal"),
    1: (TABLE_X + TABLE_WIDTH - CARD_W // 2 - 20, TABLE_CENTER_Y, "vertical"),
    2: (TABLE_CENTER_X, TABLE_Y + CARD_H // 2 + 20, "horizontal"),
    3: (TABLE_X + CARD_W // 2 + 20, TABLE_CENTER_Y, "vertical"),
}

TRICK_OFFSET = 80
TRICK_POS = {
    0: (TABLE_CENTER_X, TABLE_CENTER_Y + TRICK_OFFSET),
    1: (TABLE_CENTER_X + TRICK_OFFSET, TABLE_CENTER_Y),
    2: (TABLE_CENTER_X, TABLE_CENTER_Y - TRICK_OFFSET),
    3: (TABLE_CENTER_X - TRICK_OFFSET, TABLE_CENTER_Y),
}

LABEL_POS = {
    0: (TABLE_CENTER_X, TABLE_Y + TABLE_HEIGHT - 8),
    1: (TABLE_X + TABLE_WIDTH - CARD_W - 50, TABLE_Y + 30),
    2: (TABLE_CENTER_X, TABLE_Y + 8),
    3: (TABLE_X + CARD_W + 50, TABLE_Y + 30),
}

AUTOPLAY_DELAY_MS = 400

# Sidebar layout
SB_PAD = 10          # padding
SB_BTN_H = 34        # výška tlačidla
SB_BTN_GAP = 6       # medzera medzi tlačidlami
SB_SECTION_GAP = 30  # medzera medzi sekciami
SB_LABEL_H = 30  # výška labelu nad skupinou tlačidiel
SB_INNER_W = SIDEBAR_WIDTH - SB_PAD * 2  # vnútorná šírka


class TesterScreen:
    def __init__(self, scenario: Scenario):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption(f"Chuj Tester — {scenario.name}")
        self.clock = pygame.time.Clock()

        self.scenario = scenario
        self.engine = TesterEngine(scenario)

        self.running = True
        self.last_step: StepResult | None = None

        self.autoplay_mode: str | None = None
        self.autoplay_next_time: int = 0
        self.override_mode: bool = False

        self.card_images: dict[str, pygame.Surface] = {}
        self.card_back: pygame.Surface | None = None
        self._load_card_images()

        font_name = "segoeui,arial,dejavusans,liberationsans"
        mono_name = "consolas,dejavusansmono,couriernew,courier"
        self.font_small = pygame.font.SysFont(font_name, 18)
        self.font_medium = pygame.font.SysFont(font_name, 22)
        self.font_large = pygame.font.SysFont(font_name, 28)
        self.font_mono = pygame.font.SysFont(mono_name, 15)

        self.seed_input: str = ""  # aktuálny text v inpute
        self.seed_input_active: bool = False  # či je input aktívny
    # ------------------------------------------------------------------
    # Load assets
    # ------------------------------------------------------------------

    def _load_card_images(self):
        from config import SUITS, RANKS
        for suit in SUITS:
            for rank in RANKS:
                filename = f"{suit}-{rank}.png"
                path = os.path.join(CARDS_SMALL_PATH, filename)
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.card_images[filename] = img
                except (pygame.error, FileNotFoundError):
                    pass
        back_path = os.path.join(CARDS_SMALL_PATH, CARD_BACK_IMAGE)
        try:
            self.card_back = pygame.image.load(back_path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            self.card_back = None

    def _get_card_image(self, card: Card) -> pygame.Surface | None:
        return self.card_images.get(card.image_name)

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self):
        while self.running:
            self.clock.tick(30)
            self._handle_events()
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self):
        self._tick_autoplay()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                # Seed input má prednosť
                if self.seed_input_active:
                    if event.key == pygame.K_RETURN:
                        self._on_seed_load_clicked()
                    elif event.key == pygame.K_BACKSPACE:
                        self.seed_input = self.seed_input[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self.seed_input_active = False
                        self.seed_input = ""
                    elif event.unicode.isdigit():
                        self.seed_input += event.unicode
                else:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key in (pygame.K_SPACE, pygame.K_RIGHT):
                        self._on_next_clicked()
                    elif event.key == pygame.K_RETURN:
                        self._on_next_clicked()
                    elif event.key == pygame.K_o:
                        self._on_override_clicked()
                    elif event.key == pygame.K_e:
                        self._on_export_clicked()
                    elif event.key == pygame.K_LEFT:
                        self._on_back_clicked()
                    elif event.key == pygame.K_r:
                        self._on_reset_clicked()
                    elif event.key == pygame.K_t:
                        self._on_trick_clicked()
                    elif event.key == pygame.K_g:
                        self._on_random_clicked()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _tick_autoplay(self):
        if self.autoplay_mode is None:
            return
        if self.engine.is_complete():
            self.autoplay_mode = None
            return
        now = pygame.time.get_ticks()
        if now < self.autoplay_next_time:
            return
        try:
            self.last_step = self.engine.next_step()
        except Exception as e:
            print(f"ERROR pri autoplay: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            self.autoplay_mode = None
            return
        if self.autoplay_mode == "trick" and self.last_step.trick_completed:
            self.autoplay_mode = None
            return
        if self.autoplay_mode == "round" and self.last_step.round_completed:
            self.autoplay_mode = None
            return
        self.autoplay_next_time = now + AUTOPLAY_DELAY_MS

    def _handle_click(self, pos: tuple[int, int]):
        # Sidebar kliky
        if pos[0] < SIDEBAR_WIDTH:
            self._handle_sidebar_click(pos)
            return

        # Override mód — klik na kartu
        if self.override_mode:
            clicked = self._get_clicked_playable_card(pos)
            if clicked is not None:
                self._do_override(clicked)
            else:
                self.override_mode = False
            return

    # ------------------------------------------------------------------
    # Sidebar — kliky
    # ------------------------------------------------------------------

    def _handle_sidebar_click(self, pos: tuple[int, int]):
        rects = self._build_sidebar_rects()

        # Seed input — spracuj pred ostatnými
        if rects["seed_input"].collidepoint(pos):
            self.seed_input_active = True
            return
        if rects["seed_load"].collidepoint(pos):
            self._on_seed_load_clicked()
            return

        # Klik mimo seed input — deaktivuj
        self.seed_input_active = False

        # Akcie
        if rects["next"].collidepoint(pos):
            self._on_next_clicked()
        elif rects["back"].collidepoint(pos):
            self._on_back_clicked()
        elif rects["ai_toggle"].collidepoint(pos):  # ← pridať
            self._on_ai_toggle_clicked()  # ← pridať
        elif rects["override"].collidepoint(pos):
            self._on_override_clicked()
        elif rects["override"].collidepoint(pos):
            self._on_override_clicked()
        elif rects["trick"].collidepoint(pos):
            self._on_trick_clicked()
        elif rects["round"].collidepoint(pos):
            self._on_round_clicked()
        elif rects["reset"].collidepoint(pos):
            self._on_reset_clicked()
        elif rects["random"].collidepoint(pos):
            self._on_random_clicked()
        elif rects["export"].collidepoint(pos):
            self._on_export_clicked()
        elif rects["quit"].collidepoint(pos):
            self.running = False

        # First player
        for i in range(NUM_PLAYERS):
            if rects[f"first_{i}"].collidepoint(pos):
                self._set_first_player(i)
                return

        # Leaf
        for val in [None, 0, 1, 2, 3]:
            if rects[f"leaf_{val}"].collidepoint(pos):
                self._set_illumination("leaf", val)
                return

        # Acorn
        for val in [None, 0, 1, 2, 3]:
            if rects[f"acorn_{val}"].collidepoint(pos):
                self._set_illumination("acorn", val)
                return

        # Skóre
        for i in range(NUM_PLAYERS):
            if rects[f"score_nor_{i}"].collidepoint(pos):
                self._set_score(i, 0)
                return
            if rects[f"score_90_{i}"].collidepoint(pos):
                self._set_score(i, 90)
                return

    def _set_first_player(self, i: int):
        import copy
        new_sc = copy.copy(self.engine.scenario)
        new_sc.first_player_index = i
        self._reload_engine(new_sc)

    def _set_illumination(self, suit: str, val: int | None):
        import copy
        if val is not None:
            hand = self.engine.players[val].hand.cards
            has_it = any(
                c.is_leaf_over if suit == "leaf" else c.is_acorn_over
                for c in hand
            )
            if not has_it:
                return
        new_sc = copy.copy(self.engine.scenario)
        new_sc.illuminations = {**new_sc.illuminations, suit: val}
        self._reload_engine(new_sc)

    def _set_score(self, player_idx: int, score: int):
        import copy
        new_sc = copy.copy(self.engine.scenario)
        new_sc.scores = {**getattr(new_sc, 'scores', {}), player_idx: score}
        self._reload_engine(new_sc)
        self.last_step = None

    def _reload_engine(self, new_sc: Scenario):
        self.scenario = new_sc
        self.engine = TesterEngine(new_sc)
        self.last_step = None
        pygame.display.set_caption(f"Chuj Tester — {new_sc.name}")

    # ------------------------------------------------------------------
    # Sidebar — výpočet rectov
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sidebar_rects() -> dict[str, pygame.Rect]:
        rects = {}
        x = SB_PAD
        y = SB_PAD + 40  # 40px pre názov scenára

        def btn(key, w=SB_INNER_W, h=SB_BTN_H):
            nonlocal y
            r = pygame.Rect(x, y, w, h)
            rects[key] = r
            y += h + SB_BTN_GAP
            return r

        def section(label):
            nonlocal y
            y += SB_SECTION_GAP

        # --- AKCIE ---
        section("akcie")
        btn("next")
        btn("back")
        btn("ai_toggle")
        btn("override")
        # Štich + Kolo vedľa seba
        half = (SB_INNER_W - SB_BTN_GAP) // 2
        rects["trick"] = pygame.Rect(x, y, half, SB_BTN_H)
        rects["round"] = pygame.Rect(x + half + SB_BTN_GAP, y, half, SB_BTN_H)
        y += SB_BTN_H + SB_BTN_GAP
        # Reset + Random vedľa seba
        rects["reset"] = pygame.Rect(x, y, half, SB_BTN_H)
        rects["random"] = pygame.Rect(x + half + SB_BTN_GAP, y, half, SB_BTN_H)
        y += SB_BTN_H + SB_BTN_GAP
        # Seed input + Load vedľa seba
        input_w = SB_INNER_W - SB_BTN_GAP - 50
        rects["seed_input"] = pygame.Rect(x, y, input_w, SB_BTN_H)
        rects["seed_load"] = pygame.Rect(x + input_w + SB_BTN_GAP, y, 50, SB_BTN_H)
        y += SB_BTN_H + SB_BTN_GAP
        # Export + Quit vedľa seba
        rects["export"] = pygame.Rect(x, y, half, SB_BTN_H)
        rects["quit"] = pygame.Rect(x + half + SB_BTN_GAP, y, half, SB_BTN_H)
        y += SB_BTN_H + SB_BTN_GAP

        # --- SETUP ---
        section("setup")
        # First player — 4 malé tlačidlá
        small_w = (SB_INNER_W - SB_BTN_GAP * 3) // 4
        y += SB_LABEL_H  # miesto pre "First:"
        for i in range(NUM_PLAYERS):
            rects[f"first_{i}"] = pygame.Rect(
                x + i * (small_w + SB_BTN_GAP), y, small_w, SB_BTN_H
            )
        y += SB_BTN_H + SB_BTN_GAP

        # Leaf — 5 tlačidiel (– 0 1 2 3)
        tiny_w = (SB_INNER_W - SB_BTN_GAP * 4) // 5
        y += SB_LABEL_H  # miesto pre "Q♠:"
        for idx, val in enumerate([None, 0, 1, 2, 3]):
            rects[f"leaf_{val}"] = pygame.Rect(
                x + idx * (tiny_w + SB_BTN_GAP), y, tiny_w, SB_BTN_H
            )
        y += SB_BTN_H + SB_BTN_GAP

        # Acorn
        y += SB_LABEL_H  # miesto pre "Q♣:"
        for idx, val in enumerate([None, 0, 1, 2, 3]):
            rects[f"acorn_{val}"] = pygame.Rect(
                x + idx * (tiny_w + SB_BTN_GAP), y, tiny_w, SB_BTN_H
            )
        y += SB_BTN_H + SB_BTN_GAP

        # --- SKÓRE ---
        section("skore")
        score_btn_w = (SB_INNER_W - SB_BTN_GAP) // 2
        for i in range(NUM_PLAYERS):
            y += SB_LABEL_H  # miesto pre "AI_X: Xb" nad každým hráčom
            rects[f"score_nor_{i}"] = pygame.Rect(x, y, score_btn_w, SB_BTN_H)
            rects[f"score_90_{i}"] = pygame.Rect(x + score_btn_w + SB_BTN_GAP, y, score_btn_w, SB_BTN_H)
            y += SB_BTN_H + SB_BTN_GAP

        return rects

    # ------------------------------------------------------------------
    # Akcie
    # ------------------------------------------------------------------

    def _on_next_clicked(self):
        if self.engine.is_complete():
            return
        try:
            self.last_step = self.engine.next_step()
        except Exception as e:
            print(f"ERROR pri next_step(): {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()

    def _on_back_clicked(self):
        if self.autoplay_mode is not None or not self.engine.can_go_back():
            return
        try:
            self.engine.go_back()
        except Exception as e:
            print(f"ERROR pri go_back(): {type(e).__name__}: {e}")
            return
        self.last_step = None

    def _on_ai_toggle_clicked(self):
        """Prepne starý/nový AI systém pre všetkých hráčov a reštartuje scenár."""
        # Zisti aktuálny stav
        current = getattr(self.engine.ais[0], 'use_new_system', False)
        new_value = not current

        # Ulož do scenára ako flag — engine ho použije pri _load_scenario()
        self.scenario._use_new_system = new_value

        # Reštartuj engine
        self.engine.reset()

    def _on_override_clicked(self):
        if self.autoplay_mode is not None or self.engine.is_complete():
            return
        self.engine.prepare_for_override()
        self.override_mode = True

    def _on_trick_clicked(self):
        if self.engine.is_complete() or self.autoplay_mode is not None:
            return
        self.autoplay_mode = "trick"
        self.autoplay_next_time = pygame.time.get_ticks()

    def _on_round_clicked(self):
        if self.engine.is_complete() or self.autoplay_mode is not None:
            return
        self.autoplay_mode = "round"
        self.autoplay_next_time = pygame.time.get_ticks()

    def _on_reset_clicked(self):
        self.engine.reset()
        self.last_step = None

    def _on_random_clicked(self):
        self.autoplay_mode = None
        new_scenario = random_scenario()
        seed = int(new_scenario.name.split("_")[-1])
        save_last_seed(seed)
        self._reload_engine(new_scenario)

    def _on_export_clicked(self):
        try:
            text = self._format_export()
            with open("tester_export.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("[Export] Uložené do tester_export.txt")
        except Exception as e:
            print(f"[Export] CHYBA: {type(e).__name__}: {e}")

    def _on_seed_load_clicked(self):
        try:
            seed = int(self.seed_input.strip())
            self.seed_input = ""
            self.seed_input_active = False
            new_scenario = random_scenario(seed=seed)
            save_last_seed(seed)
            self._reload_engine(new_scenario)
        except ValueError:
            self.seed_input = ""  # neplatný vstup — vyčisti

    def _do_override(self, card: Card):
        try:
            self.last_step = self.engine.next_step_override(card)
        except Exception as e:
            print(f"ERROR pri override: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
        finally:
            self.override_mode = False

    def _get_clicked_playable_card(self, pos: tuple[int, int]) -> Card | None:
        state = self.engine.current_state()
        if state.is_complete:
            return None
        player_idx = state.current_player_index
        cards = state.hands[player_idx]
        if self.engine.round.current_trick is None:
            return None
        playable = self.engine.players[player_idx].hand.get_playable_cards(
            self.engine.round.current_trick.lead_suit,
            self.engine.round.trick_number,
        )
        center_x, center_y, orientation = HAND_POS[player_idx]
        n = len(cards)
        rects = []
        if orientation == "horizontal":
            total_w = CARD_W + (n - 1) * (CARD_W - HAND_H_OVERLAP)
            start_x = center_x - total_w // 2
            for i, c in enumerate(cards):
                x = start_x + i * (CARD_W - HAND_H_OVERLAP)
                y = center_y - CARD_H // 2
                rects.append((c, pygame.Rect(x, y, CARD_W, CARD_H)))
        else:
            total_h = CARD_H + (n - 1) * (CARD_H - HAND_V_OVERLAP)
            start_y = center_y - total_h // 2
            for i, c in enumerate(cards):
                x = center_x - CARD_W // 2
                y = start_y + i * (CARD_H - HAND_V_OVERLAP)
                rects.append((c, pygame.Rect(x, y, CARD_W, CARD_H)))
        for card, rect in reversed(rects):
            if rect.collidepoint(pos):
                return card if card in playable else None
        return None

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        self.screen.fill(T_BG)
        self._draw_sidebar()
        self._draw_table_bg()
        self._draw_hands()
        self._draw_trick()
        self._draw_player_labels()
        self._draw_log_panel()
        self._draw_status_bar()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _draw_sidebar(self):
        # Pozadie
        pygame.draw.rect(
            self.screen, T_SIDEBAR_BG,
            (0, 0, SIDEBAR_WIDTH, WIN_HEIGHT)
        )
        pygame.draw.line(
            self.screen, T_BORDER,
            (SIDEBAR_WIDTH, 0), (SIDEBAR_WIDTH, WIN_HEIGHT), 1
        )

        state = self.engine.current_state()
        rects = self._build_sidebar_rects()

        # Názov scenára
        name_surf = self.font_small.render(
            self.scenario.name, True, T_TEXT
        )
        self.screen.blit(name_surf, (SB_PAD, SB_PAD))

        # Autoplay indikátor
        if self.autoplay_mode:
            ap_surf = self.font_small.render("▶ AUTOPLAY", True, T_HIGHLIGHT)
            self.screen.blit(ap_surf, (SB_PAD, SB_PAD + 20))

        # --- AKCIE ---
        self._draw_section_label("AKCIE", rects["next"].top - SB_LABEL_H)
        next_color = T_BUTTON_PRIMARY
        self._draw_sb_button(rects["next"], "Next →", next_color)
        self._draw_sb_button(rects["back"], "← Back", T_BUTTON_BG)

        # AI systém toggle
        use_new = getattr(self.engine.ais[0], 'use_new_system', False)
        ai_label = "AI: NOVÝ" if use_new else "AI: STARÝ"
        ai_color = T_BUTTON_SUCCESS if use_new else T_BUTTON_BG
        self._draw_sb_button(rects["ai_toggle"], ai_label, ai_color)

        override_color = T_HIGHLIGHT if self.override_mode else T_BUTTON_BG
        self._draw_sb_button(
            rects["override"],
            "VYBER!" if self.override_mode else "Override",
            override_color
        )
        self._draw_sb_button(rects["trick"], "Štich", T_BUTTON_BG)
        self._draw_sb_button(rects["round"], "Kolo", T_BUTTON_BG)
        self._draw_sb_button(rects["reset"], "Reset", T_BUTTON_BG)
        self._draw_sb_button(rects["random"], "Random", T_BUTTON_PRIMARY)

        # Seed input
        seed_rect = rects["seed_input"]
        input_color = T_HIGHLIGHT if self.seed_input_active else T_BUTTON_BG
        pygame.draw.rect(self.screen, input_color, seed_rect, border_radius=BUTTON_RADIUS)
        pygame.draw.rect(self.screen, T_BORDER, seed_rect, width=1, border_radius=BUTTON_RADIUS)
        display_text = self.seed_input if self.seed_input else "seed..."
        text_color = T_TEXT if self.seed_input else T_TEXT_DIM
        surf = self.font_small.render(display_text, True, text_color)
        self.screen.blit(surf, surf.get_rect(center=seed_rect.center))
        self._draw_sb_button(rects["seed_load"], "Load", T_BUTTON_PRIMARY)

        self._draw_sb_button(rects["export"], "Export", T_BUTTON_BG)
        self._draw_sb_button(rects["quit"], "Quit", T_BUTTON_BG)

        # --- SETUP ---
        self._draw_section_label("SETUP", rects["first_0"].top - SB_LABEL_H * 2 - 2)

        # First player
        fp_label = self.font_small.render("First:", True, T_TEXT_DIM)
        self.screen.blit(fp_label, (SB_PAD, rects["first_0"].top - SB_LABEL_H + 2))
        for i in range(NUM_PLAYERS):
            active = self.engine.scenario.first_player_index == i
            self._draw_sb_button(
                rects[f"first_{i}"],
                f"{i}",
                T_HIGHLIGHT if active else T_BUTTON_BG
            )

        # Leaf
        leaf_label = self.font_small.render("Q♠:", True, T_TEXT_DIM)
        self.screen.blit(leaf_label, (SB_PAD, rects["leaf_None"].top - SB_LABEL_H + 2))
        current_leaf = state.illuminations.get("leaf")
        for val in [None, 0, 1, 2, 3]:
            active = current_leaf == val
            if val is not None:
                hand = self.engine.players[val].hand.cards
                has_it = any(c.is_leaf_over for c in hand)
                color = T_HIGHLIGHT if active else (T_BUTTON_BG if has_it else T_TEXT_DIM)
            else:
                color = T_HIGHLIGHT if active else T_BUTTON_BG
            self._draw_sb_button(
                rects[f"leaf_{val}"],
                "–" if val is None else str(val),
                color
            )

        # Acorn
        acorn_label = self.font_small.render("Q♣:", True, T_TEXT_DIM)
        self.screen.blit(acorn_label, (SB_PAD, rects["acorn_None"].top - SB_LABEL_H + 2))
        current_acorn = state.illuminations.get("acorn")
        for val in [None, 0, 1, 2, 3]:
            active = current_acorn == val
            if val is not None:
                hand = self.engine.players[val].hand.cards
                has_it = any(c.is_acorn_over for c in hand)
                color = T_HIGHLIGHT if active else (T_BUTTON_BG if has_it else T_TEXT_DIM)
            else:
                color = T_HIGHLIGHT if active else T_BUTTON_BG
            self._draw_sb_button(
                rects[f"acorn_{val}"],
                "–" if val is None else str(val),
                color
            )

        # --- SKÓRE ---
        self._draw_section_label("SKÓRE", rects["score_nor_0"].top - SB_LABEL_H * 2 - 2)

        for i in range(NUM_PLAYERS):
            score = self.engine.players[i].total_score
            is_high = score >= 90
            # Label s menom a skóre
            lbl = self.font_small.render(
                f"AI_{i}: {score}b", True, T_HIGHLIGHT if is_high else T_TEXT
            )
            self.screen.blit(lbl, (SB_PAD, rects[f"score_nor_{i}"].top - SB_LABEL_H))
            self._draw_sb_button(
                rects[f"score_nor_{i}"], "0b",
                T_BUTTON_SUCCESS if not is_high else T_BUTTON_BG
            )
            self._draw_sb_button(
                rects[f"score_90_{i}"], "90+",
                T_HIGHLIGHT if is_high else T_BUTTON_BG
            )

    def _draw_section_label(self, text: str, y: int):
        surf = self.font_small.render(text, True, T_TEXT_DIM)
        self.screen.blit(surf, (SB_PAD, y))

    def _draw_sb_button(self, rect: pygame.Rect, text: str, color: tuple):
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)
        bg_color = tuple(min(255, c + 15) for c in color) if is_hover else color
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=BUTTON_RADIUS)
        border_color = T_HIGHLIGHT if is_hover else T_BORDER
        pygame.draw.rect(self.screen, border_color, rect, width=1, border_radius=BUTTON_RADIUS)
        surf = self.font_small.render(text, True, T_TEXT)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Stôl
    # ------------------------------------------------------------------

    def _draw_table_bg(self):
        pygame.draw.rect(
            self.screen, T_BG,
            (TABLE_X, TABLE_Y, TABLE_WIDTH, TABLE_HEIGHT)
        )
        pygame.draw.line(
            self.screen, T_BORDER,
            (LOG_X, TABLE_Y), (LOG_X, TABLE_Y + TABLE_HEIGHT), 1
        )

    def _draw_hands(self):
        state = self.engine.current_state()
        for player_idx in range(NUM_PLAYERS):
            self._draw_one_hand(player_idx, state.hands[player_idx])

    def _draw_one_hand(self, player_idx: int, cards: list[Card]):
        if not cards:
            return
        center_x, center_y, orientation = HAND_POS[player_idx]
        n = len(cards)
        playable_set = self._get_playable_set_for_override(player_idx)

        if orientation == "horizontal":
            total_w = CARD_W + (n - 1) * (CARD_W - HAND_H_OVERLAP)
            start_x = center_x - total_w // 2
            for i, card in enumerate(cards):
                x = start_x + i * (CARD_W - HAND_H_OVERLAP)
                y = center_y - CARD_H // 2
                self._blit_card(card, x, y)
                if card in playable_set:
                    self._draw_playable_highlight(x, y)
        else:
            total_h = CARD_H + (n - 1) * (CARD_H - HAND_V_OVERLAP)
            start_y = center_y - total_h // 2
            for i, card in enumerate(cards):
                x = center_x - CARD_W // 2
                y = start_y + i * (CARD_H - HAND_V_OVERLAP)
                self._blit_card(card, x, y)
                if card in playable_set:
                    self._draw_playable_highlight(x, y)

    def _get_playable_set_for_override(self, player_idx: int) -> set[Card]:
        if not self.override_mode:
            return set()
        state = self.engine.current_state()
        if state.is_complete or state.current_player_index != player_idx:
            return set()
        if self.engine.round.current_trick is None:
            return set()
        playable = self.engine.players[player_idx].hand.get_playable_cards(
            self.engine.round.current_trick.lead_suit,
            self.engine.round.trick_number,
        )
        return set(playable)

    def _draw_playable_highlight(self, x: int, y: int):
        rect = pygame.Rect(x - 3, y - 3, CARD_W + 6, CARD_H + 6)
        pygame.draw.rect(self.screen, T_HIGHLIGHT, rect, width=4, border_radius=6)

    def _blit_card(self, card: Card, x: int, y: int):
        img = self._get_card_image(card)
        if img is not None:
            self.screen.blit(img, (x, y))
        else:
            self._draw_card_fallback(card, x, y)

    def _draw_card_fallback(self, card: Card, x: int, y: int):
        rect = pygame.Rect(x, y, CARD_W, CARD_H)
        pygame.draw.rect(self.screen, T_PANEL_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, T_BORDER, rect, width=1, border_radius=4)
        text = self.font_medium.render(str(card), True, T_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    def _draw_trick(self):
        state = self.engine.current_state()
        for player_idx, card in state.current_trick_cards:
            cx, cy = TRICK_POS[player_idx]
            x, y = cx - CARD_W // 2, cy - CARD_H // 2
            img = self._get_card_image(card)
            if img:
                self.screen.blit(img, (x, y))
            else:
                self._draw_card_fallback(card, x, y)

    def _draw_player_labels(self):
        state = self.engine.current_state()
        for player_idx in range(NUM_PLAYERS):
            is_current = (
                not state.is_complete
                and state.current_player_index == player_idx
            )
            score = self.engine.players[player_idx].total_score
            is_high = score >= 90
            round_pts = state.round_points[player_idx]

            label = f"AI_{player_idx}  |  {round_pts}b"
            if is_high:
                label += f"  [🔥{score}]"

            text_color = T_HIGHLIGHT if is_current else T_TEXT
            surf = self.font_medium.render(label, True, text_color)
            pos = LABEL_POS[player_idx]
            rect = surf.get_rect(center=pos)
            bg_rect = rect.inflate(12, 6)
            pygame.draw.rect(self.screen, T_PANEL_BG, bg_rect, border_radius=4)
            border_color = T_HIGHLIGHT if is_current else T_BORDER
            pygame.draw.rect(self.screen, border_color, bg_rect, width=2, border_radius=4)
            self.screen.blit(surf, rect)

    # ------------------------------------------------------------------
    # Log panel
    # ------------------------------------------------------------------

    def _draw_log_panel(self):
        pygame.draw.rect(
            self.screen, T_PANEL_BG,
            (LOG_X, LOG_Y, LOG_WIDTH, LOG_HEIGHT)
        )
        x = LOG_X + 10
        y = LOG_Y + 10
        max_w = LOG_WIDTH - 20

        if self.last_step is not None:
            header = self.font_large.render("Posledný ťah", True, T_HIGHLIGHT)
            self.screen.blit(header, (x, y))
            y += header.get_height() + 4

            step_surf = self.font_medium.render(
                f"{self.last_step.player_name} zahral {self.last_step.card_played}",
                True, T_TEXT
            )
            self.screen.blit(step_surf, (x, y))
            y += step_surf.get_height() + 8

            if self.last_step.trick_completed:
                t_surf = self.font_medium.render(
                    f"→ štich vyhral AI_{self.last_step.trick_winner} "
                    f"(+{self.last_step.trick_points}b)",
                    True, T_SUCCESS
                )
                self.screen.blit(t_surf, (x, y))
                y += t_surf.get_height() + 8

            if self.last_step.round_completed:
                e_surf = self.font_medium.render(
                    "*** KOLO SKONČILO ***", True, T_WARNING
                )
                self.screen.blit(e_surf, (x, y))
                y += e_surf.get_height() + 8

            y += 4
            r_header = self.font_large.render("Reasoning", True, T_HIGHLIGHT)
            self.screen.blit(r_header, (x, y))
            y += r_header.get_height() + 4
            y = self._draw_log_entries(self.last_step.log_entries, x, y, max_w)

        else:
            header = self.font_large.render("Štart scenára", True, T_HIGHLIGHT)
            self.screen.blit(header, (x, y))
            y += header.get_height() + 6

            for line in self._wrap_text(self.scenario.description, self.font_small, max_w):
                surf = self.font_small.render(line, True, T_TEXT)
                self.screen.blit(surf, (x, y))
                y += surf.get_height() + 2

            if self.engine.illumination_logs:
                y += 8
                il_header = self.font_medium.render(
                    "Vysvietenie — rozhodnutia:", True, T_HIGHLIGHT
                )
                self.screen.blit(il_header, (x, y))
                y += il_header.get_height() + 4
                y = self._draw_log_entries(
                    self.engine.illumination_logs, x, y, max_w
                )
            if self.engine.declaration_logs:
                y += 8
                d_header = self.font_medium.render(
                    "Záväzky — rozhodnutia:", True, T_HIGHLIGHT
                )
                self.screen.blit(d_header, (x, y))
                y += d_header.get_height() + 4
                y = self._draw_log_entries(
                    self.engine.declaration_logs, x, y, max_w
                )

            y += 8
            info = self.font_medium.render(
                "Klikni 'Next' (alebo Space) na ďalší ťah", True, T_TEXT_DIM
            )
            self.screen.blit(info, (x, y))

    def _draw_log_entries(self, entries: list[LogEntry],
                          x: int, y: int, max_width: int) -> int:
        max_y = LOG_Y + LOG_HEIGHT - 20
        prev = None
        for entry in entries:
            # Hlavička pred prvým trace v slede
            header_lines = []
            if TesterLogger.needs_trace_header(entry, prev):
                y += self.font_mono.get_height() + 1
                header_lines.append(f"[{entry.player}] SITUATION_TRACE:")

            for line in header_lines + TesterLogger.format_entry(entry):
                for wline in self._wrap_text(line, self.font_mono, max_width):
                    if y >= max_y:
                        overflow = self.font_mono.render(
                            "... [viac riadkov]", True, T_TEXT_DIM
                        )
                        self.screen.blit(overflow, (x, max_y))
                        return max_y
                    surf = self.font_mono.render(wline, True, T_TEXT)
                    self.screen.blit(surf, (x, y))
                    y += surf.get_height() + 1
            prev = entry
        return y

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _draw_status_bar(self):
        y = WIN_HEIGHT - STATUS_HEIGHT
        pygame.draw.rect(self.screen, T_HEADER_BG, (0, y, WIN_WIDTH, STATUS_HEIGHT))
        pygame.draw.line(self.screen, T_BORDER, (0, y), (WIN_WIDTH, y), 1)

        state = self.engine.current_state()
        if state.is_complete:
            status_text = "Kolo dokončené"
        else:
            status_text = (
                f"Štich {state.trick_number + 1}/8  |  "
                f"Na ťahu: AI_{state.current_player_index}"
            )
        surf = self.font_medium.render(status_text, True, T_TEXT)
        self.screen.blit(surf, (TABLE_X + 10, y + (STATUS_HEIGHT - surf.get_height()) // 2))

        scores_text = "  ".join(
            f"AI_{i}: {state.round_points[i]}b" for i in range(NUM_PLAYERS)
        )
        scores_surf = self.font_medium.render(scores_text, True, T_TEXT)
        self.screen.blit(
            scores_surf,
            (WIN_WIDTH - scores_surf.get_width() - 15,
             y + (STATUS_HEIGHT - scores_surf.get_height()) // 2)
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _format_export(self) -> str:
        lines = []
        state = self.engine.current_state()
        sc = self.scenario

        lines.append("=" * 70)
        lines.append("TESTER EXPORT")
        lines.append("=" * 70)
        lines.append(f"Scenár: {sc.name}")
        lines.append(f"Popis: {sc.description}")
        lines.append("")
        lines.append("--- STAV ---")
        lines.append(f"Štich: {state.trick_number + 1}/8")
        lines.append("Kolo: DOKONČENÉ" if state.is_complete
                     else f"Na ťahu: AI_{state.current_player_index}")
        lines.append(f"First player: AI_{sc.first_player_index}")
        lines.append("")

        if any(v is not None for v in state.illuminations.values()):
            lines.append("--- VYSVIETENIE ---")
            for suit, who in state.illuminations.items():
                if who is not None:
                    lines.append(f"  {suit}-over: AI_{who}")
            lines.append("")

        if any(v is not None for v in state.declarations.values()):
            lines.append("--- ZÁVÄZKY ---")
            for idx, decl in state.declarations.items():
                if decl is not None:
                    lines.append(f"  AI_{idx}: {decl}")
            lines.append("")

        lines.append("--- SKÓRE ---")
        for i in range(NUM_PLAYERS):
            total = self.engine.players[i].total_score
            lines.append(f"  AI_{i}: {state.round_points[i]}b (celkovo: {total}b)")
        lines.append("")

        lines.append("--- RUKY ---")
        for i in range(NUM_PLAYERS):
            cards = state.hands[i]
            cards_str = " ".join(str(c) for c in cards) if cards else "(prázdna)"
            marker = " ← NA ŤAHU" if (
                not state.is_complete and state.current_player_index == i
            ) else ""
            lines.append(f"  AI_{i} ({len(cards)}): {cards_str}{marker}")
        lines.append("")

        lines.append("--- AKTUÁLNY ŠTICH ---")
        if state.current_trick_cards:
            lines.append(f"Lead: {state.current_trick_cards[0][1].suit}")
            for pi, card in state.current_trick_cards:
                lines.append(f"  AI_{pi}: {card}")
        else:
            lines.append("  (prázdny)")
        lines.append("")

        lines.append("--- HISTÓRIA ---")
        for i, th in enumerate(state.completed_tricks, 1):
            cards_str = "  ".join(f"AI_{pi}: {c}" for pi, c in th.cards)
            lines.append(f"  T{i}: leader=AI_{th.leader} | {cards_str} → AI_{th.winner}")
        lines.append("")

        if self.last_step is not None:
            lines.append("--- POSLEDNÝ ŤAH ---")
            lines.append(f"Hráč: AI_{self.last_step.player_index}")
            lines.append(f"Karta: {self.last_step.card_played}")
            if self.last_step.trick_completed:
                lines.append(
                    f"Štich: vyhral AI_{self.last_step.trick_winner} "
                    f"(+{self.last_step.trick_points}b)"
                )
            lines.append("")
            lines.append("--- REASONING ---")
            prev = None
            for entry in self.last_step.log_entries:
                if TesterLogger.needs_trace_header(entry, prev):
                    lines.append(f"  [{entry.player}] SITUATION_TRACE:")
                for line in TesterLogger.format_entry(entry):
                    lines.append(f"  {line}")
                prev = entry
            lines.append("")

        if not state.is_complete:
            idx = state.current_player_index
            ai = self.engine.ais[idx]
            mem = ai.memory
            lines.append(f"--- AIMemory (AI_{idx}) ---")
            lines.append(f"  Tricks taken: {dict(mem.tricks_taken)}")
            lines.append(f"  Specials gone: {dict(mem.special_gone)}")
            lines.append(f"  Illuminated by: {dict(mem.illuminated_by)}")
            for p_idx in range(NUM_PLAYERS):
                voids = mem.void_suits[p_idx]
                if voids:
                    lines.append(f"  Void AI_{p_idx}: {sorted(voids)}")
            for suit in ("heart", "leaf", "acorn", "bell"):
                rem = mem.remaining[suit]
                rem_str = " ".join(str(c) for c in rem) if rem else "(žiadne)"
                lines.append(f"  Remaining {suit}: {rem_str}")
            lines.append(f"  Sweep state: {ai.sweep_pipeline.state.value}")

        return "\n".join(lines)