# game/ai_v2/strategies/lead_safe.py

from game.card import Card
from game.ai_v2.context import AIContext, TrickOutcome, card_outcome
from game.ai_v2.strategies.base import Strategy


class LeadSafe(Strategy):
    """
    Vediem bezpečnou kartou ako leader.

    Varianty:
    - HIGH_SCORE  — pri 90+, vediem nízkou prebytočnou červeňou
    - BELL_ESCAPE — bell nešla, risk_pick matica
    - ESCAPE      — najnižšia escape karta (leaf/acorn prednosť)
    - EXHAUST     — vyčerpaj farbu kde mám veľa rezerv
    """

    name = "LeadSafe"

    def is_active(self, ctx: AIContext) -> bool:
        if not ctx.is_leader:
            return False

        if ctx.is_high_score and self._surplus_low_hearts(ctx):
            return True
        if self._bell_escape_card(ctx):
            return True
        if self._escape_candidates(ctx):
            return True
        if self._exhaust_candidates(ctx):
            return True

        return False

    def propose(self, ctx: AIContext) -> Card | None:
        # HIGH_SCORE — prebytočná nízka červeň
        if ctx.is_high_score:
            card = self._surplus_low_hearts(ctx)
            if card:
                self._set_log("HIGH_SCORE", f"prebytočná nízka červeň: {card}")
                return card

        # BELL_ESCAPE
        bell = self._bell_escape_card(ctx)
        if bell:
            self._set_log("BELL_ESCAPE", f"{bell}")
            return bell

        # ESCAPE
        escape = self._escape_candidates(ctx)
        if escape:
            # Leaf/acorn prednosť
            for suit in ("leaf", "acorn"):
                suit_escape = [c for c in escape if c.suit == suit]
                if suit_escape:
                    card = min(suit_escape, key=lambda c: c.rank_order)
                    self._set_log("ESCAPE", f"{suit}: {card}")
                    return card
            card = min(escape, key=lambda c: c.rank_order)
            self._set_log("ESCAPE", f"{card}")
            return card

        # EXHAUST
        exhaust = self._exhaust_candidates(ctx)
        if exhaust:
            card = min(exhaust, key=lambda c: c.rank_order)
            self._set_log("EXHAUST", f"{card}")
            return card

        return None

    def _surplus_low_hearts(self, ctx: AIContext) -> Card | None:
        """Pri 90+ — prebytočná nízka červeň (viac nízkych než vysokých)."""
        hand = self.player.hand.cards
        hearts = [c for c in hand if c.suit == "heart"]
        high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
        low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]

        surplus = len(low_hearts) - len(high_hearts)
        if surplus <= 0:
            return None

        playable_low = [
            c for c in ctx.playable
            if c.suit == "heart"
               and c.rank in ("seven", "eight", "nine")
        ]
        if not playable_low:
            return None

        return max(playable_low, key=lambda c: c.rank_order)

    def _bell_escape_card(self, ctx: AIContext) -> Card | None:
        """
        Bell escape — bell nešla + risk_pick matica.
        Zahrnuje trap bell ak mám buffer a nízke void riziko.
        """
        if "bell" in self.memory.suits_led:
            return None

        all_bell = [
            c for c in ctx.playable
            if c.suit == "bell" and not c.is_special
        ]
        if not all_bell:
            return None

        my_count = len([
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ])
        remaining = len(self.memory.remaining["bell"])
        all_in_hand = [
            c for c in self.player.hand.cards
            if c.suit == "bell" and not c.is_special
        ]

        trap_bell = [c for c in all_bell if self._is_trap(c, ctx)]
        non_trap_bell = [c for c in all_bell if not self._is_trap(c, ctx)]

        # Trap + non-trap — dump trap ak buffer + nízke void riziko
        if trap_bell and non_trap_bell:
            if remaining >= 5 and my_count <= 2:
                return max(trap_bell, key=lambda c: c.rank_order)

        # Osamelá bell
        if my_count == 1:
            card = all_bell[0]
            if not self._is_trap(card, ctx):
                return card
            return card  # osamelý trap — bell nešla = nízke void riziko

        # Non-trap bell cez risk_pick
        if non_trap_bell:
            card = self._risk_pick_matrix(
                non_trap_bell, my_count, remaining, all_in_hand, ctx
            )
            if card:
                return card

        # Trap bell fallback ak veľa remaining
        if trap_bell and my_count <= 2 and remaining >= 5:
            return max(trap_bell, key=lambda c: c.rank_order)

        return None

    def _escape_candidates(self, ctx: AIContext) -> list[Card]:
        """
        Escape karty — nie special, nie protected,
        nie last escape v živej horník farbe,
        nie A/K v živej horník farbe bez vlastného horníka.
        Card_outcome musí byť NEVER alebo UNKNOWN.
        """
        hand = self.player.hand.cards
        candidates = []

        for c in ctx.decision.hand_eval.escape_cards:
            if c not in ctx.playable:
                continue
            if c.is_special:
                continue
            if c.suit in ctx.decision.protected_suits:
                continue
            if self._is_last_escape_dangerous(c, ctx):
                continue
            # A/K v živej horník farbe bez vlastného horníka
            if c.rank in ("ace", "king") and c.suit in ("leaf", "acorn"):
                if not self.memory.is_special_gone(c.suit):
                    if not any(x.is_special and x.suit == c.suit for x in hand):
                        continue
            # Posledný buffer pre môjho horníka
            if c.suit in ("leaf", "acorn"):
                if any(x.is_special and x.suit == c.suit for x in hand):
                    if not self.memory.is_special_gone(c.suit):
                        non_special_playable = [
                            x for x in ctx.playable
                            if x.suit == c.suit and not x.is_special and x != c
                        ]
                        if not non_special_playable:
                            continue
            # card_outcome musí byť NEVER alebo UNKNOWN
            outcome = card_outcome(
                c, ctx.decision.trick,
                self.memory, ctx.decision.players_after
            )
            if outcome == TrickOutcome.CERTAIN:
                continue
            candidates.append(c)

        return candidates

    def _is_last_escape_dangerous(self, card: Card,
                                   ctx: AIContext) -> bool:
        """Posledná escape v živej horník farbe."""
        suit = card.suit
        if suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(suit):
            return False
        holders = ctx.decision.special_holders.get(suit, set())
        if not holders:
            return False
        hand = self.player.hand.cards
        if any(c.is_special and c.suit == suit for c in hand):
            return False
        remaining_escapes = [
            c for c in ctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank not in ("ace", "king")
               and c != card
        ]
        high_cards = [
            c for c in ctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank in ("ace", "king")
               and self._is_trap(c, ctx)
        ]
        return not remaining_escapes and bool(high_cards)

    def _exhaust_candidates(self, ctx: AIContext) -> list[Card]:
        """Farba kde som vysvietil horníka + 4+ rezervy + žiadny A/K."""
        candidates = []
        for suit in ("leaf", "acorn"):
            if self.memory.illuminated_by[suit] != self.player.index:
                continue
            reserves = [
                c for c in self.player.hand.cards
                if c.suit == suit and not c.is_special
            ]
            if len(reserves) < 4:
                continue
            if any(c.rank in ("ace", "king") for c in reserves):
                continue
            suit_playable = [
                c for c in ctx.playable
                if c.suit == suit and not c.is_special
            ]
            candidates += suit_playable
        return candidates

    def _risk_pick_matrix(self, suit_cards: list[Card],
                          my_count: int, remaining: int,
                          all_in_hand: list[Card],
                          ctx: AIContext) -> Card | None:
        if not suit_cards:
            return None

        def safe_or_lowest() -> Card:
            safe = [c for c in suit_cards if self._is_safe(c, ctx)]
            pool = safe if safe else suit_cards
            return min(pool, key=lambda c: c.rank_order)

        def mid_card() -> Card | None:
            if not all_in_hand:
                return None
            highest = max(all_in_hand, key=lambda c: c.rank_order)
            candidates = [
                c for c in suit_cards
                if highest.rank_order - c.rank_order >= 2
            ]
            if not candidates:
                return None
            return max(candidates, key=lambda c: c.rank_order)

        if remaining >= 5:
            if my_count <= 2:
                return max(suit_cards, key=lambda c: c.rank_order)
            elif my_count == 3:
                mid = mid_card()
                return mid if mid else min(suit_cards, key=lambda c: c.rank_order)
            else:
                return safe_or_lowest()
        else:
            if my_count <= 2:
                mid = mid_card()
                return mid if mid else min(suit_cards, key=lambda c: c.rank_order)
            else:
                return safe_or_lowest()

    def weight(self, ctx: AIContext) -> float:
        return 6.0