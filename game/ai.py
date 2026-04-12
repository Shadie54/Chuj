# game/ai.py

from game.player import Player
from game.card import Card
from game.trick import Trick
from game.ai_memory import AIMemory
from game.ai_strategies_const import Strategy
from config import NUM_PLAYERS, SUITS


class AI:
    def __init__(self, player: Player, difficulty: str = "hard",
                 logger=None):
        self.player = player
        self.difficulty = difficulty
        self.logger = logger
        self.player_name = player.name

        # Nová pamäť
        self.memory = AIMemory(player.index)

        # Záväzok
        self.declaration_player: int | None = None
        self.declaration_type: str | None = None

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player_name, strategy, details)

    # ------------------------------------------------------------------
    # Záväzok
    # ------------------------------------------------------------------

    def decide_declaration(self) -> str | None:
        if self.difficulty == "easy":
            return None

        hand = self.player.hand.cards

        if self._can_take_none(hand):
            self._log(Strategy.DECLARATION_NONE, "žiadne trestné karty")
            return "none"
        if self.difficulty == "hard" and self._can_take_all(hand):
            self._log(Strategy.DECLARATION_ALL, "dominancia")
            return "all"

        return None

    @staticmethod
    def _can_take_none(hand: list[Card]) -> bool:
        has_penalty = any(card.is_penalty_card for card in hand)
        has_special = any(card.is_special for card in hand)
        if has_penalty or has_special:
            return False
        high_cards = [c for c in hand if c.rank in ("ace", "king")]
        if high_cards:
            return False
        return True

    def _can_take_all(self, hand: list[Card]) -> bool:
        for suit in SUITS:
            suit_cards = [c for c in hand if c.suit == suit]
            if not suit_cards:
                continue
            highest_in_hand = max(suit_cards, key=lambda c: c.rank_order)
            unplayed = self._get_unplayed_in_suit(suit, hand)
            if not unplayed:
                continue
            highest_unplayed = max(unplayed, key=lambda c: c.rank_order)
            if highest_in_hand.rank_order < highest_unplayed.rank_order:
                return False
        return True

    # ------------------------------------------------------------------
    # Vysvietenie
    # ------------------------------------------------------------------

    def decide_illumination(self) -> tuple[bool, bool]:
        if self.difficulty == "easy":
            return False, False

        hand = self.player.hand.cards
        illuminate_leaf = False
        illuminate_acorn = False

        if self.difficulty in ("medium", "hard"):
            if self.player.hand.has_leaf_over():
                other_leaf = [c for c in hand
                              if c.suit == "leaf" and not c.is_leaf_over]
                if not other_leaf:
                    illuminate_leaf = True

            if self.player.hand.has_acorn_over():
                other_acorn = [c for c in hand
                               if c.suit == "acorn" and not c.is_acorn_over]
                if not other_acorn:
                    illuminate_acorn = True

        return illuminate_leaf, illuminate_acorn

    # ------------------------------------------------------------------
    # Výber karty
    # ------------------------------------------------------------------

    def decide_card(self, playable: list[Card],
                    current_trick: Trick,
                    trick_number: int) -> Card:
        import random

        if self.difficulty == "easy":
            return random.choice(playable)

        is_leader = len(current_trick.played_cards) == 0

        # Hra proti záväzku
        if self.declaration_player is not None:
            if self.declaration_player != self.player.index:
                card = self._play_against_declaration(
                    playable, current_trick,
                    trick_number, self.declaration_type,
                    self.declaration_player
                )
                if card:
                    return card

        if is_leader:
            return self._decide_as_leader(playable, trick_number)
        else:
            return self._decide_as_follower(playable, current_trick,
                                             trick_number)

    # ------------------------------------------------------------------
    # Leader stratégia
    # ------------------------------------------------------------------

    def _decide_as_leader(self, playable: list[Card],
                          trick_number: int) -> Card:
        hand = self.player.hand.cards

        # Prvý štych — žiadna červeň
        non_heart = [c for c in playable if c.suit != "heart"]
        if trick_number == 0 and non_heart:
            playable = non_heart

        # FORCE_SPECIAL — donútiť súpera zobrať horníka
        force_card = self._try_force_special(playable, hand)
        if force_card:
            return force_card

        # Rozdeľ karty na "isté štychy" a "neisté"
        sure_win = []
        risky = []

        for card in playable:
            if card.is_special or card.suit == "heart":
                risky.append(card)
                continue

            # Mám horníka tej istej farby?
            my_special_same_suit = any(
                c.is_special and c.suit == card.suit for c in hand
            )

            # Je karta najvyššia ostávajúca?
            if self.memory.is_highest_remaining(card):
                if my_special_same_suit:
                    risky.append(card)  # istý štych ale mám horníka → nebezpečné
                else:
                    sure_win.append(card)
            else:
                risky.append(card)  # niekto má vyššiu

        # Preferuj riskovú nízku kartu — pusť niekoho iného na štych
        safe_risky = [
            c for c in risky
            if not c.is_special and c.suit != "heart"
        ]
        if safe_risky:
            card = min(safe_risky, key=lambda c: c.rank_order)
            self._log(Strategy.SAFE_LEAD, f"nízka karta: {card}")
            return card

        # Zahraj istý štych len ak mám dobrý dôvod
        if sure_win:
            has_dangerous = any(
                c.is_special or (c.suit == "heart" and
                c.rank in ("ace", "king"))
                for c in hand
            )
            if has_dangerous:
                card = min(sure_win, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"istý štych: {card}")
                return card

        # Fallback — najnižšia karta
        card = min(playable, key=lambda c: c.rank_order)
        self._log(Strategy.SAFE_LEAD, f"fallback: {card}")
        return card

    def _try_force_special(self, playable: list[Card],
                            hand: list[Card]) -> Card | None:
        if self.difficulty != "hard":
            return None

        for suit in SUITS:
            if self.memory.is_special_gone(suit):
                continue

            # Ostala v tejto farbe u súperov len jedna karta = horník?
            unplayed = self._get_unplayed_in_suit(suit, hand)
            if len(unplayed) == 1 and unplayed[0].is_special:
                suit_playable = [c for c in playable if c.suit == suit]
                if suit_playable:
                    self._log(Strategy.FORCE_SPECIAL,
                              f"{suit} → plonkový horník")
                    return min(suit_playable, key=lambda c: c.rank_order)

        return None

    # ------------------------------------------------------------------
    # Follower stratégia
    # ------------------------------------------------------------------

    def _decide_as_follower(self, playable: list[Card],
                            trick: Trick,
                            _trick_number: int) -> Card:
        trick_has_penalty = trick.total_base_points > 0
        trick_has_special = any(c.is_special for _, c in trick.played_cards)
        is_last = len(trick.played_cards) == NUM_PLAYERS - 1

        if trick_has_penalty or trick_has_special:
            can_under = self._can_underplay(playable, trick)
            if can_under:
                lead_cards = [c for c in playable
                              if c.suit == trick.lead_suit]
                if lead_cards:
                    self._log(Strategy.AVOID_PENALTY, "podliezam")
                    return min(lead_cards, key=lambda c: c.rank_order)
                return self._best_discard_opportunity(playable, trick)
            else:
                # Musím zobrať → zahraj najvyššiu ale NIE horníkom
                lead_cards = [c for c in playable
                              if c.suit == trick.lead_suit
                              and not c.is_special]
                if lead_cards:
                    return max(lead_cards, key=lambda c: c.rank_order)
                return max(playable, key=lambda c: c.rank_order)

        # Štych čistý
        if is_last:
            discard = self._best_discard_opportunity(playable, trick)
            if (discard.is_special or discard.suit == "heart" or
                    discard.rank in ("ace", "king")):
                return discard
            else:
                lead_cards = [c for c in playable
                              if c.suit == trick.lead_suit]
                if lead_cards:
                    return min(lead_cards, key=lambda c: c.rank_order)
                return min(playable, key=lambda c: c.rank_order)
        else:
            dump = self._try_dump_special(playable, trick)
            if dump:
                return dump
            lead_cards = [c for c in playable if c.suit == trick.lead_suit]
            if lead_cards:
                return min(lead_cards, key=lambda c: c.rank_order)
            return self._best_discard_opportunity(playable, trick)

    def _try_dump_special(self, playable: list[Card],
                          trick: Trick) -> Card | None:
        lead_suit = trick.lead_suit
        has_lead = any(c.suit == lead_suit for c in self.player.hand.cards)
        specials_in_hand = [c for c in playable if c.is_special]

        if not specials_in_hand or has_lead:
            return None

        current_best = self._get_best_card(trick)
        for special in specials_in_hand:
            if not self._beats(special, current_best, trick):
                self._log(Strategy.DUMP_SPECIAL, f"{special}")
                return special

        return None

    def _best_discard_opportunity(self, playable: list[Card],
                                  trick: Trick) -> Card:
        current_best = self._get_best_card(trick)

        # 1. Horník ak ho štych neberie
        specials = [c for c in playable if c.is_special]
        for s in specials:
            if not self._beats(s, current_best, trick):
                self._log(Strategy.DUMP_SPECIAL, f"príležitosť: {s}")
                return s

        # 2. Vysoká červeň
        hearts = [c for c in playable if c.suit == "heart"]
        if hearts:
            card = max(hearts, key=lambda c: c.rank_order)
            self._log(Strategy.AVOID_PENALTY, f"červeň: {card}")
            return card

        # 3. Nebezpečné karty podľa pamäte
        hand = self.player.hand.cards
        dangerous = self.memory.get_dangerous_cards(hand)
        for d in dangerous:
            if d in playable and not d.is_special:
                self._log(Strategy.AVOID_PENALTY, f"nebezpečná: {d}")
                return d

        # 4. Najvyššia karta
        return max(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # Hra proti záväzku
    # ------------------------------------------------------------------

    def _play_against_declaration(self, playable, trick,
                                   _trick_number, decl_type,
                                   _decl_player) -> Card | None:
        is_leader = len(trick.played_cards) == 0

        if decl_type == "all":
            current_best = self._get_best_card(trick)
            can_beat = [c for c in playable
                        if self._beats(c, current_best, trick)]
            if can_beat:
                self._log(Strategy.AGAINST_DECLARATION, "pokazím all")
                return min(can_beat, key=lambda c: c.rank_order)

        elif decl_type == "none":
            if is_leader:
                best_suit = self._find_suit_to_force_penalty(playable)
                if best_suit:
                    suit_cards = [c for c in playable
                                  if c.suit == best_suit]
                    return min(suit_cards, key=lambda c: c.rank_order)
            else:
                if trick.lead_suit:
                    lead_cards = [c for c in playable
                                  if c.suit == trick.lead_suit]
                    if lead_cards:
                        return max(lead_cards, key=lambda c: c.rank_order)
                penalty = [c for c in playable if c.is_penalty_card]
                if penalty:
                    return max(penalty, key=lambda c: c.rank_order)

        return None

    def _find_suit_to_force_penalty(self, playable: list[Card]) -> str | None:
        hand = self.player.hand.cards
        best_suit = None
        best_score = -1

        for suit in SUITS:
            if suit == "heart":
                continue
            suit_cards = [c for c in playable if c.suit == suit]
            if not suit_cards:
                continue
            remaining = self.memory.get_remaining_count(suit)
            score = 8 - remaining
            if score > best_score:
                best_score = score
                best_suit = suit

        return best_suit

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _get_unplayed_in_suit(self, suit: str,
                               hand: list[Card]) -> list[Card]:
        """Používa pamäť — presné ostávajúce karty."""
        return [c for c in self.memory.get_remaining(suit)
                if c not in hand]

    @staticmethod
    def _beats(card: Card, current_best: Card | None,
               trick: Trick) -> bool:
        if current_best is None:
            return True
        if card.suit != trick.lead_suit:
            return False
        if current_best.suit != trick.lead_suit:
            return True
        return card.rank_order > current_best.rank_order

    @staticmethod
    def _get_best_card(trick: Trick) -> Card | None:
        if not trick.played_cards:
            return None
        winner_idx = trick.get_winner_index()
        for idx, card in trick.played_cards:
            if idx == winner_idx:
                return card
        return None

    def _can_underplay(self, playable: list[Card],
                        trick: Trick) -> bool:
        current_best = self._get_best_card(trick)
        if current_best is None:
            return False
        lead_cards = [c for c in playable if c.suit == trick.lead_suit]
        if not lead_cards:
            return True
        return any(c.rank_order < current_best.rank_order
                   for c in lead_cards)

    # ------------------------------------------------------------------
    # Pamäť — verejné rozhranie
    # ------------------------------------------------------------------

    def record_trick(self, played_cards: list[tuple[int, Card]],
                     winner_index: int, _trick_number: int):
        self.memory.record_trick(played_cards, winner_index)

    def record_illumination(self, player_index: int,
                             leaf: bool, acorn: bool):
        self.memory.record_illumination(player_index, leaf, acorn)

    def record_declaration(self, player_index: int,
                            declaration: str | None):
        if declaration:
            self.declaration_player = player_index
            self.declaration_type = declaration

    def reset_memory(self):
        self.memory.reset()
        self.declaration_player = None
        self.declaration_type = None

    def __repr__(self) -> str:
        return f"AI({self.player.name}, difficulty={self.difficulty})"