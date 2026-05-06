# tester/tester_screen.py
import sys
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
import os
import pygame

from game.card import Card
from tester.scenario import Scenario
from tester.tester_engine import TesterEngine, StepResult
from tester.tester_logger import TesterLogger, LogEntry
from tester.random_scenario import random_scenario
from config import (
    CARDS_SMALL_PATH, CARD_SIZE_SMALL, CARD_BACK_IMAGE,
    NUM_PLAYERS,
    COLOR_BG, COLOR_BG_DARK, COLOR_PANEL_BG,
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_DARK_GRAY,
    COLOR_BUTTON_PRIMARY, COLOR_BUTTON_SECONDARY,
    COLOR_PENALTY, COLOR_BONUS,
    BUTTON_RADIUS,
)

# ------------------------------------------------------------------
# Lokálne farby testera — biele GUI s čiernym textom (debug-friendly)
# ------------------------------------------------------------------

T_BG = (245, 245, 245)           # svetlosivé pozadie
T_PANEL_BG = (255, 255, 255)     # biele panely
T_HEADER_BG = (230, 230, 230)    # mierne tmavšia hlavička
T_TEXT = (20, 20, 20)            # čierny text
T_TEXT_DIM = (100, 100, 100)     # sivý text (pre menej dôležité)
T_BORDER = (180, 180, 180)       # šedé okraje
T_HIGHLIGHT = (200, 140, 30)     # zlatá pre highlight (on-turn hráč)
T_BUTTON_BG = (220, 220, 220)    # tlačidlá pozadie
T_BUTTON_PRIMARY = (180, 200, 230)  # primary tlačidlo (Next)
T_SUCCESS = (40, 130, 40)        # zelená (víťaz štichu)
T_WARNING = (180, 40, 40)        # červená (koniec kola)

# ------------------------------------------------------------------
# Konštanty layoutu
# ------------------------------------------------------------------

WIN_WIDTH = 1600
WIN_HEIGHT = 980

# Hlavička
HEADER_HEIGHT = 60

# Status bar
STATUS_HEIGHT = 40
# Setup bar
SETUP_BAR_HEIGHT = 36

# Stôl (ľavá časť)
TABLE_X = 0
TABLE_Y = HEADER_HEIGHT + SETUP_BAR_HEIGHT
TABLE_WIDTH = 1100
TABLE_HEIGHT = WIN_HEIGHT - HEADER_HEIGHT - STATUS_HEIGHT

# Log panel (pravá časť)
LOG_X = TABLE_WIDTH
LOG_Y = HEADER_HEIGHT
LOG_WIDTH = WIN_WIDTH - TABLE_WIDTH
LOG_HEIGHT = TABLE_HEIGHT

# Stred stola
TABLE_CENTER_X = TABLE_X + TABLE_WIDTH // 2
TABLE_CENTER_Y = TABLE_Y + TABLE_HEIGHT // 2

# Karty — small format
CARD_W, CARD_H = CARD_SIZE_SMALL  # (91, 146)

# Overlap pre horizontálne ruky (AI_0, AI_2)
HAND_H_OVERLAP = 25  # koľko px sa karty prekrývajú horizontálne

# Overlap pre vertikálne ruky (AI_1, AI_3)
HAND_V_OVERLAP = 100  # vidno ~46 px z každej karty + posledná celá

# Pozície rúk hráčov: (center_x, center_y, orientation)
# orientation: "horizontal" = karty vedľa seba, "vertical" = pod sebou
HAND_POS = {
    0: (TABLE_CENTER_X,
        TABLE_Y + TABLE_HEIGHT - CARD_H // 2 - 20,
        "horizontal"),
    1: (TABLE_X + TABLE_WIDTH - CARD_W // 2 - 20,
        TABLE_CENTER_Y,
        "vertical"),
    2: (TABLE_CENTER_X,
        TABLE_Y + CARD_H // 2 + 20,
        "horizontal"),
    3: (TABLE_X + CARD_W // 2 + 20,
        TABLE_CENTER_Y,
        "vertical"),
}

# Pozície kariet v štiche (stred)
TRICK_OFFSET = 80
TRICK_POS = {
    0: (TABLE_CENTER_X, TABLE_CENTER_Y + TRICK_OFFSET),
    1: (TABLE_CENTER_X + TRICK_OFFSET, TABLE_CENTER_Y),
    2: (TABLE_CENTER_X, TABLE_CENTER_Y - TRICK_OFFSET),
    3: (TABLE_CENTER_X - TRICK_OFFSET, TABLE_CENTER_Y),
}

# Pozície menoviek hráčov
LABEL_POS = {
    0: (TABLE_CENTER_X, TABLE_Y + TABLE_HEIGHT - 8),
    1: (TABLE_X + TABLE_WIDTH - CARD_W - 50, TABLE_Y + 30),
    2: (TABLE_CENTER_X, TABLE_Y + 8),
    3: (TABLE_X + CARD_W + 50, TABLE_Y + 30),
}

# Tlačidlá v hlavičke — sprava doľava
BUTTON_W = 100
BUTTON_H = 40
BUTTON_GAP = 8
BUTTON_QUIT_X = WIN_WIDTH - BUTTON_W - BUTTON_GAP
BUTTON_RESET_X = BUTTON_QUIT_X - BUTTON_W - BUTTON_GAP
BUTTON_NEXT_X = BUTTON_RESET_X - BUTTON_W - BUTTON_GAP
BUTTON_BACK_X = BUTTON_NEXT_X - BUTTON_W - BUTTON_GAP
BUTTON_OVERRIDE_X = BUTTON_BACK_X - BUTTON_W - BUTTON_GAP
BUTTON_ROUND_X = BUTTON_OVERRIDE_X - BUTTON_W - BUTTON_GAP
BUTTON_TRICK_X = BUTTON_ROUND_X - BUTTON_W - BUTTON_GAP
BUTTON_EXPORT_X = BUTTON_TRICK_X - BUTTON_W - BUTTON_GAP * 2
BUTTON_RANDOM_X = BUTTON_EXPORT_X - BUTTON_W - BUTTON_GAP
BUTTON_Y = (HEADER_HEIGHT - BUTTON_H) // 2

# Auto-play timing
AUTOPLAY_DELAY_MS = 400


# ------------------------------------------------------------------
# TesterScreen
# ------------------------------------------------------------------

class TesterScreen:
    """
    Pygame GUI pre tester.

    Vykreslí 4 ruky odkryté + aktuálny štich + log panel.
    Tlačidlo "Next" odohrá ďalší ťah AI.
    """

    def __init__(self, scenario: Scenario):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption(f"Chuj Tester — {scenario.name}")
        self.clock = pygame.time.Clock()

        # Engine
        self.scenario = scenario
        self.engine = TesterEngine(scenario)

        # Stav GUI
        self.running = True
        self.last_step: StepResult | None = None

        # Auto-play stav
        self.autoplay_mode: str | None = None  # None | "trick" | "round"
        self.autoplay_next_time: int = 0  # pygame.time.get_ticks() kedy ďalší krok

        # Override stav
        self.override_mode: bool = False  # čaká sa na klik na kartu

        # Cache obrázkov kariet
        self.card_images: dict[str, pygame.Surface] = {}
        self.card_back: pygame.Surface | None = None
        self._load_card_images()

        # Fonty — preferujeme fonty ktoré podporujú slovenskú diakritiku
        # AJ symboly kariet (♥ ● ♠ ♣). Segoe UI Symbol nemá diakritiku,
        # preto začneme bežnými textovými fontmi ktoré majú oboje.
        font_name = "segoeui,arial,dejavusans,liberationsans"
        mono_name = "consolas,dejavusansmono,couriernew,courier"

        self.font_small = pygame.font.SysFont(font_name, 20)
        self.font_medium = pygame.font.SysFont(font_name, 24)
        self.font_large = pygame.font.SysFont(font_name, 32)
        self.font_mono = pygame.font.SysFont(mono_name, 16)

    # ------------------------------------------------------------------
    # Load assets
    # ------------------------------------------------------------------

    def _load_card_images(self):
        """Načíta všetky karty + card-back do cache."""
        from config import SUITS, RANKS

        for suit in SUITS:
            for rank in RANKS:
                filename = f"{suit}-{rank}.png"
                path = os.path.join(CARDS_SMALL_PATH, filename)
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.card_images[filename] = img
                except (pygame.error, FileNotFoundError) as e:
                    print(f"WARNING: nepodarilo sa načítať {path}: {e}")

        # Card back
        back_path = os.path.join(CARDS_SMALL_PATH, CARD_BACK_IMAGE)
        try:
            self.card_back = pygame.image.load(back_path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            self.card_back = None

    def _get_card_image(self, card: Card) -> pygame.Surface | None:
        """Vráti pygame Surface pre danú kartu (alebo None)."""
        return self.card_images.get(card.image_name)

    # ------------------------------------------------------------------
    # Hlavná slučka
    # ------------------------------------------------------------------

    def run(self):
        """Hlavná slučka — spustí GUI a beží do zatvorenia."""
        while self.running:
            self.clock.tick(30)
            self._handle_events()
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self):
        # Najprv spracuj autoplay tick (ak beží)
        self._tick_autoplay()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif (event.key == pygame.K_SPACE
                      or event.key == pygame.K_RETURN
                      or event.key == pygame.K_RIGHT):
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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if not self._handle_setup_bar_click(event.pos):
                        self._handle_click(event.pos)

    def _tick_autoplay(self):
        """Ak je autoplay aktívny a uplynul čas, zahraj ďalší ťah."""
        if self.autoplay_mode is None:
            return
        if self.engine.is_complete():
            self.autoplay_mode = None
            return

        now = pygame.time.get_ticks()
        if now < self.autoplay_next_time:
            return

        # Zahraj ďalší ťah
        try:
            self.last_step = self.engine.next_step()
        except Exception as e:
            print(f"ERROR pri autoplay next_step(): {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.autoplay_mode = None
            return

        # Rozhodni či pokračovať
        if self.autoplay_mode == "trick":
            # štich mód — končí po dokončení štichu
            if self.last_step.trick_completed:
                self.autoplay_mode = None
                return
        elif self.autoplay_mode == "round":
            # Kolo mód — končí po dokončení kola
            if self.last_step.round_completed:
                self.autoplay_mode = None
                return

        # Naplánuj ďalší tick
        self.autoplay_next_time = now + AUTOPLAY_DELAY_MS

    def _handle_click(self, pos: tuple[int, int]):
        # V override móde — klik na kartu má prioritu pred tlačidlami
        # (okrem Reset/Quit ktoré ukončia override)
        if self.override_mode:
            # Reset/Quit/Back vyrušia override
            if (self._reset_button_rect().collidepoint(pos)
                    or self._quit_button_rect().collidepoint(pos)
                    or self._back_button_rect().collidepoint(pos)):
                self.override_mode = False
                # Pokračuj normálne ↓
            else:
                # Skús klik na kartu v ruke aktívneho hráča
                clicked = self._get_clicked_playable_card(pos)
                if clicked is not None:
                    self._do_override(clicked)
                return  # v override móde nepokračujeme s ostatnými tlačidlami

        # Normálne tlačidlá
        if self._next_button_rect().collidepoint(pos):
            self._on_next_clicked()
        elif self._back_button_rect().collidepoint(pos):
            self._on_back_clicked()
        elif self._override_button_rect().collidepoint(pos):
            self._on_override_clicked()
        elif self._trick_button_rect().collidepoint(pos):
            self._on_trick_clicked()
        elif self._round_button_rect().collidepoint(pos):
            self._on_round_clicked()
        elif self._random_button_rect().collidepoint(pos):
            self._on_random_clicked()
        elif self._reset_button_rect().collidepoint(pos):
            self._on_reset_clicked()
        elif self._export_button_rect().collidepoint(pos):
            self._on_export_clicked()
        elif self._quit_button_rect().collidepoint(pos):
            self.running = False

    def _on_next_clicked(self):
        if self.engine.is_complete():
            return
        try:
            self.last_step = self.engine.next_step()
        except Exception as e:
            print(f"ERROR pri next_step(): {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def _on_reset_clicked(self):
        self.engine.reset()
        self.last_step = None

    def _on_trick_clicked(self):
        """Spustí autoplay celého štichu."""
        if self.engine.is_complete() or self.autoplay_mode is not None:
            return
        self.autoplay_mode = "trick"
        self.autoplay_next_time = pygame.time.get_ticks()

    def _on_round_clicked(self):
        """Spustí autoplay celého kola."""
        if self.engine.is_complete() or self.autoplay_mode is not None:
            return
        self.autoplay_mode = "round"
        self.autoplay_next_time = pygame.time.get_ticks()

    def _on_random_clicked(self):
        """Vygeneruje nový random scenár a načíta ho."""
        self.autoplay_mode = None
        new_scenario = random_scenario()
        self.scenario = new_scenario
        self.engine = TesterEngine(new_scenario)
        self.last_step = None
        pygame.display.set_caption(f"Chuj Tester — {new_scenario.name}")

    def _on_export_clicked(self):
        """Uloží aktuálny stav scenára do tester_export.txt v koreni."""
        try:
            text = self._format_export()
            with open("tester_export.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("[Export] Uložené do tester_export.txt")
        except Exception as e:
            print(f"[Export] CHYBA: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    def _format_export(self) -> str:
        """Naformátuje aktuálny stav scenára do textu pre debug."""
        lines = []
        state = self.engine.current_state()
        sc = self.scenario

        # === Hlavička ===
        lines.append("=" * 70)
        lines.append("TESTER EXPORT")
        lines.append("=" * 70)
        lines.append(f"Scenár: {sc.name}")
        lines.append(f"Popis: {sc.description}")
        lines.append("")

        # === Stav kola ===
        lines.append("--- STAV ---")
        lines.append(f"štich: {state.trick_number + 1}/8")
        if state.is_complete:
            lines.append("Kolo: DOKONČENÉ")
        else:
            lines.append(f"Na ťahu: AI_{state.current_player_index}")
        lines.append(f"Override mode: {'ÁNO' if self.override_mode else 'nie'}")
        lines.append(f"First player kola: AI_{sc.first_player_index}")
        lines.append("")

        # === Iluminácie a záväzky ===
        if any(v is not None for v in state.illuminations.values()):
            lines.append("--- VYSVIETENIE ---")
            for suit_short, who in state.illuminations.items():
                if who is not None:
                    lines.append(f"  {suit_short}-over vysvietený hráčom AI_{who}")
            lines.append("")

        if any(v is not None for v in state.declarations.values()):
            lines.append("--- ZÁVÄZKY ---")
            for idx, decl in state.declarations.items():
                if decl is not None:
                    lines.append(f"  AI_{idx}: {decl}")
            lines.append("")

        # === Skóre ===
        lines.append("--- SKÓRE KOLA (round_points) ---")
        for i in range(NUM_PLAYERS):
            lines.append(f"  AI_{i}: {state.round_points[i]}b")
        lines.append("")

        # === Ruky všetkých hráčov ===
        lines.append("--- RUKY ---")
        for i in range(NUM_PLAYERS):
            cards = state.hands[i]
            cards_str = " ".join(str(c) for c in cards) if cards else "(prázdna)"
            current_marker = " ← NA ŤAHU" if (
                    not state.is_complete
                    and state.current_player_index == i
            ) else ""
            lines.append(f"  AI_{i} ({len(cards)}): {cards_str}{current_marker}")
        lines.append("")

        # === Aktuálny štich ===
        lines.append("--- AKTUÁLNY štich ---")
        if state.current_trick_cards:
            # Lead suit z prvej karty
            lead_suit = state.current_trick_cards[0][1].suit
            lines.append(f"Lead suit: {lead_suit}")
            for player_idx, card in state.current_trick_cards:
                lines.append(f"  AI_{player_idx}: {card}")
        else:
            lines.append("  (žiadne karty zatiaľ)")
        lines.append("")

        # === História odohratých štichov ===
        lines.append("--- HISTÓRIA ŠTICHOV (chronologicky) ---")
        if not state.completed_tricks:
            lines.append("  (žiadne štichy ešte odohrané)")
        else:
            for i, th in enumerate(state.completed_tricks, start=1):
                cards_str = "  ".join(
                    f"AI_{pi}: {c}" for pi, c in th.cards
                )
                lines.append(
                    f"  T{i}: leader=AI_{th.leader} | {cards_str} "
                    f"→ AI_{th.winner}"
                )
        lines.append("")

        # === Posledný ťah + reasoning ===
        if self.last_step is not None:
            lines.append("--- POSLEDNÝ ŤAH ---")
            lines.append(
                f"Hráč: {self.last_step.player_name} "
                f"(AI_{self.last_step.player_index})"
            )
            lines.append(f"Zahraná karta: {self.last_step.card_played}")
            if self.last_step.trick_completed:
                lines.append(
                    f"štich dokončený, vyhral AI_{self.last_step.trick_winner} "
                    f"(+{self.last_step.trick_points}b)"
                )
            if self.last_step.round_completed:
                lines.append("KOLO DOKONČENÉ")
            lines.append("")

            lines.append("--- REASONING CHAIN POSLEDNÉHO ŤAHU ---")
            if not self.last_step.log_entries:
                lines.append("  (žiadne entries)")
            else:
                for entry in self.last_step.log_entries:
                    formatted = TesterLogger.format_entry(entry)
                    for line in formatted:
                        lines.append(f"  {line}")
            lines.append("")
        else:
            lines.append("--- POSLEDNÝ ŤAH ---")
            lines.append("  (žiadny ťah ešte neprebehol)")
            lines.append("")

        # === Pamäť AI hráča na ťahu — užitočné pre debug sweep pipeline ===
        if not state.is_complete:
            current_idx = state.current_player_index
            ai = self.engine.ais[current_idx]
            mem = ai.memory
            lines.append(f"--- AIMemory (AI_{current_idx}) ---")
            lines.append(f"  Tricks taken: {dict(mem.tricks_taken)}")
            lines.append(f"  Specials gone: {dict(mem.special_gone)}")
            lines.append(f"  Illuminated by: {dict(mem.illuminated_by)}")
            lines.append("  Void suits:")
            for p_idx in range(NUM_PLAYERS):
                voids = mem.void_suits[p_idx]
                if voids:
                    lines.append(f"    AI_{p_idx}: {sorted(voids)}")
            lines.append("  Remaining (u súperov):")
            for suit in ("heart", "leaf", "acorn", "bell"):
                rem = mem.remaining[suit]
                rem_str = " ".join(str(c) for c in rem) if rem else "(žiadne)"
                lines.append(f"    {suit}: {rem_str}")
            lines.append(f"  Sweep state: {ai.sweep_pipeline.state.value}")
            lines.append("")

        return "\n".join(lines)

    def _on_back_clicked(self):
        """Vráti sa o jeden ťah späť."""
        if self.autoplay_mode is not None:
            return  # nedovoľ Back počas autoplay
        if not self.engine.can_go_back():
            return
        try:
            self.engine.go_back()
        except Exception as e:
            print(f"ERROR pri go_back(): {type(e).__name__}: {e}")
            return

        # Aktualizuj last_step na predošlý (alebo None)
        # Logger.full_history obsahuje záznamy chronologicky.
        # last_step.log_entries je posledný "blok" pred go_back-om
        # ale snapshot ich už restoroval — nemáme priamy odkaz na
        # predošlý StepResult. Riešenie: nastav None, GUI ukáže
        # placeholder.
        self.last_step = None

    def _on_override_clicked(self):
        """Vstúpi do override mode — čaká na klik na kartu."""
        if self.autoplay_mode is not None:
            return
        if self.engine.is_complete():
            return
        # Ak je čakajúci nový štich, spusti ho aby existoval current_trick
        self.engine.prepare_for_override()
        self.override_mode = True

    def _do_override(self, card: Card):
        """Zahrá override kartu."""
        try:
            self.last_step = self.engine.next_step_override(card)
        except Exception as e:
            print(f"ERROR pri override: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.override_mode = False

    def _get_clicked_playable_card(self, pos: tuple[int, int]) -> Card | None:
        """
        Zistí či užívateľ klikol na playable kartu aktívneho hráča.
        Vráti kartu alebo None.
        """
        state = self.engine.current_state()
        if state.is_complete:
            return None

        player_idx = state.current_player_index
        cards = state.hands[player_idx]

        # Získaj playable karty (rovnaká logika ako v engine)
        if self.engine.round.current_trick is None:
            return None
        lead_suit = self.engine.round.current_trick.lead_suit
        trick_num = self.engine.round.trick_number
        playable = self.engine.players[player_idx].hand.get_playable_cards(
            lead_suit, trick_num,
        )

        # Vypočítaj rectangles pre každú kartu (rovnaká logika ako _draw_one_hand)
        center_x, center_y, orientation = HAND_POS[player_idx]
        n = len(cards)
        rects: list[tuple[Card, pygame.Rect]] = []

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

        # Hľadaj klik OD POSLEDNEJ KARTY (najvyššia v Z-order)
        for card, rect in reversed(rects):
            if rect.collidepoint(pos):
                if card in playable:
                    return card
                return None  # klikol na neplayable kartu

        return None  # klik mimo kariet

    # ------------------------------------------------------------------
    # Kreslenie — root
    # ------------------------------------------------------------------

    def _draw(self):
        self.screen.fill(T_BG)

        self._draw_header()
        self._draw_setup_bar()
        self._draw_table_bg()
        self._draw_hands()
        self._draw_trick()
        self._draw_player_labels()
        self._draw_log_panel()
        self._draw_status_bar()

    # ------------------------------------------------------------------
    # Header (hlavička s tlačidlami)
    # ------------------------------------------------------------------

    def _draw_header(self):
        # Pozadie hlavičky
        pygame.draw.rect(
            self.screen, T_HEADER_BG,
            (0, 0, WIN_WIDTH, HEADER_HEIGHT),
        )
        pygame.draw.line(
            self.screen, T_BORDER,
            (0, HEADER_HEIGHT), (WIN_WIDTH, HEADER_HEIGHT), 1,
        )

        # Názov scenára vľavo (môže byť dlhý pri random — skráť)
        scenario_label = f"Scenár: {self.scenario.name}"
        title = self.font_large.render(scenario_label, True, T_TEXT)
        self.screen.blit(title, (15, (HEADER_HEIGHT - title.get_height()) // 2))

        # Indikátor autoplay
        if self.autoplay_mode is not None:
            mode_label = "▶ AUTOPLAY"
            mode_surf = self.font_medium.render(mode_label, True, T_HIGHLIGHT)
            self.screen.blit(
                mode_surf,
                (title.get_width() + 30,
                 (HEADER_HEIGHT - mode_surf.get_height()) // 2),
            )

        # Tlačidlá vpravo (sprava doľava: Quit, Reset, Next, Kolo, štich | Random)
        self._draw_button(self._random_button_rect(), "Random", T_BUTTON_PRIMARY)
        self._draw_button(self._export_button_rect(), "Export", T_BUTTON_BG)
        self._draw_button(self._trick_button_rect(), "štich", T_BUTTON_BG)
        self._draw_button(self._round_button_rect(), "Kolo", T_BUTTON_BG)
        # Override tlačidlo má aktívnu farbu keď je v override móde
        override_color = T_HIGHLIGHT if self.override_mode else T_BUTTON_BG
        self._draw_button(
            self._override_button_rect(),
            "Override" if not self.override_mode else "VYBER!",
            override_color,
        )
        self._draw_button(self._back_button_rect(), "← Back", T_BUTTON_BG)
        self._draw_button(self._next_button_rect(), "Next →", T_BUTTON_PRIMARY)
        self._draw_button(self._reset_button_rect(), "Reset", T_BUTTON_BG)
        self._draw_button(self._quit_button_rect(), "Quit", T_BUTTON_BG)

    def _draw_setup_bar(self):
        """Nakreslí setup bar — first player a vysvietenie."""
        state = self.engine.current_state()
        bar_y = HEADER_HEIGHT
        cy = bar_y + SETUP_BAR_HEIGHT // 2

        pygame.draw.rect(
            self.screen, T_HEADER_BG,
            (0, bar_y, WIN_WIDTH, SETUP_BAR_HEIGHT)
        )
        pygame.draw.line(
            self.screen, T_BORDER,
            (0, bar_y + SETUP_BAR_HEIGHT),
            (WIN_WIDTH, bar_y + SETUP_BAR_HEIGHT), 1
        )

        x = 15

        # First player
        lbl = self.font_small.render("First:", True, T_TEXT_DIM)
        self.screen.blit(lbl, (x, cy - lbl.get_height() // 2))
        x += lbl.get_width() + 6
        for i in range(NUM_PLAYERS):
            active = self.engine.scenario.first_player_index == i
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            self._draw_button(r, f"AI_{i}", T_HIGHLIGHT if active else T_BUTTON_BG)
            x += 46
        x += 16

        # Leaf
        lbl = self.font_small.render("Q♠:", True, T_TEXT_DIM)
        self.screen.blit(lbl, (x, cy - lbl.get_height() // 2))
        x += lbl.get_width() + 6
        current_leaf = state.illuminations.get("leaf")
        # Leaf
        for val in [None, 0, 1, 2, 3]:
            active = current_leaf == val
            # Ak val je hráč — skontroluj či má Q♠
            if val is not None:
                hand = self.engine.players[val].hand.cards
                has_it = any(c.is_leaf_over for c in hand)
                color = T_HIGHLIGHT if active else (T_BUTTON_BG if has_it else T_TEXT_DIM)
            else:
                color = T_HIGHLIGHT if active else T_BUTTON_BG
            label = "–" if val is None else f"AI_{val}"
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            self._draw_button(r, label, color)
            x += 46
        x += 16

        # Acorn
        lbl = self.font_small.render("Q♣:", True, T_TEXT_DIM)
        self.screen.blit(lbl, (x, cy - lbl.get_height() // 2))
        x += lbl.get_width() + 6
        current_acorn = state.illuminations.get("acorn")
        for val in [None, 0, 1, 2, 3]:
            active = current_acorn == val  # ← bolo current_leaf
            if val is not None:
                hand = self.engine.players[val].hand.cards
                has_it = any(c.is_acorn_over for c in hand)  # ← bolo is_leaf_over
                color = T_HIGHLIGHT if active else (T_BUTTON_BG if has_it else T_TEXT_DIM)
            else:
                color = T_HIGHLIGHT if active else T_BUTTON_BG
            label = "–" if val is None else f"AI_{val}"
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            self._draw_button(r, label, color)
            x += 46

    def _handle_setup_bar_click(self, pos) -> bool:
        """
        Spracuje klik na setup bar. Zmena = reset so zmeneným scenárom.
        Vracia True ak klik patril setup baru.
        """
        bar_y = HEADER_HEIGHT
        if not (bar_y <= pos[1] <= bar_y + SETUP_BAR_HEIGHT):
            return False

        import copy
        x = 15

        # First player
        lbl_w = self.font_small.size("First:")[0]
        x += lbl_w + 6
        for i in range(NUM_PLAYERS):
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            if r.collidepoint(pos):
                new_sc = copy.copy(self.engine.scenario)
                new_sc.first_player_index = i
                self.engine = TesterEngine(new_sc)
                return True
            x += 46
        x += 16

        # Leaf
        lbl_w = self.font_small.size("Q♠:")[0]
        x += lbl_w + 6
        for val in [None, 0, 1, 2, 3]:
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            if r.collidepoint(pos):
                # Ignoruj klik ak hráč nemá Q♠
                if val is not None:
                    hand = self.engine.players[val].hand.cards
                    if not any(c.is_leaf_over for c in hand):
                        return True  # klik absorbujeme ale nič nerobíme
                new_sc = copy.copy(self.engine.scenario)
                new_sc.illuminations = {**new_sc.illuminations, "leaf": val}
                self.engine = TesterEngine(new_sc)
                return True
            x += 46
        x += 16

        # Acorn
        lbl_w = self.font_small.size("Q♣:")[0]
        x += lbl_w + 6
        for val in [None, 0, 1, 2, 3]:
            r = pygame.Rect(x, bar_y + 4, 42, SETUP_BAR_HEIGHT - 8)
            if r.collidepoint(pos):
                # Ignoruj klik ak hráč nemá Q♣
                if val is not None:
                    hand = self.engine.players[val].hand.cards
                    if not any(c.is_acorn_over for c in hand):
                        return True  # klik absorbujeme ale nič nerobíme
                new_sc = copy.copy(self.engine.scenario)
                new_sc.illuminations = {**new_sc.illuminations, "acorn": val}
                self.engine = TesterEngine(new_sc)
                return True
            x += 46

        return False

    @staticmethod
    def _next_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_NEXT_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _reset_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_RESET_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _quit_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_QUIT_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _trick_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_TRICK_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _round_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_ROUND_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _random_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_RANDOM_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _back_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_BACK_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _override_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_OVERRIDE_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    @staticmethod
    def _export_button_rect() -> pygame.Rect:
        return pygame.Rect(BUTTON_EXPORT_X, BUTTON_Y, BUTTON_W, BUTTON_H)

    def _draw_button(self, rect: pygame.Rect, text: str, color: tuple):
        mouse_pos = pygame.mouse.get_pos()
        is_hover = rect.collidepoint(mouse_pos)

        bg_color = tuple(min(255, c + 15) for c in color) if is_hover else color
        pygame.draw.rect(
            self.screen, bg_color, rect, border_radius=BUTTON_RADIUS,
        )

        border_color = T_HIGHLIGHT if is_hover else T_BORDER
        pygame.draw.rect(
            self.screen, border_color, rect, width=2, border_radius=BUTTON_RADIUS,
        )

        # ↓ DÔLEŽITÉ — musí byť T_TEXT (čierny), nie COLOR_WHITE
        surf = self.font_medium.render(text, True, T_TEXT)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Stôl — pozadie
    # ------------------------------------------------------------------

    def _draw_table_bg(self):
        # Stôl
        pygame.draw.rect(
            self.screen, T_BG,
            (TABLE_X, TABLE_Y, TABLE_WIDTH, TABLE_HEIGHT),
        )

        # Vertikálny separator medzi stolom a logom
        pygame.draw.line(
            self.screen, T_BORDER,
            (LOG_X, TABLE_Y),
            (LOG_X, TABLE_Y + TABLE_HEIGHT),
            1,
        )

    # ------------------------------------------------------------------
    # Ruky hráčov
    # ------------------------------------------------------------------

    def _draw_hands(self):
        state = self.engine.current_state()
        for player_idx in range(NUM_PLAYERS):
            cards = state.hands[player_idx]
            self._draw_one_hand(player_idx, cards)

    def _draw_one_hand(self, player_idx: int, cards: list[Card]):
        if not cards:
            return

        center_x, center_y, orientation = HAND_POS[player_idx]
        n = len(cards)

        # V override móde určí playable karty pre highlight
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
        """V override móde vráti playable karty aktívneho hráča, inak prázdne."""
        if not self.override_mode:
            return set()
        state = self.engine.current_state()
        if state.is_complete:
            return set()
        if state.current_player_index != player_idx:
            return set()
        if self.engine.round.current_trick is None:
            return set()

        playable = self.engine.players[player_idx].hand.get_playable_cards(
            self.engine.round.current_trick.lead_suit,
            self.engine.round.trick_number,
        )
        return set(playable)

    def _draw_playable_highlight(self, x: int, y: int):
        """Zlatý rámček okolo karty pre indikáciu 'klikni ma'."""
        rect = pygame.Rect(x - 3, y - 3, CARD_W + 6, CARD_H + 6)
        pygame.draw.rect(
            self.screen, T_HIGHLIGHT, rect, width=4, border_radius=6,
        )

    def _blit_card(self, card: Card, x: int, y: int):
        """Nakreslí jednu kartu na danú pozíciu (alebo fallback)."""
        img = self._get_card_image(card)
        if img is not None:
            self.screen.blit(img, (x, y))
        else:
            self._draw_card_fallback(card, x, y)

    def _draw_card_fallback(self, card: Card, x: int, y: int):
        """Ak obrázok karty chýba, nakresli rámček s textom."""
        rect = pygame.Rect(x, y, CARD_W, CARD_H)
        pygame.draw.rect(self.screen, T_PANEL_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, T_BORDER, rect, width=1, border_radius=4)
        text = self.font_medium.render(str(card), True, T_TEXT)
        self.screen.blit(text, text.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Aktuálny štich
    # ------------------------------------------------------------------

    def _draw_trick(self):
        state = self.engine.current_state()
        if not state.current_trick_cards:
            return

        for player_idx, card in state.current_trick_cards:
            cx, cy = TRICK_POS[player_idx]
            x = cx - CARD_W // 2
            y = cy - CARD_H // 2
            img = self._get_card_image(card)
            if img is not None:
                self.screen.blit(img, (x, y))
            else:
                self._draw_card_fallback(card, x, y)

    # ------------------------------------------------------------------
    # Menovky hráčov
    # ------------------------------------------------------------------

    def _draw_player_labels(self):
        state = self.engine.current_state()

        for player_idx in range(NUM_PLAYERS):
            name = f"AI_{player_idx}"
            is_current = (
                not state.is_complete
                and state.current_player_index == player_idx
            )

            # Skóre kola
            round_pts = state.round_points[player_idx]

            label = f"{name}  |  {round_pts}b"
            text_color = T_HIGHLIGHT if is_current else T_TEXT
            surf = self.font_medium.render(label, True, text_color)
            pos = LABEL_POS[player_idx]
            rect = surf.get_rect(center=pos)

            # Pozadie pod menovku
            bg_rect = rect.inflate(12, 6)
            pygame.draw.rect(
                self.screen, T_PANEL_BG, bg_rect, border_radius=4,
            )
            border_color = T_HIGHLIGHT if is_current else T_BORDER
            pygame.draw.rect(
                self.screen, border_color, bg_rect, width=2, border_radius=4,
            )

            self.screen.blit(surf, rect)

    # ------------------------------------------------------------------
    # Log panel
    # ------------------------------------------------------------------

    def _draw_log_panel(self):
        # Pozadie panelu
        pygame.draw.rect(
            self.screen, T_PANEL_BG,
            (LOG_X, LOG_Y, LOG_WIDTH, LOG_HEIGHT),
        )

        x = LOG_X + 10
        y = LOG_Y + 10
        max_text_width = LOG_WIDTH - 20

        # Posledný ťah
        if self.last_step is not None:
            header = self.font_large.render(
                "Posledný ťah", True, T_HIGHLIGHT,
            )
            self.screen.blit(header, (x, y))
            y += header.get_height() + 4

            step_text = (
                f"{self.last_step.player_name} zahral "
                f"{self.last_step.card_played}"
            )
            step_surf = self.font_medium.render(step_text, True, T_TEXT)
            self.screen.blit(step_surf, (x, y))
            y += step_surf.get_height() + 8

            if self.last_step.trick_completed:
                trick_text = (
                    f"→ štich vyhral AI_{self.last_step.trick_winner} "
                    f"(+{self.last_step.trick_points}b)"
                )
                trick_surf = self.font_medium.render(
                    trick_text, True, T_SUCCESS,
                )
                self.screen.blit(trick_surf, (x, y))
                y += trick_surf.get_height() + 8

            if self.last_step.round_completed:
                end_surf = self.font_medium.render(
                    "*** KOLO SKONČILO ***", True, T_WARNING,
                )
                self.screen.blit(end_surf, (x, y))
                y += end_surf.get_height() + 8

            # Reasoning chain
            y += 4
            reason_header = self.font_large.render(
                "Reasoning", True, T_HIGHLIGHT,
            )
            self.screen.blit(reason_header, (x, y))
            y += reason_header.get_height() + 4

            y = self._draw_log_entries(
                self.last_step.log_entries, x, y, max_text_width,
            )

        else:
            # Žiadny ťah ešte nebol — zobraz info o scenári
            header = self.font_large.render(
                "Štart scenára", True, T_HIGHLIGHT,
            )
            self.screen.blit(header, (x, y))
            y += header.get_height() + 6

            desc_lines = self._wrap_text(
                self.scenario.description,
                self.font_small,
                max_text_width,
            )
            for line in desc_lines:
                surf = self.font_small.render(line, True, T_TEXT)
                self.screen.blit(surf, (x, y))
                y += surf.get_height() + 2

            y += 8
            info = self.font_medium.render(
                "Klikni 'Next' (alebo Space) na ďalší ťah",
                True, T_TEXT_DIM,
            )
            self.screen.blit(info, (x, y))

    def _draw_log_entries(self, entries: list[LogEntry],
                          x: int, y: int,
                          max_width: int) -> int:
        """Vykreslí log entries s text wrappingom. Vracia novú y pozíciu."""
        max_y = LOG_Y + LOG_HEIGHT - 20

        for entry in entries:
            lines = TesterLogger.format_entry(entry)
            for line in lines:
                # Zalom dlhý riadok
                wrapped = self._wrap_text(line, self.font_mono, max_width)
                for wline in wrapped:
                    if y >= max_y:
                        overflow = self.font_mono.render(
                            "... [viac riadkov]", True, T_TEXT_DIM,
                        )
                        self.screen.blit(overflow, (x, max_y))
                        return max_y

                    surf = self.font_mono.render(wline, True, T_TEXT)
                    self.screen.blit(surf, (x, y))
                    y += surf.get_height() + 1

        return y

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font,
                    max_width: int) -> list[str]:
        """Jednoduchý text wrap podľa pixelovej šírky."""
        words = text.split()
        lines = []
        current = ""
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

        pygame.draw.rect(
            self.screen, T_HEADER_BG,
            (0, y, WIN_WIDTH, STATUS_HEIGHT),
        )
        pygame.draw.line(
            self.screen, T_BORDER, (0, y), (WIN_WIDTH, y), 1,
        )

        state = self.engine.current_state()

        # Ľavá strana — trick info
        if state.is_complete:
            status_text = "Kolo dokončené"
        else:
            status_text = (
                f"štich {state.trick_number + 1}/8  |  "
                f"Na ťahu: AI_{state.current_player_index}"
            )

        surf = self.font_medium.render(status_text, True, T_TEXT)
        self.screen.blit(surf, (15, y + (STATUS_HEIGHT - surf.get_height()) // 2))

        # Pravá strana — skóre všetkých
        scores_text = "  ".join(
            f"AI_{i}: {state.round_points[i]}b"
            for i in range(NUM_PLAYERS)
        )
        scores_surf = self.font_medium.render(scores_text, True, T_TEXT)
        scores_x = WIN_WIDTH - scores_surf.get_width() - 15
        self.screen.blit(
            scores_surf,
            (scores_x, y + (STATUS_HEIGHT - scores_surf.get_height()) // 2),
        )