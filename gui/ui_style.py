# gui/ui_style.py
#
# Spoločný vzhľad obrazoviek mimo hry (grafický rework menu, 2026-10-27):
# hlavné menu, Tutoriál, Nastavenia, Profil, Koniec hry. Elegantné tmavšie
# prevedenie — tmavý drevený stôl s mäkkým svetlom, takmer čierne panely so
# zlatohnedým rámom, tlačidlá v troch úrovniach dôležitosti.
#
# Všetko kreslí cez gui/canvas.py v logických súradniciach. Pomalšie veci
# (osvetlenie pozadia, mäkké žiary) patria do statickej vrstvy obrazovky —
# výsledky osvetlenia sa navyše cachujú podľa veľkosti okna.

import math
import os

import pygame

TABLE_BG_PATH = os.path.join("assets", "graphics", "table.jpg")

# ----------------------------------------------------------------------
# Farby a rozmery
# ----------------------------------------------------------------------

GOLD = (222, 172, 64)
GOLD_SOFT = (150, 112, 58)          # zlatohnedý rám
TEXT = (238, 228, 208)              # krémový text
TEXT_DIM = (150, 132, 108)          # popisky, nápovedy

# Osvetlenie stola: celkové stmavenie (alfa), vinetácia navyše k okrajom a
# teplé svetlo hore v strede (pripočítané RGB). table.jpg (2026-10-27) má
# vinetáciu aj svetlo už v sebe, preto sú hodnoty mierne.
BG_DIM = 40
BG_VIGNETTE = 110
BG_WARM_LIGHT = (34, 20, 8)
CENTER_SHADE_ALPHA = 150

# Tlačidlá — tri úrovne (podľa návrhu "Elegantné a tmavšie"):
#   1 = hlavná akcia obrazovky (Pokračovať, Nová hra, Ponechať…) — zlatohnedá
#   2 = dôležité akcie (Nová hra a Tutoriál v menu, kapitoly…) — stredne hnedá
#   3 = ostatné (Profil, Nastavenia, Koniec, Späť…) — takmer čierna
# Každá úroveň: (výplň RGBA, presvetlenie hornej polovice — alfa, rám, text)
BTN_RADIUS = 10
BTN_TIERS = {
    1: ((112, 78, 36, 240), 34, (222, 172, 64), (255, 240, 214)),
    2: ((70, 47, 24, 236), 18, (150, 112, 58), (244, 232, 210)),
    3: ((27, 19, 12, 230), 9, (98, 76, 46), (232, 222, 202)),
}
BTN_BORDER_HOVER = (240, 196, 92)
BTN_TEXT_HOVER = (252, 210, 116)
BTN_DISABLED = ((22, 15, 9, 170), (70, 56, 38), (96, 84, 68))

# Panely
PANEL_FILL = (17, 11, 7, 226)
PANEL_RADIUS = 12


# ----------------------------------------------------------------------
# Tlačidlá a panely
# ----------------------------------------------------------------------

def draw_button(c, rect, label: str, font, tier: int = 3,
                hover: bool = False, enabled: bool = True,
                shadow: bool = True):
    """Tlačidlo v štýle menu. `tier` 1–3 = dôležitosť (pozri BTN_TIERS)."""
    rect = pygame.Rect(rect)
    if shadow:
        c.overlay(rect.move(0, 4), (0, 0, 0, 110), border_radius=BTN_RADIUS)
    if not enabled:
        fill, border, text_color = BTN_DISABLED
        c.overlay(rect, fill, border_radius=BTN_RADIUS)
        c.rect(border, rect, width=1, border_radius=BTN_RADIUS)
    else:
        fill, highlight, border, text_color = BTN_TIERS[tier]
        c.overlay(rect, fill, border_radius=BTN_RADIUS)
        top = pygame.Rect(rect.x + 2, rect.y + 2, rect.width - 4,
                          rect.height // 2 - 2)
        c.overlay(top, (255, 214, 140, highlight),
                  border_radius=BTN_RADIUS - 2)
        if hover:
            c.overlay(rect, (255, 214, 140, 24), border_radius=BTN_RADIUS)
            border, text_color = BTN_BORDER_HOVER, BTN_TEXT_HOVER
        c.rect(border, rect, width=2, border_radius=BTN_RADIUS)
    if label:
        surf = font.render(label, True, text_color)
        c.blit(surf, surf.get_rect(center=rect.center))


def draw_panel(c, rect, title: str | None = None, font=None,
               title_x: int = 28, title_cy: int = 30, divider_y: int = 52):
    """Tmavý panel so zlatohnedým rámom, voliteľne s nadpisom a čiarou."""
    rect = pygame.Rect(rect)
    c.overlay(rect, PANEL_FILL, border_radius=PANEL_RADIUS)
    # jemné presvetlenie hornej hrany (dojem hĺbky)
    c.overlay((rect.x + 3, rect.y + 3, rect.width - 6, min(40, rect.height // 3)),
              (255, 214, 140, 6), border_radius=PANEL_RADIUS - 3)
    c.rect(GOLD_SOFT, rect, width=2, border_radius=PANEL_RADIUS)
    if title and font is not None:
        label = font.render(title, True, GOLD)
        c.blit(label, label.get_rect(midleft=(rect.left + title_x,
                                              rect.top + title_cy)))
        if divider_y:
            c.line((70, 54, 34), (rect.left + 24, rect.top + divider_y),
                   (rect.right - 24, rect.top + divider_y), width=1)


def draw_screen_title(c, text: str, font, center: tuple[int, int],
                      line_half_w: int = 260, line_gap: int = 44):
    """Nadpis obrazovky: zlatý text s tieňom a pod ním ozdobná linka
    (dve tenké čiary zbiehajúce sa ku kosoštvorcu v strede)."""
    cx, cy = center
    shadow = font.render(text, True, (0, 0, 0))
    title = font.render(text, True, GOLD)
    rect = title.get_rect(center=center)
    c.blit(shadow, (rect.x + 3, rect.y + 3))
    c.blit(title, rect)
    y = cy + line_gap
    c.line(GOLD_SOFT, (cx - line_half_w, y), (cx - 14, y), width=2)
    c.line(GOLD_SOFT, (cx + 14, y), (cx + line_half_w, y), width=2)
    c.polygon(GOLD, [(cx, y - 7), (cx + 8, y), (cx, y + 7), (cx - 8, y)])


def draw_backdrop(c, center_shade: bool = True, extra_dim: int = 0):
    """Pozadie obrazoviek mimo hry: stôl „cover" cez celé okno (aj pásma),
    stmavenie, vinetácia, teplé svetlo hore a voliteľne mäkké stmavenie
    stredu za obsahom. `extra_dim` = ďalšie rovnomerné stmavenie (alfa)
    pre obrazovky s veľa textom."""
    if os.path.exists(TABLE_BG_PATH):
        c.target.blit(c.background(TABLE_BG_PATH, c.target.get_size()), (0, 0))
    else:
        c.fill_window((45, 28, 15))
    apply_lighting(c.target)
    if center_shade:
        apply_center_shade(c.target)
    if extra_dim:
        c.overlay_window((0, 0, 0, extra_dim))


# ----------------------------------------------------------------------
# Osvetlenie — mäkké prechody z malej mriežky zväčšenej cez smoothscale
# (žiadne ostré hrany). Počíta sa cez CELÉ okno (aj pásma pri 21:9),
# stred = stred okna.
# ----------------------------------------------------------------------

_GRID = (64, 36)
# Hotové vrstvy osvetlenia podľa veľkosti okna — obrazovky sa vytvárajú pri
# každom otvorení, osvetlenie sa tak počíta len raz za rozlíšenie.
_LIGHT_CACHE: dict = {}


def scaled_grid(target_size, pixel_fn, alpha: bool = True) -> pygame.Surface:
    gw, gh = _GRID
    small = pygame.Surface((gw, gh), pygame.SRCALPHA if alpha else 0)
    for gy in range(gh):
        v = (gy + 0.5) / gh
        for gx in range(gw):
            small.set_at((gx, gy), pixel_fn((gx + 0.5) / gw, v))
    return pygame.transform.smoothscale(small, target_size)


def apply_lighting(target: pygame.Surface):
    """Celkové stmavenie + vinetácia (tmavšie okraje) + teplé svetlo
    hore v strede."""
    size = target.get_size()
    aspect = size[0] / size[1]

    def shade(u, v):
        dx, dy = (u - 0.5) * aspect / (16 / 9), v - 0.42
        r2 = (dx / 0.62) ** 2 + (dy / 0.75) ** 2
        a = BG_DIM + BG_VIGNETTE * min(1.0, r2) ** 1.6
        return (0, 0, 0, int(min(235, a)))

    def light(u, v):
        dx, dy = (u - 0.5) * aspect / (16 / 9), v - 0.18
        k = math.exp(-((dx / 0.28) ** 2 + (dy / 0.30) ** 2))
        return tuple(int(ch * k) for ch in BG_WARM_LIGHT)

    key = ("light", size)
    if key not in _LIGHT_CACHE:
        _LIGHT_CACHE[key] = (scaled_grid(size, shade),
                             scaled_grid(size, light, alpha=False))
    shade_surf, light_surf = _LIGHT_CACHE[key]
    target.blit(shade_surf, (0, 0))
    target.blit(light_surf, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def apply_center_shade(target: pygame.Surface):
    """Mäkký tmavý pás za obsahom v strede — priehľadnosť klesá doľava
    a doprava podľa Gaussovej krivky, bez zvislých hrán."""
    size = target.get_size()
    aspect = size[0] / size[1]

    def shade(u, v):
        dx = (u - 0.5) * aspect / (16 / 9)
        k = math.exp(-(dx / 0.19) ** 2)
        return (8, 5, 3, int(CENTER_SHADE_ALPHA * k))

    key = ("center", size)
    if key not in _LIGHT_CACHE:
        _LIGHT_CACHE[key] = scaled_grid(size, shade)
    target.blit(_LIGHT_CACHE[key], (0, 0))


def blit_soft_ellipse(c, rect: pygame.Rect, color, strength: int,
                      additive: bool, square: bool = False):
    """Mäkká škvrna (žiara alebo tieň) v logickom obdĺžniku `rect`.
    Počíta sa pri každom volaní — patrí do statickej vrstvy."""
    pr = c.prect(rect)

    def fn(u, v):
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        if square:
            d = max(abs(dx) ** 4, abs(dy) ** 4) ** 0.25
            k = max(0.0, min(1.0, (1.0 - d) / 0.35))
        else:
            k = math.exp(-2.6 * (dx * dx + dy * dy))
        if additive:
            return tuple(int(ch * k * strength / 255) for ch in color)
        return (*color, int(strength * k))

    surf = scaled_grid(pr.size, fn, alpha=not additive)
    c.target.blit(surf, pr.topleft,
                  special_flags=pygame.BLEND_RGB_ADD if additive else 0)
