# tester/sim_screen.py
"""
Simulátor GUI — nastavenia + progress + výsledky.

Spustenie samostatne:
    python -m tester.sim_screen
"""

import os
import sys
import threading
import time
import subprocess
import pygame

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tester.simulator import (
    SimConfig, Findings, OUTPUT_DIR,
    _run_single_game, _write_output,
)

# ------------------------------------------------------------------
# Vzhľad — bielo-šedý štýl, čierne písmo (štýl testera)
# ------------------------------------------------------------------

W, H = 720, 640
FPS = 30

C_BG = (240, 240, 240)          # svetlošedé pozadie
C_PANEL = (255, 255, 255)       # biele panely/inputy
C_BORDER = (160, 160, 160)      # šedý rám
C_BORDER_DARK = (100, 100, 100)
C_TEXT = (0, 0, 0)              # čierne písmo
C_TEXT_DIM = (120, 120, 120)
C_ACCENT = (0, 100, 200)        # modrý akcent (aktívne prvky)
C_BTN = (225, 225, 225)         # tlačidlo
C_BTN_HOVER = (210, 210, 210)
C_GREEN = (40, 140, 60)
C_RED = (190, 40, 40)

FONT_NAME = "tahoma"

WATCHES = [
    ("watch_illuminated_and_caught",   "Vysvietil + schytal vlastného horníka", False),
    ("illuminated_exclude_high_score", "vylúč 90+ prípady", True),
    ("watch_none_declaration_failed",  "Nechytím nič — zlyhalo", False),
    ("watch_global_fallback",          "Global fallback", False),
    ("watch_sweep_result",             "Sweep (zobral/nezobral všetko)", False),
]


def _text(surf, font, txt, color, **anchor):
    s = font.render(txt, True, color)
    surf.blit(s, s.get_rect(**anchor))


# ------------------------------------------------------------------
# SimSetupScreen
# ------------------------------------------------------------------

class SimSetupScreen:
    LEFT = 50       # ľavý okraj labelov
    CTRL_X = 420    # stĺpec ovládacích prvkov

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont(FONT_NAME, 26, bold=True)
        self.font = pygame.font.SysFont(FONT_NAME, 16)
        self.font_sm = pygame.font.SysFont(FONT_NAME, 14)

        self.num_games = 100
        self.seed_enabled = False
        self.seed_value = 42
        self.system = "new"

        self.watches = {k: True for k, _, _ in WATCHES}

        self._editing_games = False
        self._editing_seed = False
        self._input_buf = ""

        self._build_layout()

    def _build_layout(self):
        y = 80
        self.games_y = y
        self.games_input_rect = pygame.Rect(self.CTRL_X, y - 14, 110, 28)
        y += 44

        self.seed_y = y
        self.seed_check_rect = pygame.Rect(self.CTRL_X, y - 11, 22, 22)
        self.seed_input_rect = pygame.Rect(self.CTRL_X + 32, y - 14, 100, 28)
        y += 44

        self.sys_y = y
        self.sys_new_rect = pygame.Rect(self.CTRL_X, y - 14, 80, 28)
        self.sys_old_rect = pygame.Rect(self.CTRL_X + 88, y - 14, 80, 28)
        y += 54

        self.watch_header_y = y
        y += 32
        self.watch_rects = {}
        for k, label, indent in WATCHES:
            cb = pygame.Rect(self.CTRL_X, y - 11, 22, 22)
            self.watch_rects[k] = (cb, y, label, indent)
            y += 32
        y += 20

        self.run_btn = pygame.Rect(W // 2 - 100, y, 200, 40)

    # -------------------- beh --------------------

    def run(self) -> SimConfig | None:
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                result = self._handle(event)
                if result == "quit":
                    return None
                if result == "run":
                    return self._build_config()
            self._draw()
            pygame.display.flip()

    def _build_config(self) -> SimConfig:
        cfg = SimConfig(num_games=self.num_games)
        if self.seed_enabled:
            cfg.seed = self.seed_value
        for k, _, _ in WATCHES:
            setattr(cfg, k, self.watches[k])
        cfg._use_old_system = (self.system == "old")
        return cfg

    # -------------------- eventy --------------------

    def _handle(self, event):
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos)
        return None

    def _handle_key(self, event):
        if not (self._editing_games or self._editing_seed):
            return
        if event.key == pygame.K_RETURN:
            self._commit_input()
        elif event.key == pygame.K_ESCAPE:
            self._editing_games = self._editing_seed = False
        elif event.key == pygame.K_BACKSPACE:
            self._input_buf = self._input_buf[:-1]
        elif event.unicode.isdigit():
            self._input_buf += event.unicode

    def _commit_input(self):
        val = int(self._input_buf) if self._input_buf.isdigit() else None
        if self._editing_games and val and val > 0:
            self.num_games = min(val, 99999)
        if self._editing_seed and val is not None:
            self.seed_value = val
        self._editing_games = self._editing_seed = False

    def _handle_click(self, pos):
        if self.games_input_rect.collidepoint(pos):
            self._editing_games, self._editing_seed = True, False
            self._input_buf = str(self.num_games)
            return None
        if self.seed_check_rect.collidepoint(pos):
            self.seed_enabled = not self.seed_enabled
            return None
        if self.seed_enabled and self.seed_input_rect.collidepoint(pos):
            self._editing_seed, self._editing_games = True, False
            self._input_buf = str(self.seed_value)
            return None
        if self.sys_new_rect.collidepoint(pos):
            self.system = "new"
        if self.sys_old_rect.collidepoint(pos):
            self.system = "old"
        for k, (cb, y, label, indent) in self.watch_rects.items():
            if cb.collidepoint(pos):
                if (k == "illuminated_exclude_high_score"
                        and not self.watches["watch_illuminated_and_caught"]):
                    break
                self.watches[k] = not self.watches[k]
                break
        if self.run_btn.collidepoint(pos):
            self._commit_input()
            return "run"
        return None

    # -------------------- kreslenie --------------------

    def _draw_input(self, rect, value, editing):
        pygame.draw.rect(self.screen, C_PANEL, rect)
        pygame.draw.rect(self.screen,
                         C_ACCENT if editing else C_BORDER, rect, 1)
        txt = (value + "|") if editing else value
        _text(self.screen, self.font, txt, C_TEXT,
              centerx=rect.centerx, centery=rect.centery)

    def _draw_checkbox(self, rect, checked, grayed=False):
        pygame.draw.rect(self.screen, C_PANEL, rect)
        pygame.draw.rect(self.screen,
                         C_BORDER if grayed else C_BORDER_DARK, rect, 1)
        if checked and not grayed:
            inner = rect.inflate(-8, -8)
            pygame.draw.rect(self.screen, C_ACCENT, inner)

    def _draw(self):
        self.screen.fill(C_BG)

        _text(self.screen, self.font_title, "Simulátor", C_TEXT,
              left=self.LEFT, centery=40)

        # Počet hier
        _text(self.screen, self.font, "Počet hier:", C_TEXT,
              left=self.LEFT, centery=self.games_y)
        val = self._input_buf if self._editing_games else str(self.num_games)
        self._draw_input(self.games_input_rect, val, self._editing_games)

        # Seed
        _text(self.screen, self.font, "Seed:", C_TEXT,
              left=self.LEFT, centery=self.seed_y)
        self._draw_checkbox(self.seed_check_rect, self.seed_enabled)
        if self.seed_enabled:
            val = self._input_buf if self._editing_seed else str(self.seed_value)
            self._draw_input(self.seed_input_rect, val, self._editing_seed)
        else:
            _text(self.screen, self.font_sm, "(náhodný)", C_TEXT_DIM,
                  left=self.seed_check_rect.right + 10, centery=self.seed_y)

        # Systém
        _text(self.screen, self.font, "AI systém:", C_TEXT,
              left=self.LEFT, centery=self.sys_y)
        for label, rect, key in [("NOVÝ", self.sys_new_rect, "new"),
                                  ("STARÝ", self.sys_old_rect, "old")]:
            active = self.system == key
            pygame.draw.rect(self.screen, C_PANEL, rect)
            pygame.draw.rect(self.screen,
                             C_ACCENT if active else C_BORDER, rect,
                             2 if active else 1)
            _text(self.screen, self.font, label,
                  C_ACCENT if active else C_TEXT,
                  centerx=rect.centerx, centery=rect.centery)

        # Watchers
        _text(self.screen, self.font, "Sledovať:", C_TEXT,
              left=self.LEFT, centery=self.watch_header_y)
        for k, (cb, y, label, indent) in self.watch_rects.items():
            grayed = (k == "illuminated_exclude_high_score"
                      and not self.watches["watch_illuminated_and_caught"])
            self._draw_checkbox(cb, self.watches[k], grayed)
            x = self.LEFT + (46 if indent else 20)
            prefix = "└ " if indent else ""
            _text(self.screen, self.font_sm, prefix + label,
                  C_TEXT_DIM if grayed else C_TEXT,
                  left=x, centery=y)

        # Tlačidlo SPUSTIŤ
        hover = self.run_btn.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen,
                         C_BTN_HOVER if hover else C_BTN, self.run_btn)
        pygame.draw.rect(self.screen, C_BORDER_DARK, self.run_btn, 1)
        _text(self.screen, self.font, "Spustiť", C_TEXT,
              centerx=self.run_btn.centerx, centery=self.run_btn.centery)


# ------------------------------------------------------------------
# SimRunScreen
# ------------------------------------------------------------------

class SimRunScreen:
    def __init__(self, screen: pygame.Surface, config: SimConfig):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.config = config
        self.font_title = pygame.font.SysFont(FONT_NAME, 24, bold=True)
        self.font = pygame.font.SysFont(FONT_NAME, 16)
        self.font_sm = pygame.font.SysFont(FONT_NAME, 14)

        self._progress = 0
        self._findings_count = 0
        self._done = False
        self._elapsed = 0.0
        self._stats: dict = {}
        self._findings: Findings | None = None
        self._error: str | None = None

        cx = W // 2
        self.btn_open = pygame.Rect(cx - 250, H - 70, 170, 36)
        self.btn_findings = pygame.Rect(cx - 70, H - 70, 170, 36)
        self.btn_new = pygame.Rect(cx + 110, H - 70, 80, 36)

        self._thread = threading.Thread(target=self._run_sim, daemon=True)
        self._thread.start()

    def _run_sim(self):
        import random as _random
        findings = Findings()
        stats: dict = {}
        rng = _random.Random(self.config.seed)
        start = time.time()

        for i in range(self.config.num_games):
            _random.seed(rng.randint(0, 2 ** 31))
            try:
                _run_single_game(i, self.config, findings, stats)
            except Exception as e:
                self._error = f"Chyba v hre {i}: {e}"
                self._done = True
                return
            self._progress = i + 1
            self._findings_count = len(findings.records)
            self._elapsed = time.time() - start

        self._elapsed = time.time() - start
        self._stats = stats
        self._findings = findings
        _write_output(self.config, findings, stats, self._elapsed)
        self._done = True

    def run(self) -> str:
        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    result = self._handle_click(event.pos)
                    if result:
                        return result
            self._draw()
            pygame.display.flip()

    def _handle_click(self, pos) -> str | None:
        if not self._done:
            return None
        if self.btn_open.collidepoint(pos):
            self._open_file(os.path.join(OUTPUT_DIR, "sim_summary.txt"))
        if self.btn_findings.collidepoint(pos):
            self._open_tester_findings()
        if self.btn_new.collidepoint(pos):
            return "new"
        return None

    @staticmethod
    def _open_file(path):
        if not os.path.exists(path):
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])

    @staticmethod
    def _open_tester_findings():
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.Popen(
            [sys.executable, os.path.join(root, "tester_main.py"), "--findings"],
            cwd=root,
        )

    def _draw(self):
        self.screen.fill(C_BG)
        cx = W // 2
        n = self.config.num_games
        prog, done = self._progress, self._done

        status = "Hotovo" if done else "Prebieha…"
        _text(self.screen, self.font_title, f"Simulácia — {status}",
              C_GREEN if done else C_TEXT, left=50, centery=40)

        _text(self.screen, self.font,
              f"Hier: {prog} / {n}    Čas: {self._elapsed:.1f}s    "
              f"Nálezov: {self._findings_count}",
              C_TEXT, left=50, centery=80)

        # Progress bar
        bar = pygame.Rect(50, 105, W - 100, 24)
        pygame.draw.rect(self.screen, C_PANEL, bar)
        pygame.draw.rect(self.screen, C_BORDER, bar, 1)
        if n:
            fill = pygame.Rect(bar.x + 1, bar.y + 1,
                               int((bar.width - 2) * prog / n), bar.height - 2)
            pygame.draw.rect(self.screen,
                             C_GREEN if done else C_ACCENT, fill)
        _text(self.screen, self.font_sm, f"{int(100 * prog / n) if n else 0}%",
              C_TEXT, centerx=cx, centery=bar.centery)

        if self._error:
            _text(self.screen, self.font, f"CHYBA: {self._error}", C_RED,
                  left=50, centery=170)
            return

        if done:
            stats, findings = self._stats, self._findings
            y = 165
            fs = stats.get("final_scores", [])
            lines = [
                f"Kôl spolu: {stats.get('rounds_total', 0):,}",
                f"Priemerné finálne skóre: "
                f"{(sum(fs) / len(fs)) if fs else 0:.1f}",
                "Prehry:  " + "   ".join(
                    f"AI_{i}: {stats.get(f'loser_AI_{i}', 0)}"
                    for i in range(4)
                ),
            ]
            for line in lines:
                _text(self.screen, self.font, line, C_TEXT, left=50, centery=y)
                y += 28

            y += 12
            _text(self.screen, self.font, "Nálezy:", C_TEXT, left=50, centery=y)
            y += 28
            if findings:
                for ftype, count in sorted(findings.counts.items()):
                    _text(self.screen, self.font_sm,
                          f"{ftype}: {count:,}", C_TEXT, left=70, centery=y)
                    y += 24

            path = os.path.join(OUTPUT_DIR, "sim_findings.jsonl")
            _text(self.screen, self.font_sm, path, C_TEXT_DIM,
                  left=50, centery=y + 12)

            for rect, label in [(self.btn_open, "Otvoriť súhrn"),
                                (self.btn_findings, "Nálezy v testeri"),
                                (self.btn_new, "Nová")]:
                hover = rect.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen,
                                 C_BTN_HOVER if hover else C_BTN, rect)
                pygame.draw.rect(self.screen, C_BORDER_DARK, rect, 1)
                _text(self.screen, self.font_sm, label, C_TEXT,
                      centerx=rect.centerx, centery=rect.centery)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main(screen: pygame.Surface | None = None):
    standalone = screen is None
    if standalone:
        pygame.init()
        screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("CHUJ — Simulátor")

    while True:
        setup = SimSetupScreen(screen)
        config = setup.run()
        if config is None:
            break
        run_screen = SimRunScreen(screen, config)
        result = run_screen.run()
        if result != "new":
            break

    if standalone:
        pygame.quit()


if __name__ == "__main__":
    main()