# tester/sim_screen.py
"""
GUI spúšťač/konfigurátor pre headless simulátor (tester/simulator.py).

Vznik: 2026-09-29 — počet --no-xxx-watch CLI flagov v simulátore rástol
s každým novým watcherom a bolo čoraz ťažšie mať prehľad, čo je zapnuté.
Toto je vizuálna náhrada: checkboxy zoskupené do záložiek podľa témy
(Sweep / Deklarácie a horníci / Rozhodnutia v štichoch — rozdelenie
zodpovedá modulom v kóde: game/ai_sweep/, ai_declaration.py,
ai_v2/strategies/+selector.py), štvrtá záložka "Výsledky" pre progress
a súhrn po behu. Spustenie na pozadí (aby okno nezamrzlo) + rýchly skok
do prehliadača nálezov (tester_main.py --findings).

Záložkový layout (nahradil pôvodný jednostĺpcový zoznam všetkých
checkboxov naraz — s pribúdajúcimi watchermi to prestávalo byť
prehľadné) — pozri claude/ dokumentáciu k tejto session pre koncept.

Použitie:
    python sim_main.py
"""

import os
import sys
import subprocess
import threading

import pygame

from tester import simulator
from tester.simulator import SimConfig
from config import get_font
from gui.lesson_panel import LessonPanel  # wrap_text — recyklované, netreba duplikovať

# ------------------------------------------------------------------
# Lokálne farby — svetlá "tool" téma, rovnaký princíp ako
# tester/tester_screen.py (iné než tmavá herná paleta v config.py)
# ------------------------------------------------------------------
S_BG = (245, 245, 245)
S_PANEL_BG = (255, 255, 255)
S_TEXT = (20, 20, 20)
S_TEXT_DIM = (100, 100, 100)
S_BORDER = (180, 180, 180)
S_HIGHLIGHT = (200, 140, 30)
S_BUTTON_BG = (220, 220, 220)
S_BUTTON_PRIMARY = (180, 200, 230)
S_BUTTON_SUCCESS = (180, 230, 180)
S_CHECK_ON = (80, 160, 80)
S_INPUT_ACTIVE = (255, 255, 210)
S_ERROR = (180, 40, 40)
S_TAB_BG = (230, 230, 230)
S_TAB_ACTIVE_BG = (255, 255, 255)

WIN_WIDTH = 900
WIN_HEIGHT = 600

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTENT_X = 30
CONTENT_Y = 155
RIGHT_X = 430
# Priestor pred pravým panelom — dlhší text sa musí zalomiť, inak zasahuje
# pod Hier/Seed polia a tlačidlá (a nie vždy je to vidno — text pod bielym
# políčkom sa jednoducho stratí, kým pod priehľadným pozadím je "vidno"
# prekrytie; nájdené 2026-09-29 pri hinte na prázdnej Výsledky záložke).
CONTENT_MAX_WIDTH = RIGHT_X - CONTENT_X - 20

# ------------------------------------------------------------------
# Záložky — (kľúč, popisok, zoznam (SimConfig pole, popisok, submodifikátor))
# Pridanie nového watchera do SimConfig = pridaj riadok do príslušnej
# záložky tu, žiadny ďalší kód sa meniť nemusí.
# ------------------------------------------------------------------
WATCHER_TABS = [
    ("sweep", "Sweep", [
        ("watch_sweep_success", "Sweep — úspešný", False),
        ("watch_sweep_failed", "Sweep — neúspešný", False),
        ("watch_sweep_90_eval", "Sweep 90+ eval (výskum §14)", False),
        ("watch_sweep_ev_audit", "Sweep EV audit (§8)", False),
        ("watch_gate2_audit", "Gate2 audit (§16 A3)", False),
    ]),
    ("declarations", "Deklarácie a horníci", [
        ("watch_none_declaration_failed", "\"Nechytím nič\" zlyhalo", False),
        ("watch_illuminated_and_caught", "Vysvietil + schytal vlastného horníka", False),
        ("illuminated_exclude_high_score", "vylúč 90+ prípady", True),
        ("watch_hornik_capture", "Schytávanie horníkov", False),
    ]),
    ("cardplay", "Rozhodnutia v štichoch", [
        ("watch_global_fallback", "Global fallback", False),
        ("watch_forced_lead_trap", "Forced lead trap", False),
    ]),
]
# Záložka, do ktorej sa dynamicky dopĺňajú položky z SimConfig.watch_decisions
# (napr. AcceptTrick.FORCED_POINTS) — pozri _rows_for_tab.
DECISIONS_TAB_KEY = "cardplay"
RESULTS_TAB_KEY = "results"
RESULTS_TAB_LABEL = "Výsledky"

ALL_WATCHER_FIELDS = [
    (field, label, indented)
    for _key, _tab_label, fields in WATCHER_TABS
    for field, label, indented in fields
]


class SimScreen:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_WIDTH, WIN_HEIGHT))
        pygame.display.set_caption("Chuj — Simulátor")
        self.clock = pygame.time.Clock()
        self.running = True

        self.font_small = get_font(16)
        self.font_medium = get_font(20)
        self.font_large = get_font(26)

        default_cfg = SimConfig()
        self.checked: dict[str, bool] = {
            field: getattr(default_cfg, field) for field, _, _ in ALL_WATCHER_FIELDS
        }
        self.decision_items: list[tuple[str, str]] = list(default_cfg.watch_decisions)
        self.decision_checked: dict[tuple[str, str], bool] = {
            item: True for item in self.decision_items
        }

        self.games_input = str(default_cfg.num_games)
        self.seed_input = ""
        self.active_field: str | None = None  # "games" / "seed" / None

        self.active_tab: str = WATCHER_TABS[0][0]

        # Beh na pozadí — simulácia s pygame vôbec nepracuje, takže je
        # bezpečné pustiť ju vo vlákne. Zdieľaný stav (sim_progress /
        # sim_result / sim_error / sim_running) sa medzi vláknami mení len
        # jednoduchým priradením (nie mutáciou na mieste), čo GIL robí
        # atomickým — pre tento nástroj (nie bezpečnostne kritický kód)
        # to stačí bez zámku.
        self.sim_thread: threading.Thread | None = None
        self.sim_running = False
        self.sim_progress = (0, 0, 0.0)  # (hotovo, spolu, elapsed_s)
        self.sim_result = None  # (findings, stats, elapsed) po dobehnutí
        self.sim_error: str | None = None

        self._build_static_rects()

    # ------------------------------------------------------------------
    # Layout — tab bar a pravý panel sa nemenia podľa aktívnej záložky,
    # počítajú sa raz. Riadky checkboxov aktívnej záložky sa počítajú za
    # behu (_row_rects) — je ich málo (max 5), netreba cachovať.
    # ------------------------------------------------------------------

    def _build_static_rects(self):
        self.tab_rects: dict[str, pygame.Rect] = {}
        x = CONTENT_X
        y = 92
        for key, label in self._tab_keys_labels():
            w = self.font_small.size(self._tab_caption(key, label))[0] + 28
            self.tab_rects[key] = pygame.Rect(x, y, w, 30)
            x += w + 6

        self.games_rect = pygame.Rect(RIGHT_X, CONTENT_Y, 140, 32)
        self.seed_rect = pygame.Rect(RIGHT_X, CONTENT_Y + 60, 140, 32)
        self.run_btn = pygame.Rect(RIGHT_X, CONTENT_Y + 115, 140, 40)
        self.open_tester_btn = pygame.Rect(RIGHT_X, CONTENT_Y + 170, 240, 40)

    @staticmethod
    def _tab_keys_labels():
        labels = [(k, label) for k, label, _fields in WATCHER_TABS]
        labels.append((RESULTS_TAB_KEY, RESULTS_TAB_LABEL))
        return labels

    def _tab_caption(self, key: str, label: str) -> str:
        if key == RESULTS_TAB_KEY:
            return label
        rows = self._rows_for_tab(key)
        # Submodifikátor (napr. "vylúč 90+ prípady") nie je nezávislý
        # watcher, len prepínač správania toho nad ním — do počtu sa
        # nezaratáva.
        countable = [r for r in rows if not r[3]]
        checked = sum(1 for kind, k, _l, _i in countable if self._is_checked(kind, k))
        return f"{label} ({checked}/{len(countable)})"

    # ------------------------------------------------------------------
    # Riadky danej záložky
    # ------------------------------------------------------------------

    def _rows_for_tab(self, tab_key: str):
        """Vráti [(kind, key, label, indented), ...] pre danú záložku.
        kind je 'field' (bool pole SimConfig) alebo 'decision' (položka
        watch_decisions)."""
        if tab_key == RESULTS_TAB_KEY:
            return []
        fields = next(f for k, _l, f in WATCHER_TABS if k == tab_key)
        rows = [("field", field, label, indented) for field, label, indented in fields]
        if tab_key == DECISIONS_TAB_KEY:
            for item in self.decision_items:
                strategy, variant = item
                rows.append(("decision", item, f"{strategy}.{variant}", False))
        return rows

    def _is_checked(self, kind: str, key) -> bool:
        if kind == "field":
            return self.checked[key]
        return self.decision_checked[key]

    def _toggle(self, kind: str, key):
        if kind == "field":
            self.checked[key] = not self.checked[key]
        else:
            self.decision_checked[key] = not self.decision_checked[key]

    def _row_rects(self, tab_key: str):
        """Riadky danej záložky s vypočítanými Rect-mi checkboxov —
        [(kind, key, label, indented, rect), ...]."""
        out = []
        y = CONTENT_Y
        for kind, key, label, indented in self._rows_for_tab(tab_key):
            cx = CONTENT_X + (24 if indented else 0)
            out.append((kind, key, label, indented, pygame.Rect(cx, y, 20, 20)))
            y += 30
        return out

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
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(event.pos)

    def _handle_keydown(self, event):
        if self.active_field is None:
            if event.key == pygame.K_ESCAPE:
                self.running = False
            return
        target = "games_input" if self.active_field == "games" else "seed_input"
        current = getattr(self, target)
        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.active_field = None
        elif event.key == pygame.K_BACKSPACE:
            setattr(self, target, current[:-1])
        elif event.unicode.isdigit():
            setattr(self, target, current + event.unicode)

    def _handle_click(self, pos):
        for key, rect in self.tab_rects.items():
            if rect.collidepoint(pos):
                self.active_tab = key
                return

        for kind, key, _label, _indented, rect in self._row_rects(self.active_tab):
            if rect.collidepoint(pos):
                self._toggle(kind, key)
                return

        if self.games_rect.collidepoint(pos):
            self.active_field = "games"
            return
        if self.seed_rect.collidepoint(pos):
            self.active_field = "seed"
            return
        self.active_field = None

        if self.run_btn.collidepoint(pos) and not self.sim_running:
            self._start_simulation()
            return

        if self.open_tester_btn.collidepoint(pos):
            self._open_tester()
            return

    # ------------------------------------------------------------------
    # Spustenie simulácie (na pozadí)
    # ------------------------------------------------------------------

    def _build_config(self) -> SimConfig:
        try:
            num_games = max(1, int(self.games_input))
        except ValueError:
            num_games = 100
        seed = int(self.seed_input) if self.seed_input.strip() else None

        kwargs = {field: self.checked[field] for field, _, _ in ALL_WATCHER_FIELDS}
        watch_decisions = [
            item for item in self.decision_items if self.decision_checked[item]
        ]
        return SimConfig(
            num_games=num_games,
            seed=seed,
            watch_decisions=watch_decisions,
            **kwargs,
        )

    def _start_simulation(self):
        config = self._build_config()
        self.sim_running = True
        self.sim_progress = (0, config.num_games, 0.0)
        self.sim_result = None
        self.sim_error = None
        # Rovno na Výsledky — nech je vidno progress bez ručného preklikania.
        self.active_tab = RESULTS_TAB_KEY

        def progress_cb(done, total, elapsed):
            self.sim_progress = (done, total, elapsed)

        def worker():
            try:
                result = simulator.run(config, progress_callback=progress_cb)
                self.sim_result = result
            except Exception as e:
                self.sim_error = f"{type(e).__name__}: {e}"
            finally:
                self.sim_running = False

        self.sim_thread = threading.Thread(target=worker, daemon=True)
        self.sim_thread.start()

    def _open_tester(self):
        """Spustí tester_main.py --findings ako samostatný proces (needusí
        blokovať/zavrieť toto okno — dajú sa mať otvorené obe naraz)."""
        tester_main = os.path.join(_REPO_ROOT, "tester_main.py")
        if not os.path.exists(tester_main):
            return
        try:
            subprocess.Popen([sys.executable, tester_main, "--findings"],
                             cwd=_REPO_ROOT)
        except Exception as e:
            print(f"[SimScreen] Nepodarilo sa spustiť tester: {e}")

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def _draw(self):
        self.screen.fill(S_BG)
        self._draw_header()
        self._draw_tabs()
        self._draw_content()
        self._draw_right_panel()

    def _blit_wrapped(self, text: str, x: int, y: int, color,
                      max_width: int = CONTENT_MAX_WIDTH) -> int:
        """Vykreslí text zalomený na max_width (pozri CONTENT_MAX_WIDTH —
        inak zasahuje pod pravý panel). Vráti y hneď POD posledným
        riadkom, aby sa dal ďalší prvok napojiť bez napevno zadaného
        odhadu výšky."""
        lines = LessonPanel.wrap_text(text, self.font_small, max_width)
        for line in lines:
            surf = self.font_small.render(line, True, color)
            self.screen.blit(surf, (x, y))
            y += 20
        return y

    def _draw_header(self):
        title = self.font_large.render("Chuj — Simulátor", True, S_TEXT)
        self.screen.blit(title, (30, 18))
        sub = self.font_small.render(
            "Headless batch beh (tester/simulator.py) — konfigurácia a spustenie",
            True, S_TEXT_DIM
        )
        self.screen.blit(sub, (30, 52))

    def _draw_tabs(self):
        for key, label in self._tab_keys_labels():
            rect = self.tab_rects[key]
            active = key == self.active_tab
            bg = S_TAB_ACTIVE_BG if active else S_TAB_BG
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            border = S_HIGHLIGHT if active else S_BORDER
            pygame.draw.rect(
                self.screen, border, rect, width=2 if active else 1, border_radius=6
            )
            caption = self._tab_caption(key, label)
            text = self.font_small.render(caption, True, S_TEXT if active else S_TEXT_DIM)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

    def _draw_content(self):
        if self.active_tab == RESULTS_TAB_KEY:
            if self.sim_running:
                self._draw_progress()
            elif self.sim_error:
                self._draw_error()
            elif self.sim_result:
                self._draw_summary()
            else:
                self._blit_wrapped(
                    "Zatiaľ žiadny beh — nastav watchery v záložkách a klikni Spustiť.",
                    CONTENT_X, CONTENT_Y, S_TEXT_DIM
                )
            return

        rows = self._row_rects(self.active_tab)
        for kind, key, label, indented, rect in rows:
            pygame.draw.rect(self.screen, S_PANEL_BG, rect)
            pygame.draw.rect(self.screen, S_BORDER, rect, width=1)
            if self._is_checked(kind, key):
                inner = rect.inflate(-6, -6)
                pygame.draw.rect(self.screen, S_CHECK_ON, inner)
            color = S_TEXT_DIM if indented else S_TEXT
            text = self.font_small.render(label, True, color)
            self.screen.blit(text, (rect.right + 8, rect.y + 2))

        if self.active_tab == DECISIONS_TAB_KEY:
            # Pozícia počítaná dynamicky podľa počtu riadkov (presne ten
            # istý druh chyby ako pri progress bare v predošlej verzii by
            # sa tu zopakoval pri napevno zadanom y).
            y = (rows[-1][4].bottom + 12) if rows else CONTENT_Y
            self._blit_wrapped(
                "(ďalšie kombinácie zatiaľ cez SimConfig.watch_decisions v kóde"
                " — objavia sa tu ako checkbox automaticky)",
                CONTENT_X, y, S_TEXT_DIM
            )

    def _draw_right_panel(self):
        self._draw_labeled_input(
            "Hier:", self.games_rect, self.games_input,
            self.active_field == "games"
        )
        self._draw_labeled_input(
            "Seed (voliteľné):", self.seed_rect, self.seed_input,
            self.active_field == "seed"
        )
        can_run = not self.sim_running
        self._draw_button(
            self.run_btn, "Spustiť",
            S_BUTTON_PRIMARY if can_run else S_BUTTON_BG
        )
        self._draw_button(self.open_tester_btn, "Otvoriť v testeri", S_BUTTON_SUCCESS)

    def _draw_labeled_input(self, label, rect, value, active):
        text = self.font_small.render(label, True, S_TEXT)
        self.screen.blit(text, (rect.x, rect.y - 20))
        bg = S_INPUT_ACTIVE if active else S_PANEL_BG
        pygame.draw.rect(self.screen, bg, rect)
        pygame.draw.rect(
            self.screen, S_HIGHLIGHT if active else S_BORDER, rect,
            width=2 if active else 1
        )
        val_surf = self.font_medium.render(value or " ", True, S_TEXT)
        self.screen.blit(val_surf, (rect.x + 8, rect.y + 5))

    def _draw_button(self, rect, label, color):
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        pygame.draw.rect(self.screen, S_BORDER, rect, width=1, border_radius=6)
        text = self.font_medium.render(label, True, S_TEXT)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def _draw_progress(self):
        done, total, elapsed = self.sim_progress
        y = CONTENT_Y
        text = self.font_medium.render(
            f"Beží... hra {done}/{total} ({elapsed:.1f}s)", True, S_TEXT
        )
        self.screen.blit(text, (CONTENT_X, y))

        bar_rect = pygame.Rect(CONTENT_X, y + 30, 340, 18)
        pygame.draw.rect(self.screen, S_PANEL_BG, bar_rect)
        pygame.draw.rect(self.screen, S_BORDER, bar_rect, width=1)
        if total > 0:
            frac = min(1.0, done / total)
            fill_rect = pygame.Rect(
                bar_rect.x, bar_rect.y, int(bar_rect.w * frac), bar_rect.h
            )
            pygame.draw.rect(self.screen, S_HIGHLIGHT, fill_rect)

    def _draw_error(self):
        self._blit_wrapped(f"Chyba: {self.sim_error}", CONTENT_X, CONTENT_Y, S_ERROR)

    def _draw_summary(self):
        findings, stats, elapsed = self.sim_result
        x, y = CONTENT_X, CONTENT_Y
        header = self.font_medium.render(
            f"Hotovo — {stats.get('games_total', 0)} hier, "
            f"{stats.get('rounds_total', 0)} kôl, {elapsed:.1f}s",
            True, S_TEXT
        )
        self.screen.blit(header, (x, y))
        y += 32

        final_scores = stats.get("final_scores", [])
        if final_scores:
            avg = sum(final_scores) / len(final_scores)
            avg_text = self.font_small.render(
                f"Priemerné finálne skóre: {avg:.1f}", True, S_TEXT_DIM
            )
            self.screen.blit(avg_text, (x, y))
            y += 24

        y += 10
        col_header = self.font_small.render(
            "NÁLEZY (výskytov | kôl s aspoň 1 výskytom)", True, S_TEXT_DIM
        )
        self.screen.blit(col_header, (x, y))
        y += 22

        # Rovnaká logika ako _write_output v simulator.py — kôl s aspoň
        # 1 výskytom, nie surový počet výskytov (jedno kolo môže mať
        # viac nálezov toho istého typu).
        rounds_with_finding: dict[str, set] = {}
        for rec in findings.records:
            key = (rec.get("game_index"), rec.get("round_number"))
            rounds_with_finding.setdefault(rec["type"], set()).add(key)

        for ftype in sorted(findings.counts.keys()):
            if y > WIN_HEIGHT - 30:
                more = self.font_small.render("…", True, S_TEXT_DIM)
                self.screen.blit(more, (x, y))
                break
            count = findings.counts[ftype]
            rounds_affected = len(rounds_with_finding.get(ftype, set()))
            row = self.font_small.render(
                f"{ftype}: {count} | {rounds_affected}", True, S_TEXT
            )
            self.screen.blit(row, (x, y))
            y += 20
