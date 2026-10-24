# tools/res_testbed.py
#
# Testbed na porovnanie techník podpory rozlíšení — krok 1 reworku
# (claude/11_RESOLUTION_REWORK_ANALYSIS.md §4). Samostatný súbor, hru
# NEMENÍ — kreslí len reprezentatívnu vzorku hernej obrazovky (karty,
# tlačidlá, panel KOLO, výklad, bublinu) tromi technikami:
#
#   a1      — logické plátno 1920×L_h → pygame.transform.smoothscale na okno
#             (CPU, každú snímku)
#   scaled  — logické plátno cez pygame.SCALED (škáluje GPU) — len naživo
#   hybrid  — kreslí sa priamo v natívnom rozlíšení cez vrstvu Canvas
#             (logické súradnice → fyzické; text vo fyzickej veľkosti,
#             karty z cards-large cez smoothscale)
#
# Scéna je napísaná LEN RAZ, v logických súradniciach, cez API Canvas —
# rovnaké API, aké by po schválení dostali obrazovky hry. Techniky sa
# líšia len tým, kam a v akej mierke Canvas kreslí. Testbed tak zároveň
# overuje, či API Canvas pokryje vzory, ktoré hra používa (otočené karty,
# copy()+set_alpha(), text zalamovaný podľa metrík fontu, overlaye).
#
# Logický priestor: šírka vždy 1920, výška L_h = 1080…1200 podľa pomeru
# strán (16:10 využije extra výšku), širšie než 16:9 → pásma po bokoch.
#
# NAŽIVO:
#   python tools/res_testbed.py                                  # natívne, bezrámovo
#   python tools/res_testbed.py --resolution 1366x768 --windowed
#   python tools/res_testbed.py --resolution 1440x900 --windowed --technique a1
#
#   Klávesy: 1 = a1, 2 = scaled, 3 = hybrid, C = cache statickej vrstvy
#            (len hybrid), H = 16:10 výška zap/vyp,
#            G = mriežka logického priestoru, O = overlay cez celú obrazovku,
#            F = frametime, Z = lupa 2× pod myšou, S = screenshot, Esc = koniec
#
# HEADLESS (bez okna, aj rozlíšenia väčšie než monitor):
#   python tools/res_testbed.py --offscreen testbed_out
#   → pre každé rozlíšenie PNG oboch techník (a1, hybrid), výrezy textu a
#     karty 1:1 vedľa seba (crop_*.png) a timings.csv s časom snímky.
#   Technika "scaled" sa headless odmerať nedá (bez GPU); vizuálne je
#   podobná a1 (ten istý zväčšený bitmap, len iný filter).

import argparse
import csv
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGICAL_W = 1920
L_H_MIN, L_H_MAX = 1080, 1200

OFFSCREEN_RESOLUTIONS = [
    (1366, 768), (1920, 1080), (1920, 1200), (2560, 1440),
    (2560, 1600), (3440, 1440), (3840, 2160),
]

CARD_W, CARD_H = 181, 293   # logická veľkosť karty (= dnešná medium)

COLOR_GOLD = (212, 160, 40)
COLOR_WHITE = (255, 248, 235)
COLOR_GRAY = (120, 100, 80)
COLOR_YELLOW = (255, 220, 100)
COLOR_RED = (200, 60, 40)
COLOR_GREEN = (80, 180, 80)
COLOR_PANEL = (25, 15, 8)
COLOR_BTN_PRIMARY = (180, 110, 45)
COLOR_BTN_SECONDARY = (60, 45, 30)


# ======================================================================
# Viewport — logický priestor a mierka
# ======================================================================

class Viewport:
    """Ako sa logický priestor 1920×L_h zmestí do okna W×H."""

    def __init__(self, width: int, height: int, use_extra_height: bool = True):
        self.width, self.height = width, height
        if use_extra_height:
            ideal = LOGICAL_W * height / width
            self.l_h = int(round(min(L_H_MAX, max(L_H_MIN, ideal))))
        else:
            self.l_h = L_H_MIN
        self.scale = min(width / LOGICAL_W, height / self.l_h)
        self.phys_w = round(LOGICAL_W * self.scale)
        self.phys_h = round(self.l_h * self.scale)
        self.ox = (width - self.phys_w) // 2
        self.oy = (height - self.phys_h) // 2

    def to_logical(self, pos):
        x, y = pos
        return ((x - self.ox) / self.scale, (y - self.oy) / self.scale)

    def describe(self) -> str:
        bands = ""
        if self.ox:
            bands = f", pásma po bokoch {self.ox}px"
        elif self.oy:
            bands = f", pásma hore/dole {self.oy}px"
        return (f"{self.width}x{self.height}  s={self.scale:.3f}  "
                f"logicky 1920x{self.l_h}{bands}")


# ======================================================================
# Canvas — od kroku 2 žije v gui/canvas.py (tu sa len importuje, aby
# testbed overoval presne ten kód, ktorý bude používať hra)
# ======================================================================

Canvas = None   # doplní _load_canvas() — import až po nastavení SDL ovládača


def _load_canvas():
    """gui.canvas importuje config → gui.display, ktorý pri importe zisťuje
    rozlíšenie monitora. Headless (--offscreen) preto musí byť SDL_VIDEODRIVER
    nastavený skôr, než sa importuje."""
    global Canvas
    sys.path.insert(0, ROOT)
    from gui.canvas import Canvas as _GuiCanvas

    class _TestbedCanvas(_GuiCanvas):
        def card(self, name, angle=0, lsize=(CARD_W, CARD_H)):
            return super().card(f"{name}.png", angle, lsize)

    Canvas = _TestbedCanvas


# ======================================================================
# Scéna — napísaná raz, v logických súradniciach
# ======================================================================

HUMAN_HAND = ["heart-ace", "heart-nine", "bell-king", "bell-seven",
              "leaf-over", "leaf-ten", "acorn-under", "acorn-eight"]
TRICK = [("acorn-ace", 0, 120), ("leaf-nine", 150, 0),
         ("bell-ten", 0, -120), ("heart-king", -150, 0)]
LESSON_TEXT = (
    "V každom štichu zahrá každý zo štyroch hráčov jednu kartu. "
    "Ostatní musia priznať farbu — zahrať kartu rovnakej farby. "
    "Štich vyhráva najvyššia karta vo farbe, ktorou sa začínalo."
)
LESSON_SMALL = "Malé písmo (18): Vysvietený zelený horník = 16 b, žaluďový = 8 b."


def wrap(font, text, max_w):
    lines = []
    for para in text.split("\n\n"):
        if lines:
            lines.append("")
        cur = ""
        for word in para.split(" "):
            test = f"{cur} {word}".strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def draw_button(c: "Canvas", rect, label, color, hover):
    c.overlay(rect, (*color, 240 if hover else 200))
    c.rect(COLOR_WHITE if hover else COLOR_GOLD, rect, width=2, border_radius=8)
    surf = c.font(24).render(label, True, COLOR_WHITE)
    c.blit(surf, surf.get_rect(center=rect.center))


def _draw_buttons(c: "Canvas", l_h: int, mouse_logical):
    import pygame
    tcx, tcy = LOGICAL_W // 2, l_h // 2
    # Tlačidlá záväzku a OK
    by = tcy + CARD_H // 2 + 18
    for rect, label, primary in (
        (pygame.Rect(tcx - 420, by, 260, 50), "Beriem všetko  [-20b]", False),
        (pygame.Rect(tcx - 140, by, 260, 50), "Nechytím nič  [-10b]", True),
        (pygame.Rect(tcx + 140, by, 120, 50), "OK", True),
    ):
        draw_button(c, rect, label, COLOR_BTN_PRIMARY if primary
                    else COLOR_BTN_SECONDARY, rect.collidepoint(mouse_logical))

    # Stĺpec tlačidiel vpravo dole (opravený — nekoliduje so záväzkom)
    for i, label in enumerate(["Tipy: ZAP", "Posledný štich", "Chujogram",
                               "Pravidlá", "Menu"]):
        rect = pygame.Rect(LOGICAL_W - 600, l_h - 330 + i * 60, 200, 50)
        draw_button(c, rect, label, COLOR_BTN_SECONDARY,
                    rect.collidepoint(mouse_logical))


def draw_scene(c: "Canvas", l_h: int, mouse_logical, flags: dict, title: str,
               part: str = "all"):
    """part: "all" | "static" (všetko okrem tlačidiel s hoverom) |
    "dynamic" (len tlačidlá). Rozdelenie slúži na meranie cache statickej
    vrstvy — v kartovej hre sa väčšina obrazovky medzi snímkami nemení."""
    if part == "dynamic":
        _draw_buttons(c, l_h, mouse_logical)
        return
    tcx, tcy = LOGICAL_W // 2, l_h // 2
    # Kotvy: ruka hráča a tlačidlá dole, PC2 hore, stôl v strede.
    # Pri 16:10 (l_h=1200) sa extra výška rozdelí medzi ruky a štich.
    hand_y = l_h - 220

    # PC2 hore (otočené rubom), PC3 vľavo, PC1 vpravo
    for i in range(8):
        c.blit(c.card("card-back", 180), (400 + i * 100, -50))
    for i in range(8):
        c.blit(c.card("card-back", -90), (30, 150 + i * 65))
        c.blit(c.card("card-back", 90), (LOGICAL_W - 30 - CARD_H, 150 + i * 65))

    # Štich v strede
    for name, dx, dy in TRICK:
        img = c.card(name)
        c.blit(img, img.get_rect(center=(tcx + dx, tcy + dy)))

    # Ruka hráča (prvá karta „vysvietená" ako v hre: posun o 20 nahor)
    for i, name in enumerate(HUMAN_HAND):
        y = hand_y - (20 if name == "leaf-over" else 0)
        c.blit(c.card(name), (400 + i * 100, y))
        c.rect(COLOR_GREEN, (400 + i * 100 - 2, y - 2, CARD_W + 4, CARD_H + 4),
               width=3, border_radius=5)

    # Ukážka copy()+set_alpha() (tutoriálová animácia štichu)
    ghost = c.card("heart-seven").copy()
    ghost.set_alpha(110)
    c.blit(ghost, ghost.get_rect(center=(tcx + 420, tcy)))

    if part == "all":
        _draw_buttons(c, l_h, mouse_logical)

    # Panel KOLO vpravo dole — písmo 30/24/18
    px, py, pw, ph = LOGICAL_W - 370, l_h - 280, 350, 260
    c.overlay((px, py, pw, ph), (20, 12, 5, 210))
    c.rect(COLOR_GOLD, (px, py, pw, ph), width=2, border_radius=10)
    t = c.font(30).render("KOLO 7", True, COLOR_GOLD)
    c.blit(t, t.get_rect(left=px + 30, top=py + 8))
    seed = c.font(18).render("(27 856 498)", True, COLOR_GRAY)
    c.blit(seed, seed.get_rect(right=px + pw - 8, centery=py + 8 + t.get_height() // 2))
    c.line(COLOR_GOLD, (px + 10, py + 43), (px + pw - 10, py + 43))
    for i, (name, pts) in enumerate([("Hráč", "0b"), ("Počítač 1", "+8b"),
                                     ("Počítač 2", "+1b"), ("Počítač 3", "0b")]):
        y = py + 48 + i * 48
        n = c.font(24).render(name, True, COLOR_YELLOW if i == 0 else COLOR_WHITE)
        c.blit(n, (px + 10, y))
        p = c.font(24).render(pts, True, COLOR_RED if pts != "0b" else COLOR_GRAY)
        c.blit(p, p.get_rect(right=px + pw - 10, top=y))
        for k in range(5):
            c.circle(COLOR_GREEN if k < i + 1 else COLOR_GRAY,
                     (px + 18 + k * 20, y + 35), 8, 0 if k < i + 1 else 1)

    # Panel výkladu vľavo hore — text zalamovaný podľa LOGICKÝCH metrík
    lx, ly, lw = 360, 90, 560
    body = c.font(24)
    small = c.font(18)
    lines = [(body, ln, 32) for ln in wrap(body, LESSON_TEXT, lw - 60)]
    lines.append((body, "", 16))
    lines += [(small, ln, 24) for ln in wrap(small, LESSON_SMALL, lw - 60)]
    lh = 46 + sum(step for _, _, step in lines) + 24
    c.overlay((lx, ly, lw, lh), (*COLOR_PANEL, 235))
    c.rect(COLOR_GOLD, (lx, ly, lw, lh), width=2, border_radius=14)
    cnt = small.render("Krok 3/17", True, COLOR_GRAY)
    c.blit(cnt, (lx + 20, ly + 14))
    ty = ly + 46
    for font, line, step in lines:
        if line:
            c.blit(font.render(line, True, COLOR_WHITE), (lx + 30, ty))
        ty += step

    # Rečová bublina pri PC1
    b = c.font(28).render("Svietim zeleného!", True, COLOR_YELLOW)
    bw, bh = b.get_width() + 32, b.get_height() + 32
    bx, byb = LOGICAL_W - 520 - bw // 2, 380 - bh
    c.overlay((bx, byb, bw, bh), (20, 12, 5, 220))
    c.rect(COLOR_YELLOW, (bx, byb, bw, bh), width=2, border_radius=12)
    c.polygon(COLOR_YELLOW, [(bx + bw, byb + bh // 2 - 12),
                             (bx + bw, byb + bh // 2 + 12),
                             (bx + bw + 24, byb + bh // 2)])
    c.blit(b, b.get_rect(centerx=bx + bw // 2, top=byb + 16))

    if flags.get("overlay"):
        c.overlay((0, 0, LOGICAL_W, l_h), (0, 0, 0, 150))

    if flags.get("grid"):
        c.rect((0, 255, 255), (0, 0, LOGICAL_W, l_h), width=2)
        for x in range(0, LOGICAL_W, 240):
            c.line((0, 120, 120), (x, 0), (x, l_h))
        for y in range(0, l_h, 120):
            c.line((0, 120, 120), (0, y), (LOGICAL_W, y))

    hdr = c.font(18).render(title, True, COLOR_WHITE)
    c.overlay((10, l_h - 34, hdr.get_width() + 16, 28), (0, 0, 0, 170))
    c.blit(hdr, (18, l_h - 30))


# ======================================================================
# Techniky
# ======================================================================

class Renderer:
    """Vykreslí jednu snímku zvolenou technikou na `display`."""

    def __init__(self, technique: str, display, vp: Viewport, cache_overlays=True,
                 layer_cache: bool = False):
        import pygame
        self.layer_cache = layer_cache and technique == "hybrid"
        self._layer = None
        self._layer_key = None
        self.technique = technique
        self.display = display
        self.vp = vp
        bg_path = os.path.join("assets", "graphics", "table.jpg")
        if technique == "hybrid":
            self.canvas = Canvas(display, vp.scale, vp.ox, vp.oy)
            self.bg = Canvas.background(self.canvas, bg_path, display.get_size())
        elif technique == "a1":
            self.logical = pygame.Surface((LOGICAL_W, vp.l_h)).convert()
            self.canvas = Canvas(self.logical, 1.0)
            self.bg = Canvas.background(self.canvas, bg_path, (LOGICAL_W, vp.l_h))
        else:  # scaled — display JE logické plátno (pygame.SCALED)
            self.canvas = Canvas(display, 1.0)
            self.bg = Canvas.background(self.canvas, bg_path, (LOGICAL_W, vp.l_h))
        self.canvas.cache_overlays = cache_overlays

    def mouse_logical(self, phys_pos):
        if self.technique == "scaled":
            return phys_pos           # pygame.SCALED prepočíta myš samo
        return self.vp.to_logical(phys_pos)

    def render(self, mouse_phys, flags):
        import pygame
        title = {"a1": "A1 (smoothscale CPU)", "scaled": "A1-GPU (pygame.SCALED)",
                 "hybrid": "HYBRID (Canvas, natívne)"}[self.technique]
        title += f"  |  {self.vp.describe()}"
        ml = self.mouse_logical(mouse_phys)
        if self.technique == "hybrid" and self.layer_cache:
            # Statická vrstva sa prekreslí len pri zmene (tu: pri zmene
            # prepínačov), inak sa len raz blitne celá a navrch sa kreslia
            # tlačidlá s hoverom.
            key = tuple(sorted(flags.items()))
            if self._layer is None or key != self._layer_key:
                self._layer = pygame.Surface(self.display.get_size()).convert()
                self._layer.blit(self.bg, (0, 0))
                self.canvas.target = self._layer
                draw_scene(self.canvas, self.vp.l_h, ml, flags,
                           title + "  [cache vrstvy]", part="static")
                self.canvas.target = self.display
                self._layer_key = key
            self.display.blit(self._layer, (0, 0))
            draw_scene(self.canvas, self.vp.l_h, ml, flags, title,
                       part="dynamic")
        elif self.technique == "hybrid":
            # Pozadie cez celé okno vrátane pásiem (rozhodnutie §8 bod 5)
            self.display.blit(self.bg, (0, 0))
            draw_scene(self.canvas, self.vp.l_h, ml, flags, title)
        elif self.technique == "a1":
            self.logical.blit(self.bg, (0, 0))
            draw_scene(self.canvas, self.vp.l_h, ml, flags, title)
            self.display.fill((0, 0, 0))
            pygame.transform.smoothscale(
                self.logical, (self.vp.phys_w, self.vp.phys_h),
                self.display.subsurface(pygame.Rect(
                    self.vp.ox, self.vp.oy, self.vp.phys_w, self.vp.phys_h)))
        else:
            self.display.blit(self.bg, (0, 0))
            draw_scene(self.canvas, self.vp.l_h, ml, flags, title)


# ======================================================================
# Režimy behu
# ======================================================================

def parse_resolution(text):
    w, h = text.lower().replace("×", "x").split("x")
    return int(w), int(h)


def run_live(args):
    import pygame
    pygame.init()
    if args.resolution:
        width, height = parse_resolution(args.resolution)
    else:
        width, height = pygame.display.get_desktop_sizes()[0]
    windowed = args.windowed
    technique = args.technique
    flags = {"overlay": False, "grid": False}
    use_extra = not args.no_extra_height
    show_ft = True
    zoom = False
    layer = False
    frame_times: list[float] = []

    def make_display():
        nonlocal vp, renderer, display, technique
        vp = Viewport(width, height, use_extra)
        if technique == "scaled":
            mode_flags = pygame.SCALED | (0 if windowed else pygame.FULLSCREEN)
            try:
                display = pygame.display.set_mode((LOGICAL_W, vp.l_h), mode_flags)
            except pygame.error as exc:
                # SCALED potrebuje GPU renderer — bez neho ostaň pri hybride
                print(f"pygame.SCALED nie je dostupné ({exc}), prepínam na hybrid")
                technique = "hybrid"
        if technique != "scaled":
            if not windowed:
                os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
            display = pygame.display.set_mode(
                (width, height), 0 if windowed else pygame.NOFRAME)
        pygame.display.set_caption("Chuj — testbed rozlíšení")
        renderer = Renderer(technique, display, vp, layer_cache=layer)
        frame_times.clear()

    vp = renderer = display = None
    make_display()
    clock = pygame.time.Clock()
    ft_font = pygame.font.SysFont("consolas,dejavusansmono", 18)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                key = event.key
                if key == pygame.K_ESCAPE:
                    return
                if key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    technique = {pygame.K_1: "a1", pygame.K_2: "scaled",
                                 pygame.K_3: "hybrid"}[key]
                    make_display()
                elif key == pygame.K_h:
                    use_extra = not use_extra
                    make_display()
                elif key == pygame.K_c:
                    layer = not layer
                    renderer = Renderer(technique, display, vp, layer_cache=layer)
                elif key == pygame.K_g:
                    flags["grid"] = not flags["grid"]
                elif key == pygame.K_o:
                    flags["overlay"] = not flags["overlay"]
                elif key == pygame.K_f:
                    show_ft = not show_ft
                elif key == pygame.K_z:
                    zoom = not zoom
                elif key == pygame.K_s:
                    name = f"testbed_{technique}_{width}x{height}.png"
                    pygame.image.save(display, name)
                    print(f"uložené {name}")

        t0 = time.perf_counter()
        renderer.render(pygame.mouse.get_pos(), flags)
        dt = (time.perf_counter() - t0) * 1000
        frame_times.append(dt)
        del frame_times[:-120]

        if zoom and technique != "scaled":
            mx, my = pygame.mouse.get_pos()
            src = pygame.Rect(mx - 120, my - 70, 240, 140).clip(display.get_rect())
            if src.width and src.height:
                piece = display.subsurface(src).copy()
                big = pygame.transform.scale(piece, (src.width * 2, src.height * 2))
                display.blit(big, (display.get_width() - big.get_width() - 10, 10))
                pygame.draw.rect(display, (0, 255, 255),
                                 (display.get_width() - big.get_width() - 10, 10,
                                  big.get_width(), big.get_height()), 2)

        if show_ft and frame_times:
            avg = statistics.mean(frame_times)
            p99 = sorted(frame_times)[int(len(frame_times) * 0.99) - 1]
            txt = (f"{technique}  kreslenie {avg:5.1f} ms (p99 {p99:5.1f})  "
                   f"FPS {clock.get_fps():4.0f}   [1/2/3 C H G O F Z S Esc]")
            surf = ft_font.render(txt, True, (255, 255, 0), (0, 0, 0))
            display.blit(surf, (8, 8))

        pygame.display.flip()
        clock.tick(0 if args.unlimited else 60)


def run_offscreen(args):
    import pygame
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    out = os.path.abspath(args.offscreen)
    os.makedirs(out, exist_ok=True)
    resolutions = ([parse_resolution(r) for r in args.only.split(",")]
                   if args.only else OFFSCREEN_RESOLUTIONS)
    rows = []
    flags = {"overlay": False, "grid": False}
    for width, height in resolutions:
        display = pygame.display.set_mode((width, height))
        vp = Viewport(width, height, not args.no_extra_height)
        shots = {}
        for technique, cached, layer in (("a1", True, False), ("a1", False, False),
                                         ("hybrid", True, False), ("hybrid", False, False),
                                         ("hybrid", True, True)):
            if True:
                renderer = Renderer(technique, display, vp, cache_overlays=cached,
                                    layer_cache=layer)
                renderer.render((0, 0), flags)          # zahriatie cache
                times = []
                for _ in range(args.frames):
                    t0 = time.perf_counter()
                    renderer.render((0, 0), flags)
                    times.append((time.perf_counter() - t0) * 1000)
                # Druhé meranie s overlayom cez celú obrazovku (menu, pravidlá)
                ov_times = []
                for _ in range(args.frames):
                    t0 = time.perf_counter()
                    renderer.render((0, 0), {"overlay": True, "grid": False})
                    ov_times.append((time.perf_counter() - t0) * 1000)
                rows.append({
                    "rozlisenie": f"{width}x{height}",
                    "technika": technique + ("+cache_vrstvy" if layer else ""),
                    "overlaye_cachovane": "ano" if cached else "nie",
                    "mierka": f"{vp.scale:.3f}", "L_h": vp.l_h,
                    "snimka_ms_median": f"{statistics.median(times):.1f}",
                    "snimka_ms_max": f"{max(times):.1f}",
                    "s_overlayom_ms_median": f"{statistics.median(ov_times):.1f}",
                })
                if cached and not layer:
                    renderer.render((0, 0), flags)
                    path = os.path.join(out, f"{width}x{height}_{technique}.png")
                    pygame.image.save(display, path)
                    shots[technique] = display.copy()
        _save_crops(out, width, height, vp, shots)
        print(f"{width}x{height}: hotovo  ({vp.describe()})", file=sys.stderr)

    with open(os.path.join(out, "timings.csv"), "w", newline="",
              encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print("  ".join(f"{k}={v}" for k, v in r.items()))


def _save_crops(out, width, height, vp, shots):
    """Výrezy 1:1 (fyzické pixely) tej istej logickej oblasti z oboch
    techník pod sebou: text panelu výkladu a roh karty v ruke."""
    import pygame
    regions = {
        "text": (360, 90, 560, 230),               # panel výkladu
        "karta": (400, 0, 300, 180),               # roh prvých kariet ruky
        "kolo": (LOGICAL_W - 370, 0, 350, 150),    # panel KOLO (malé písmo)
    }
    for name, (x, y, w, h) in regions.items():
        if name in ("karta", "kolo"):
            y = vp.l_h - (220 if name == "karta" else 280) - 10
        canvas = Canvas(None, vp.scale, vp.ox, vp.oy)
        prect = canvas.prect((x, y, w, h)).clip(pygame.Rect(0, 0, width, height))
        pieces = [shots[t].subsurface(prect).copy() for t in ("a1", "hybrid")]
        font = pygame.font.SysFont("dejavusans,arial", 16)
        labels = [font.render(t, True, (255, 255, 0), (0, 0, 0))
                  for t in ("A1 (zväčšený bitmap)", "HYBRID (natívne)")]
        sheet = pygame.Surface((prect.width,
                                2 * prect.height + 2 * 22 + 6))
        sheet.fill((40, 40, 40))
        yy = 0
        for lab, piece in zip(labels, pieces):
            sheet.blit(lab, (4, yy + 2))
            sheet.blit(piece, (0, yy + 22))
            yy += 22 + prect.height + 6
        pygame.image.save(sheet, os.path.join(
            out, f"crop_{width}x{height}_{name}.png"))


def main():
    parser = argparse.ArgumentParser(description="Testbed techník rozlíšenia.")
    parser.add_argument("--resolution", default=None, help="napr. 1366x768")
    parser.add_argument("--windowed", action="store_true", help="okno s rámom")
    parser.add_argument("--technique", default="hybrid",
                        choices=("a1", "scaled", "hybrid"))
    parser.add_argument("--no-extra-height", action="store_true",
                        help="nevyužiť extra výšku pri 16:10 (vždy 1920x1080)")
    parser.add_argument("--unlimited", action="store_true",
                        help="bez limitu 60 FPS (na meranie)")
    parser.add_argument("--offscreen", default=None,
                        help="headless: priečinok na PNG a timings.csv")
    parser.add_argument("--only", default=None,
                        help="headless: len tieto rozlíšenia, napr. 3840x2160,1366x768")
    parser.add_argument("--frames", type=int, default=20,
                        help="headless: počet meraných snímok")
    args = parser.parse_args()

    os.chdir(ROOT)
    if args.offscreen:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    else:
        # DPI awareness ako v main.py — MUSÍ byť pred prvým dotykom displeja
        # (aj pred importom gui.canvas), inak Windows pri 125–150 % podsunie
        # zmenšené "virtuálne" rozlíšenie.
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    _load_canvas()
    if args.offscreen:
        run_offscreen(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()
