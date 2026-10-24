# config.py

import pygame
pygame.init()

# ------------------------------------------------------------------
# Obrazovka
# ------------------------------------------------------------------
# Rework rozlíšení (claude/11_RESOLUTION_REWORK_ANALYSIS.md): hra kreslí v
# LOGICKOM priestore, nie vo fyzickom rozlíšení monitora. Šírka je vždy
# SCREEN_WIDTH = 1920. Výška je 1080…1200 podľa pomeru strán okna a môže sa
# zmeniť aj za behu (Nastavenia → Zobrazenie) — preto tu NIE JE konštanta
# SCREEN_HEIGHT, ale gui.display.logical_height(). Okno, mierku a prepočet
# myši rieši gui/display.py, rozloženie hernej obrazovky gui/layout.py.
from gui.display import LOGICAL_W

SCREEN_WIDTH = LOGICAL_W
FPS = 60

# ------------------------------------------------------------------
# Cesty k obrázkom kariet
# ------------------------------------------------------------------
CARDS_SMALL_PATH = "assets/cards-small"
CARDS_MEDIUM_PATH = "assets/cards-medium"
CARDS_LARGE_PATH = "assets/cards-large"
SUIT_ICONS_PATH = "assets/suit-icons"

# ------------------------------------------------------------------
# Veľkosti kariet (šírka x výška)
# ------------------------------------------------------------------
CARD_SIZE_SMALL = (91, 146)
CARD_SIZE_MEDIUM = (181, 293)
CARD_SIZE_LARGE = (363, 585)

# ------------------------------------------------------------------
# Karty
# ------------------------------------------------------------------
SUITS = ["heart", "bell", "leaf", "acorn"]

# Poradie kariet od najvyššej po najnižšiu (iné, ako v Tisíci!)
RANKS = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]

# Bodová hodnota kariet (trestné body)
CARD_POINTS = {
    "heart":  {"ace": 1, "king": 1, "over": 1, "under": 1,
               "ten": 1, "nine": 1, "eight": 1, "seven": 1},
    "bell":   {"ace": 0, "king": 0, "over": 0, "under": 0,
               "ten": 0, "nine": 0, "eight": 0, "seven": 0},
    "leaf":   {"ace": 0, "king": 0, "over": 8, "under": 0,
               "ten": 0, "nine": 0, "eight": 0, "seven": 0},
    "acorn":  {"ace": 0, "king": 0, "over": 4, "under": 0,
               "ten": 0, "nine": 0, "eight": 0, "seven": 0},
}

# Špeciálne karty
LEAF_OVER = ("leaf", "over")        # zelený horník — 8b
ACORN_OVER = ("acorn", "over")      # žaluďový horník — 4b

# Hodnoty horníkov pri vysvietení (2x násobok)
ILLUMINATED_POINTS = {
    "leaf":  {"over": 16},          # zelený horník vysvietený
    "acorn": {"over": 8},           # žaluďový horník vysvietený
}

# Bonus za zobrazenie všetkých trestných kariet v kole
SHOOT_MOON_BONUS = -10              # -10b za všetky karty v kole

# Záväzky
DECLARATION_ALL_BONUS = -20         # zoberiem všetky štichy
DECLARATION_ALL_PENALTY = 20        # ak nesplním, +20b, ostatní 0b
DECLARATION_NONE_BONUS = -10        # nechytím ani jeden štich
DECLARATION_FAIL_PENALTY = 10       # dostanem +10b ak záväzok nesplním

# Séria bez trestných bodov
NO_PENALTY_STREAK = 5               # počet kôl bez trestných bodov
NO_PENALTY_BONUS = -10              # bonus za sériu

# ------------------------------------------------------------------
# Herné pravidlá
# ------------------------------------------------------------------
NUM_PLAYERS = 4
CARDS_PER_PLAYER = 8
TRICKS_PER_ROUND = 8
WINNING_SCORE = 100                 # prehráva hráč, ktorý prekročí 100b
RESET_SCORE = 90                    # ak má hráč presne 100b → reset na 90
HIGH_SCORE_THRESHOLD = 90           # nad 90b sa nepočítajú horníci

# Rozdávanie: 4-4 + 4-4
DEAL_SEQUENCE = [4, 4]

# ------------------------------------------------------------------
# Poradie hráčov (proti smeru hodinových ručičiek)
# ------------------------------------------------------------------
# 0 = Hráč (dole)
# 1 = Počítač 1 (vľavo)
# 2 = Počítač 2 (hore)
# 3 = Počítač 3 (vpravo)
PLAYER_ORDER = [0, 1, 2, 3]        # proti smeru hodinových ručičiek

# ------------------------------------------------------------------
# Debug
# ------------------------------------------------------------------
DEBUG_MODE = False

# ------------------------------------------------------------------
# GUI — Farby
# ------------------------------------------------------------------
COLOR_BG = (45, 28, 15)
COLOR_BG_DARK = (30, 18, 8)
COLOR_WHITE = (255, 248, 235)
COLOR_BLACK = (15, 10, 5)
COLOR_YELLOW = (255, 220, 100)
COLOR_RED = (200, 60, 40)
COLOR_GREEN = (80, 180, 80)
COLOR_GRAY = (120, 100, 80)
COLOR_DARK_GRAY = (60, 45, 30)
COLOR_GOLD = (212, 160, 40)
COLOR_TRUMP = (0, 190, 170)
COLOR_PANEL_BG = (25, 15, 8)

# Špeciálne farby pre Chuj
COLOR_PENALTY = (200, 60, 40)       # trestné body — červená
COLOR_BONUS = (80, 180, 80)         # bonusové body — zelená
COLOR_ILLUMINATED = (255, 200, 0)   # vysvietený horník — zlatá

# ------------------------------------------------------------------
# GUI — Rýchlosť animácií (nastaviteľná v SettingsScreen)
# ------------------------------------------------------------------
# Násobok aplikovaný na základnú card_speed TrickAnimation a
# CardThrowAnimation (nie DealAnimation — tá zostáva na pevnej rýchlosti).
ANIMATION_SPEED_MIN = 0.5
ANIMATION_SPEED_MAX = 2.0
ANIMATION_SPEED_DEFAULT = 1.5

# ------------------------------------------------------------------
# GUI — Fonty
# ------------------------------------------------------------------
FONT_SIZE_SMALL = 18
FONT_SIZE_MEDIUM = 24
FONT_SIZE_LARGE = 32
FONT_SIZE_XLARGE = 48

# ------------------------------------------------------------------
# GUI — rozloženie
# ------------------------------------------------------------------
# Pozície rúk, štichu, tlačidiel a panelov hernej obrazovky počíta
# gui/layout.py podľa logickej výšky okna. Pôvodné pevné konštanty
# (HAND_CONFIGS, TRICK_START_POSITIONS, BUTTON_*_Y, TIP_PANEL_*,
# ROUND_STATUS_* …) odstránil krok 8 reworku rozlíšení. Logická šírka je
# stála, takže vodorovný stred stola ostáva konštantou.
TABLE_CENTER_X = SCREEN_WIDTH // 2

# ------------------------------------------------------------------
# GUI — Tlačidlá
# ------------------------------------------------------------------
BUTTON_RADIUS = 8

COLOR_BUTTON_PRIMARY = (180, 110, 45)
COLOR_BUTTON_SECONDARY = (60, 45, 30)


# ------------------------------------------------------------------
# Chujogram
# ------------------------------------------------------------------
BULLET_RADIUS = 8
BULLET_COLOR = COLOR_GOLD

# ------------------------------------------------------------------
# Obrázok zadnej strany karty
# ------------------------------------------------------------------
CARD_BACK_IMAGE = "card-back.png"

# ------------------------------------------------------------------
# HELPER METÓDA PRE FONT
# ------------------------------------------------------------------
_FONT_CACHE: dict[int, pygame.font.Font] = {}


def get_font(size: int) -> pygame.font.Font:
    """Vráti font s podporou Unicode znakov (♥ ● ♠ ♣).

    Fonty sa cachujú — SysFont pri každom volaní hľadá a otvára súbor
    fontu a niektoré miesta volajú get_font() každú snímku (napr.
    menovky hráčov). Objekt fontu sa nikde nemení (set_bold a pod.),
    takže zdieľanie je bezpečné a vykreslenie je identické."""
    font = _FONT_CACHE.get(size)
    if font is None:
        font = None
        for font_name in ("tahoma", "arial"):
            try:
                font = pygame.font.SysFont(font_name, size)
                break
            except Exception:
                continue
        if font is None:
            # Pôvodný fallback volal get_font() rekurzívne (nekonečne).
            font = pygame.font.Font(None, size)
        _FONT_CACHE[size] = font
    return font