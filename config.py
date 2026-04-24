# config.py

import pygame
pygame.init()

# ------------------------------------------------------------------
# Obrazovka
# ------------------------------------------------------------------
_info = pygame.display.Info()
SCREEN_WIDTH = _info.current_w
SCREEN_HEIGHT = _info.current_h
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
DECLARATION_NONE_BONUS = -10        # nechytím ani jeden trestný bod
DECLARATION_FAIL_PENALTY = 10       # ostatní dostanú -10b ak záväzok nesplní

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
# GUI — Fonty
# ------------------------------------------------------------------
FONT_SIZE_SMALL = 18
FONT_SIZE_MEDIUM = 24
FONT_SIZE_LARGE = 32
FONT_SIZE_XLARGE = 48

# ------------------------------------------------------------------
# GUI — Pozície (4 hráči)
# ------------------------------------------------------------------
TABLE_CENTER_X = SCREEN_WIDTH // 2
TABLE_CENTER_Y = SCREEN_HEIGHT // 2

CARD_OVERLAP = 30
CARD_FAN_OFFSET = 60

# Ruky hráčov
# Hráč 0 — dole (horizontálne)
HUMAN_HAND_X = 200
HUMAN_HAND_Y = 860

# Počítač 1 — vľavo (vertikálne)
PC1_HAND_X = 30
PC1_HAND_Y = 150

# Počítač 2 — hore (horizontálne, otočené)
PC2_HAND_X = 200
PC2_HAND_Y = 30

# Počítač 3 — vpravo (vertikálne, otočené)
PC3_HAND_X = SCREEN_WIDTH - 30 - CARD_SIZE_MEDIUM[1]
PC3_HAND_Y = 150

# Pozície štichov na stole
TRICK_POS = {
    0: (TABLE_CENTER_X, TABLE_CENTER_Y + 120),      # hráč — dole
    1: (TABLE_CENTER_X + 150, TABLE_CENTER_Y),       # PC1 — vpravo
    2: (TABLE_CENTER_X, TABLE_CENTER_Y - 120),       # PC2 — hore
    3: (TABLE_CENTER_X - 150, TABLE_CENTER_Y),       # PC3 — vľavo
}

# ------------------------------------------------------------------
# Pozície rúk hráčov — použité v card_renderer, deal_animation, screen
# ------------------------------------------------------------------
HAND_CONFIGS = {
    0: {"direction": "horizontal", "x": 400,  "y": 860,  "offset": 100},  # Hráč — dole
    1: {"direction": "vertical",   "x": 1600, "y": 150,  "offset": 65},   # PC1 — vpravo (bolo vľavo)
    2: {"direction": "horizontal", "x": 400,  "y": -50,  "offset": 100},  # PC2 — hore
    3: {"direction": "vertical",   "x": 30,   "y": 150,  "offset": 65},   # PC3 — vľavo (bolo vpravo)
}

# Štartové pozície štichov na stole
TRICK_START_POSITIONS = {
    0: (TABLE_CENTER_X, TABLE_CENTER_Y + 120),
    1: (TABLE_CENTER_X + 150, TABLE_CENTER_Y),
    2: (TABLE_CENTER_X, TABLE_CENTER_Y - 120),
    3: (TABLE_CENTER_X - 150, TABLE_CENTER_Y),
}

# ------------------------------------------------------------------
# GUI — Tlačidlá
# ------------------------------------------------------------------
BUTTON_WIDTH = 180
BUTTON_HEIGHT = 50
BUTTON_RADIUS = 8
BUTTON_Y = TABLE_CENTER_Y + CARD_SIZE_MEDIUM[1] // 2 + 18

COLOR_BUTTON_PRIMARY = (180, 110, 45)
COLOR_BUTTON_SECONDARY = (60, 45, 30)

# Tlačidlá vpravo dole
BUTTON_SORT_WIDTH = 200
BUTTON_SORT_HEIGHT = 50
BUTTON_SORT_X = SCREEN_WIDTH - 600
BUTTON_SORT_Y = SCREEN_HEIGHT - 200

BUTTON_INFO_WIDTH = 200
BUTTON_INFO_HEIGHT = 50
BUTTON_INFO_X = SCREEN_WIDTH - 600
BUTTON_INFO_Y = SCREEN_HEIGHT - 145

BUTTON_MENU_WIDTH = 200
BUTTON_MENU_HEIGHT = 50
BUTTON_MENU_X = SCREEN_WIDTH - 600
BUTTON_MENU_Y = SCREEN_HEIGHT - 90

# Round status panel — pravý horný roh
ROUND_STATUS_W = 300
ROUND_STATUS_H = 220
ROUND_STATUS_X = SCREEN_WIDTH - 320
ROUND_STATUS_Y = SCREEN_HEIGHT - ROUND_STATUS_H - 20    # vpravo dole


# ------------------------------------------------------------------
# Chujogram
# ------------------------------------------------------------------
BULLET_RADIUS = 8
BULLET_COLOR = (200, 60, 40)
CHUJOGRAM_X = 20
CHUJOGRAM_Y = 20

# ------------------------------------------------------------------
# Obrázok zadnej strany karty
# ------------------------------------------------------------------
CARD_BACK_IMAGE = "card-back.png"