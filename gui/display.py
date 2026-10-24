# gui/display.py
#
# Okno hry, logický priestor a prepočet myši. Toto je JEDINÉ miesto, ktoré
# volá pygame.display.set_mode() a flip(). Rework rozlíšení, krok 2:
# claude/11_RESOLUTION_REWORK_ANALYSIS.md §3.3 a §5.
#
# Logický priestor:
#   Hra kreslí a hit-testuje v logických súradniciach. Šírka je vždy 1920,
#   výška L_h = 1080…1200 podľa pomeru strán okna (16:10 využije extra
#   výšku). Širšie okno (21:9) dostane pásma po bokoch, užšie než 16:10
#   pásma hore a dole. Mierka s = fyzické px / logické px.
#
# Kreslenie:
#   Každá obrazovka kreslí cez canvas() — Canvas (gui/canvas.py) nad
#   FYZICKÝM oknom v správnej mierke a s posunom pásiem. Text a karty sa tak
#   vykresľujú priamo v cieľovom rozlíšení (ostré aj pri 4K). present() je
#   len flip(). Dočasnú "A1" sieť (logický povrch preškálovaný do okna)
#   odstránil krok 8 — žiadna obrazovka ju už nepoužívala.
#
# Vstup:
#   get_events() a mouse_pos() prepočítajú pozície myši na logické
#   súradnice. Pri zhode okna s logickým priestorom sú to presne pôvodné
#   hodnoty.
#
# Výber rozlíšenia pri štarte (od najvyššej priority):
#   1. príkazový riadok:  --resolution 1366x768 --windowed | --borderless
#                         --safe   (1280x720 v okne, ignoruje všetko ostatné)
#   2. premenná prostredia CHUJ_RESOLUTION=1366x768 (+ CHUJ_WINDOWED=1)
#      — používajú headless testy a tools/screenshot_gallery.py
#   3. settings.json, kľúč "display" (Nastavenia → Zobrazenie, krok 7)
#   4. automaticky: natívne rozlíšenie monitora, bezrámové okno
#
# Modul zámerne NEimportuje config.py — config si odtiaľto berie
# LOGICAL_W, takže opačný import by bol cyklický.

import json
import os
import sys
from dataclasses import dataclass

import pygame

LOGICAL_W = 1920
L_H_MIN = 1080
L_H_MAX = 1200

SAFE_RESOLUTION = (1280, 720)
WINDOW_CAPTION = "Chuj"
ICON_PATH = os.path.join("assets", "graphics", "chuj.png")

_SETTINGS_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "settings.json"
)


# ----------------------------------------------------------------------
# Režim a viewport
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class DisplayMode:
    width: int
    height: int
    windowed: bool        # False = bezrámové okno cez celú obrazovku
    source: str           # odkiaľ prišlo: "cli" | "env" | "settings" | "auto" | "safe"


class Viewport:
    """Ako sa logický priestor 1920×L_h zmestí do okna W×H."""

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        ideal = LOGICAL_W * height / width
        self.l_h = int(round(min(L_H_MAX, max(L_H_MIN, ideal))))
        self.scale = min(width / LOGICAL_W, height / self.l_h)
        self.phys_w = round(LOGICAL_W * self.scale)
        self.phys_h = round(self.l_h * self.scale)
        self.ox = (width - self.phys_w) // 2
        self.oy = (height - self.phys_h) // 2

    @property
    def is_identity(self) -> bool:
        """Okno = logický priestor 1:1 (bez mierky a pásiem)."""
        return (self.width, self.height) == (LOGICAL_W, self.l_h)

    def to_logical(self, pos) -> tuple[int, int]:
        if self.is_identity:
            return pos
        x, y = pos
        return (int((x - self.ox) / self.scale),
                int((y - self.oy) / self.scale))

    def __repr__(self) -> str:
        return (f"Viewport({self.width}x{self.height}, s={self.scale:.3f}, "
                f"logicky 1920x{self.l_h}, posun {self.ox},{self.oy})")


def parse_resolution(text: str) -> tuple[int, int]:
    w, h = text.lower().replace("×", "x").split("x")
    return int(w), int(h)


def _cli_mode(argv) -> DisplayMode | None:
    """Vlastné, tolerantné čítanie argumentov — ostatné argumenty (napr.
    --seed testera) nechávame bez povšimnutia."""
    args = list(argv)
    if "--safe" in args:
        return DisplayMode(*SAFE_RESOLUTION, windowed=True, source="safe")
    resolution = None
    for i, arg in enumerate(args):
        if arg == "--resolution" and i + 1 < len(args):
            resolution = args[i + 1]
        elif arg.startswith("--resolution="):
            resolution = arg.split("=", 1)[1]
    windowed = "--windowed" in args and "--borderless" not in args
    if resolution is None:
        if "--windowed" in args:
            w, h = _desktop_size()
            return DisplayMode(int(w * 0.8), int(h * 0.8), True, "cli")
        return None
    try:
        w, h = parse_resolution(resolution)
    except ValueError:
        print(f"[display] neplatné --resolution {resolution!r}, ignorujem",
              file=sys.stderr)
        return None
    return DisplayMode(w, h, windowed, "cli")


def _env_mode() -> DisplayMode | None:
    value = os.environ.get("CHUJ_RESOLUTION")
    if not value:
        return None
    try:
        w, h = parse_resolution(value)
    except ValueError:
        return None
    windowed = os.environ.get("CHUJ_WINDOWED", "") not in ("", "0")
    return DisplayMode(w, h, windowed, "env")


def _settings_mode() -> DisplayMode | None:
    """settings.json → "display": {"mode": "window"|"borderless",
    "width": …, "height": …}. Neplatné alebo chýbajúce = None (auto)."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f).get("display")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get("mode") != "window":
        return None   # "borderless"/"auto" → natívne rozlíšenie
    try:
        w, h = int(data["width"]), int(data["height"])
    except (KeyError, TypeError, ValueError):
        return None
    dw, dh = _desktop_size()
    if w > dw or h > dh or w < 800 or h < 600:
        return None   # iný monitor — návrat na "Automaticky"
    return DisplayMode(w, h, True, "settings")


def _desktop_size() -> tuple[int, int]:
    # CHUJ_DESKTOP=WxH — len pre headless testy a galériu (dummy ovládač
    # hlási plochu 1024×768, takže by sa neponúkla žiadna veľkosť okna).
    fake = os.environ.get("CHUJ_DESKTOP")
    if fake:
        try:
            return parse_resolution(fake)
        except ValueError:
            pass
    if not pygame.display.get_init():
        pygame.display.init()
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            return sizes[0]
    except (AttributeError, pygame.error):
        pass
    info = pygame.display.Info()
    return info.current_w, info.current_h


_startup_mode: DisplayMode | None = None


def startup_mode() -> DisplayMode:
    """Režim, v ktorom sa okno otvorí pri štarte (vypočíta sa raz)."""
    global _startup_mode
    if _startup_mode is None:
        _startup_mode = (_cli_mode(sys.argv[1:]) or _env_mode()
                         or _settings_mode())
        if _startup_mode is None:
            w, h = _desktop_size()
            _startup_mode = DisplayMode(w, h, False, "auto")
    return _startup_mode


def startup_viewport() -> Viewport:
    mode = startup_mode()
    return Viewport(mode.width, mode.height)


# ----------------------------------------------------------------------
# Okno
# ----------------------------------------------------------------------

_window = None       # povrch okna (fyzický)
_viewport: Viewport | None = None
_canvas = None       # Canvas nad oknom (gui/canvas.py), vytvára sa lenivo
_mode: DisplayMode | None = None   # režim aktuálne otvoreného okna


def open_window(mode: DisplayMode | None = None):
    """Otvorí (alebo znovu otvorí) okno. Vráti povrch okna."""
    global _window, _viewport, _canvas, _mode
    mode = mode or startup_mode()
    _mode = mode
    if not pygame.display.get_init():
        pygame.display.init()
    flags = 0
    if not mode.windowed:
        # Bezrámové okno cez celú obrazovku — rovnako, ako hra pôsobila
        # doteraz, len už bez rámu, ktorý by mohol presahovať plochu.
        os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
        flags = pygame.NOFRAME
    else:
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
        os.environ["SDL_VIDEO_CENTERED"] = "1"
    try:
        icon = pygame.image.load(ICON_PATH)
        pygame.display.set_icon(icon)
    except (FileNotFoundError, pygame.error):
        pass
    _window = pygame.display.set_mode((mode.width, mode.height), flags)
    pygame.display.set_caption(WINDOW_CAPTION)
    _viewport = Viewport(mode.width, mode.height)
    _canvas = None          # nová mierka → nový Canvas aj s cache
    return _window


def apply_mode(mode: DisplayMode):
    """Prepne okno za behu (Nastavenia → Zobrazenie, krok 7 reworku).

    Okno sa vytvorí NANOVO (display.quit/init): pri opätovnom set_mode()
    by Windows nemusel zmeniť rám ani polohu okna (bezrámové na 0,0 →
    okno s rámom by malo titulok mimo plochy). Canvas aj s cache vznikne
    pri ďalšom canvas() znova; obrazovky si ho po prepnutí musia vypýtať
    nanovo (SettingsScreen._rebuild, ostatné sa vytvárajú pri otvorení)."""
    if pygame.display.get_init():
        pygame.display.quit()
    pygame.display.init()
    return open_window(mode)


# Ponuka veľkostí okna (Nastavenia → Zobrazenie). Bežné rozlíšenia podľa
# Steam Hardware Survey; ponúknu sa len tie, ktoré sa s rámom a panelom
# úloh zmestia na plochu KONKRÉTNEHO hráča (window_sizes()).
WINDOW_SIZES = (
    (1366, 768), (1440, 900), (1600, 900), (1680, 1050),
    (1920, 1080), (1920, 1200), (2560, 1080), (2560, 1440),
    (2560, 1600), (2880, 1800), (3440, 1440), (3840, 2160),
)
WINDOW_MARGIN_W = 16      # ľavý + pravý okraj rámu
WINDOW_MARGIN_H = 80      # titulok okna + panel úloh


def desktop_size() -> tuple[int, int]:
    """Natívne rozlíšenie (hlavného) monitora."""
    return _desktop_size()


def window_sizes() -> list[tuple[int, int]]:
    """Veľkosti okna, ktoré sa na tomto monitore zmestia aj s rámom."""
    dw, dh = _desktop_size()
    return [(w, h) for w, h in WINDOW_SIZES
            if w <= dw - WINDOW_MARGIN_W and h <= dh - WINDOW_MARGIN_H]


def fullscreen_mode() -> DisplayMode:
    """Bezrámová celá obrazovka v natívnom rozlíšení."""
    w, h = _desktop_size()
    return DisplayMode(w, h, False, "auto")


def get_surface():
    """Povrch okna. Ak okno ešte neexistuje (napr. headless test,
    samostatný launcher), otvorí ho podľa startup_mode(). Obrazovky naň
    nekreslia priamo — kreslí sa cez canvas()."""
    if _window is None or pygame.display.get_surface() is not _window:
        return open_window()
    return _window


def logical_height() -> int:
    """Logická výška aktuálneho okna (alebo štartovacieho režimu, kým
    okno ešte neexistuje). Používa gui/layout.py."""
    if _viewport is not None:
        return _viewport.l_h
    return startup_viewport().l_h


def current_mode() -> DisplayMode:
    """Režim aktuálne otvoreného okna (Nastavenia → Zobrazenie)."""
    if _mode is None:
        get_surface()
    return _mode


def viewport() -> Viewport:
    if _viewport is None:
        get_surface()
    return _viewport


def canvas():
    """Canvas nad fyzickým oknom (mierka a pásma podľa viewportu). Pri
    novom okne (iné rozlíšenie) vznikne nový — aj s prázdnou cache."""
    global _canvas
    get_surface()
    if _canvas is None:
        from gui.canvas import Canvas   # lenivo: canvas importuje config
        vp = _viewport
        _canvas = Canvas(_window, vp.scale, vp.ox, vp.oy)
    return _canvas


def present():
    """Zobrazí nakreslenú snímku."""
    pygame.display.flip()


_MOUSE_EVENTS = (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                 pygame.MOUSEMOTION)


def get_events() -> list:
    """pygame.event.get() s pozíciami myši v logických súradniciach."""
    events = pygame.event.get()
    vp = _viewport
    if vp is None or vp.is_identity:
        return events
    out = []
    for event in events:
        if event.type in _MOUSE_EVENTS and hasattr(event, "pos"):
            attrs = dict(event.__dict__)
            attrs["pos"] = vp.to_logical(event.pos)
            if "rel" in attrs:
                attrs["rel"] = (int(attrs["rel"][0] / vp.scale),
                                int(attrs["rel"][1] / vp.scale))
            event = pygame.event.Event(event.type, attrs)
        out.append(event)
    return out


def mouse_pos() -> tuple[int, int]:
    """pygame.mouse.get_pos() v logických súradniciach."""
    pos = pygame.mouse.get_pos()
    vp = _viewport
    if vp is None:
        return pos
    return vp.to_logical(pos)
