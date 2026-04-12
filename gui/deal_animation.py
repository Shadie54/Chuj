# gui/deal_animation.py

import pygame
from config import (
    SCREEN_HEIGHT,
    TABLE_CENTER_X, TABLE_CENTER_Y,
    COLOR_WHITE,
    FONT_SIZE_MEDIUM, CARD_SIZE_MEDIUM
)


class DealAnimation:
    def __init__(self, screen: pygame.Surface, card_renderer):
        self.screen = screen
        self.card_renderer = card_renderer
        self.font = pygame.font.SysFont(None, FONT_SIZE_MEDIUM)

        # Cieľové pozície pre každého hráča
        # {player_index: [(x, y), (x, y), ...]} — pozícia každej karty
        self.target_positions = {
            0: [],  # človek — dole
            1: [],  # AI ľavý
            2: [],  # AI stredný
            3: [],  # AI pravý
        }
        self.talon_positions = []

        # Animačný stav
        self.cards_in_flight: list[dict] = []   # karty ktoré letia
        self.dealt_cards: list[dict] = []        # karty ktoré už doleteli
        self.deal_queue: list[dict] = []         # fronta kariet na rozdanie
        self.current_deal_index: int = 0
        self.deal_timer: int = 0
        self.deal_interval: int = 80            # ms medzi kartami
        self.card_speed: float = 25.0           # px za frame
        self.done: bool = False
        self.skipped: bool = False

        self._build_target_positions()

    # ------------------------------------------------------------------
    # Inicializácia pozícií
    # ------------------------------------------------------------------

    def _build_target_positions(self):
        from config import HAND_CONFIGS

        for player_idx, config in HAND_CONFIGS.items():
            positions = []
            for i in range(8):
                if config["direction"] == "horizontal":
                    x = config["x"] + i * config["offset"]
                    y = config["y"]
                else:
                    x = config["x"]
                    y = config["y"] + i * config["offset"]
                positions.append((x, y))

            # PC2 — obráť poradie pozícií
            if player_idx == 2:
                positions = list(reversed(positions))

            self.target_positions[player_idx] = positions

    def _build_deal_queue(self, first_player_index: int):
        """
        Zostaví frontu kariet podľa poradia rozdávania.
        4-4-4-4 + 4-4-4-4
        Začína hráčom first_player_index.
        """
        self.deal_queue = []
        card_counters = {0: 0, 1: 0, 2: 0, 3: 0}

        def add_cards(player_idx: int, count: int):
            for _ in range(count):
                idx = card_counters[player_idx]
                self.deal_queue.append({
                    "target_player": player_idx,
                    "target_pos": self.target_positions[player_idx][idx],
                    "is_talon": False
                })
                card_counters[player_idx] += 1

        # Poradie hráčov od first_player
        order = [(first_player_index + i) % 4 for i in range(4)]

        # 4-4-4-4 + 4-4-4-4
        for batch in [4, 4]:
            for p in order:
                add_cards(p, batch)

    # ------------------------------------------------------------------
    # Spustenie animácie
    # ------------------------------------------------------------------

    def start(self, obligation_index: int):
        """Spustí animáciu rozdávania."""
        self._build_deal_queue(obligation_index)
        self.current_deal_index = 0
        self.cards_in_flight = []
        self.dealt_cards = []
        self.deal_timer = pygame.time.get_ticks()
        self.done = False
        self.skipped = False

    # ------------------------------------------------------------------
    # Hlavná aktualizácia
    # ------------------------------------------------------------------

    def update(self):
        """Aktualizuje stav animácie."""
        if self.done or self.skipped:
            return

        now = pygame.time.get_ticks()

        # Pridaj novú kartu do letu
        if (self.current_deal_index < len(self.deal_queue)
                and now >= self.deal_timer):
            card_data = self.deal_queue[self.current_deal_index]
            self.cards_in_flight.append({
                "x": float(TABLE_CENTER_X - CARD_SIZE_MEDIUM[0] // 2),
                "y": float(TABLE_CENTER_Y - CARD_SIZE_MEDIUM[1] // 2),
                "target_x": float(card_data["target_pos"][0]),
                "target_y": float(card_data["target_pos"][1]),
                "target_player": card_data["target_player"],
                "is_talon": card_data["is_talon"],
                "arrived": False
            })
            self.current_deal_index += 1
            self.deal_timer = now + self.deal_interval

        # Pohni kartami v lete
        for card in self.cards_in_flight:
            if card["arrived"]:
                continue

            dx = card["target_x"] - card["x"]
            dy = card["target_y"] - card["y"]
            dist = (dx ** 2 + dy ** 2) ** 0.5

            if dist <= self.card_speed:
                card["x"] = card["target_x"]
                card["y"] = card["target_y"]
                card["arrived"] = True
            else:
                card["x"] += dx / dist * self.card_speed
                card["y"] += dy / dist * self.card_speed

        # Presuň doletené karty do dealt_cards
        arrived = [c for c in self.cards_in_flight if c["arrived"]]
        for card in arrived:
            self.cards_in_flight.remove(card)
            self.dealt_cards.append(card)

        # Skontroluj či je animácia hotová
        if (self.current_deal_index >= len(self.deal_queue)
                and not self.cards_in_flight):
            self.done = True

    def handle_event(self, event: pygame.event.Event):
        """Spracuje udalosti — medzerník preskočí animáciu."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.skipped = True
                self.done = True
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.skipped = True
                self.done = True

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, table_bg: pygame.Surface | None):
        """Nakreslí stav animácie."""
        # Pozadie
        if table_bg:
            self.screen.blit(table_bg, (0, 0))
        else:
            self.screen.fill((45, 28, 15))

        # Doletené karty
        for card in self.dealt_cards:
            self._draw_card(card)

        # Karty v lete
        for card in self.cards_in_flight:
            self._draw_card(card)

        # Hint — preskočiť
        self._draw_skip_hint()

    def _draw_card(self, card: dict):
        """Nakreslí jednu kartu (zadná strana)."""
        img = self.card_renderer._get_card_back()

        if card["target_player"] == 1:
            img = pygame.transform.rotate(img, 90)
        elif card["target_player"] == 2:
            img = pygame.transform.rotate(img, 180)  # ← PC2 hore
        elif card["target_player"] == 3:
            img = pygame.transform.rotate(img, -90)

        self.screen.blit(img, (int(card["x"]), int(card["y"])))

    def _draw_skip_hint(self):
        """Zobrazí hint na preskočenie."""
        text = self.font.render(
            "Medzerník / klik — preskočiť", True, COLOR_WHITE
        )
        overlay = pygame.Surface(
            (text.get_width() + 20, text.get_height() + 10),
            pygame.SRCALPHA
        )
        overlay.fill((25, 15, 8, 180))
        x = TABLE_CENTER_X - overlay.get_width() // 2
        y = SCREEN_HEIGHT - 60
        self.screen.blit(overlay, (x, y))
        self.screen.blit(text, (x + 10, y + 5))

    def __repr__(self) -> str:
        return f"DealAnimation(done={self.done}, cards={len(self.deal_queue)})"