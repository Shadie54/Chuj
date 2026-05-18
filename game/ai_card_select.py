# game/ai_card_select.py

from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval, GameContext, DecisionContext
from game.ai_strategies_const import Strategy, Situation, Mode
from config import NUM_PLAYERS, SUITS


class CardSelector:
    def __init__(self, player: Player, memory: AIMemory,
                 logger=None, on_strategy=None):
        self.on_strategy = on_strategy  # callback → AI.last_strategy
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, strategy: str, details: str = ""):
        if self.on_strategy:
            self.on_strategy(strategy)
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def select(self, situation: str, mode: str,
               dctx: DecisionContext) -> Card:
        if mode == Mode.SAFE:
            return self._play_safe(situation, dctx)
        elif mode == Mode.TAKE:
            return self._play_take(situation, dctx)
        elif mode == Mode.OPEN:
            return self._play_open(situation, dctx)
        elif mode == Mode.RISK:
            return self._play_take(situation, dctx)
        return min(dctx.playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # SAFE
    # ------------------------------------------------------------------

    def _play_safe(self, situation: str, dctx: DecisionContext) -> Card:
        playable = dctx.playable
        hand_eval = dctx.hand_eval

        if dctx.is_leader:
            if situation == Situation.LEADER_HIGH_SCORE:
                hand = self.player.hand.cards
                hearts = [c for c in hand if c.suit == "heart"]
                high_hearts = [c for c in hearts if c.rank in ("ace", "king")]
                low_hearts = [c for c in hearts if c.rank in ("seven", "eight", "nine")]
                surplus_low = len(low_hearts) - len(high_hearts)
                low_heart_playable = [
                    c for c in playable
                    if c.suit == "heart"
                       and c.rank in ("seven", "eight", "nine")
                ]
                candidates = sorted(
                    low_heart_playable, key=lambda c: c.rank_order, reverse=True
                )
                if candidates and surplus_low > 0:
                    card = candidates[0]
                    self._log(Strategy.HIGH_SCORE_LEAD, f"prebytočná nízka červeň: {card}")
                    return card

            escape_playable = [
                c for c in hand_eval.escape_cards
                if c in playable
                   and not c.is_special
                   and c.suit not in dctx.protected_suits
                   and not self._is_last_escape_in_dangerous_suit(c, dctx)
                   # Veto — escape A/K vo farbe živého cudzieho horníka
                   and not (
                        c.rank in ("ace", "king")
                        and c.suit in ("leaf", "acorn")
                        and not self.memory.is_special_gone(c.suit)
                        and not any(x.is_special and x.suit == c.suit
                                    for x in self.player.hand.cards)
                )
            ]
            if escape_playable:
                card = min(escape_playable, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"escape: {card}")
                return card

            exhaust_cards = [
                c for c in playable
                if not c.is_special
                   and (c.suit not in dctx.protected_suits
                        or c.suit in dctx.exhaustable_suits)
                   and not (
                        c.suit in ("leaf", "acorn")
                        and not self.memory.is_special_gone(c.suit)
                        and not any(x.is_special and x.suit == c.suit
                                    for x in self.player.hand.cards)
                )
            ]
            if exhaust_cards:
                for c in exhaust_cards:
                    if c.suit not in ("leaf", "acorn"):
                        continue
                    if c.rank not in ("ace", "king"):
                        continue
                    if self.memory.is_special_gone(c.suit):
                        continue
                    special = next(
                        (x for x in self.player.hand.cards
                         if x.is_special and x.suit == c.suit), None
                    )
                    if special is None or special not in playable:
                        continue
                    remaining_higher = [
                        r for r in self.memory.remaining[c.suit]
                        if r.rank_order > special.rank_order and not r.is_special
                    ]
                    if remaining_higher:
                        self._log(Strategy.RISK_SPECIAL, f"risk horník: {special}")
                        return special
                card = min(exhaust_cards, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"exhaust fallback: {card}")
                return card

            # Last resort — ak nemáme nič, skúsime protected suits
            non_special = [
                c for c in playable
                if not c.is_special or self._special_is_safe_lead(c)
            ]

            # Prednostne escape z protected suits
            protected_escape = [
                c for c in non_special
                if c.suit in dctx.protected_suits
                   and c in hand_eval.escape_cards
            ]
            if protected_escape:
                card = min(protected_escape, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"last resort protected escape: {card}")
                return card

            pool = non_special if non_special else playable
            card = min(pool, key=lambda c: c.rank_order)
            self._log(Strategy.SAFE_LEAD, f"last resort: {card}")
            return card

        else:
            # Follower
            lead_suit = dctx.lead_suit

            # Dump trap A/K ak mám živého horníka v tej istej farbe
            current_best = self._get_current_best(dctx.trick)
            if lead_suit in ("leaf", "acorn"):
                if not self.memory.is_special_gone(lead_suit):
                    my_special = next(
                        (c for c in dctx.lead_cards if c.is_special), None
                    )
                    has_live_special = my_special is not None or bool(
                        dctx.special_holders.get(lead_suit, set())
                    )
                    if has_live_special:
                        special_in_trick = any(
                            c.is_special for _, c in dctx.trick.played_cards
                        )
                        if not special_in_trick and dctx.someone_takes != "no":
                            if my_special and my_special in dctx.lead_cards:
                                dangerous_after = False
                            else:
                                holders = dctx.special_holders.get(lead_suit, set())
                                dangerous_after = any(
                                    p in holders for p in dctx.players_after
                                )

                            if not dangerous_after:
                                if my_special and my_special in dctx.lead_cards:
                                    if current_best and my_special.rank_order < current_best.rank_order:
                                        self._log(Strategy.DUMP_SPECIAL,
                                                  f"dump horník živý: {my_special}")
                                        return my_special

                                if my_special and my_special in dctx.lead_cards:
                                    if self.memory.illuminated_by[lead_suit] is None:
                                        if len(dctx.players_after) == 1:
                                            trap_high = [
                                                c for c in dctx.lead_cards
                                                if c.rank in ("ace", "king") and not c.is_special
                                            ]
                                            if trap_high:
                                                card = max(trap_high, key=lambda c: c.rank_order)
                                                self._log(Strategy.DUMP_DANGEROUS,
                                                          f"dump trap A/K horník môj nevysvietený 3.poradie: {card}")
                                                return card

                                trap_high = [
                                    c for c in dctx.lead_cards
                                    if c.rank in ("ace", "king") and not c.is_special
                                ]
                                if trap_high:
                                    card = max(trap_high, key=lambda c: c.rank_order)
                                    self._log(Strategy.DUMP_FREE if dctx.is_last
                                              else Strategy.DUMP_DANGEROUS,
                                              f"dump trap A/K živý horník: {card}")
                                    return card

            current_best = self._get_current_best(dctx.trick)
            underplay = [
                c for c in dctx.lead_cards
                if current_best and c.rank_order < current_best.rank_order
            ]
            if underplay:
                specials_under = [c for c in underplay if c.is_special]
                if specials_under:
                    card = specials_under[0]
                    self._log(Strategy.DUMP_SPECIAL, f"underplay horník: {card}")
                    return card
                card = max(underplay, key=lambda c: c.rank_order)
                self._log(Strategy.UNDERPLAY, f"podliezam: {card}")
                return card
            return min(dctx.playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # TAKE
    # ------------------------------------------------------------------

    def _play_take(self, situation: str, dctx: DecisionContext) -> Card:
        playable = dctx.playable

        if situation == Situation.LEADER_AGGRESSIVE:
            for suit in SUITS:
                if self.memory.is_special_gone(suit):
                    continue
                holders = dctx.special_holders.get(suit, set())
                if not holders or self.player.index in holders:
                    continue
                suit_cards = [
                    c for c in playable
                    if c.suit == suit
                       and not c.is_special
                       and c.rank not in ("ace", "king")
                ]
                if suit_cards:
                    card = min(suit_cards, key=lambda c: c.rank_order)
                    self._log(Strategy.FORCE_SPECIAL,
                              f"vytiahni horníka {suit}: {card}")
                    return card
        if situation == Situation.FOLLOWER_RISK:
            return self._risk_trap(dctx)

        if situation == Situation.FOLLOWER_FORCED_CLEAN:
            return self._controlled_take(dctx)

        if situation == Situation.FOLLOWER_FREE_TAKE:
            return self._free_take(dctx)

        # Follower štandard
        non_special_lead = [c for c in dctx.lead_cards if not c.is_special]
        if non_special_lead:
            if dctx.is_last:
                card = max(non_special_lead, key=lambda c: c.rank_order)
                self._log(Strategy.FORCED_TAKE, f"najvyššia lead (posledný): {card}")
            else:
                card = min(non_special_lead, key=lambda c: c.rank_order)
                self._log(Strategy.FORCED_TAKE, f"najnižšia lead: {card}")
            return card

        if dctx.lead_cards:
            return max(dctx.lead_cards, key=lambda c: c.rank_order)
        return max(playable, key=lambda c: c.rank_order)

    def _controlled_take(self, dctx: DecisionContext) -> Card:
        lead_cards = dctx.lead_cards

        # Dump trap A/K — len ak som posledný
        if dctx.is_last:
            danger = [
                c for c in lead_cards
                if c.rank in ("ace", "king") and self._is_trap(c, dctx.trick)
            ]
            if danger:
                card = max(danger, key=lambda c: c.rank_order)
                self._log(Strategy.LAST_TAKE, f"dump trap A/K: {card}")
                return card

        # Najvyššia non-special lead
        non_special_lead = [c for c in lead_cards if not c.is_special]
        pool = non_special_lead if non_special_lead else lead_cards
        if pool:
            card = max(pool, key=lambda c: c.rank_order)
            self._log(Strategy.LAST_TAKE if dctx.is_last
                      else Strategy.FORCED_TAKE, f"najvyššia lead: {card}")
            return card

        return max(dctx.playable, key=lambda c: c.rank_order)

    def _free_take(self, dctx: DecisionContext) -> Card:
        lead_cards = dctx.lead_cards

        high = [
            c for c in lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        if high:
            card = max(high, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_FREE, f"dump A/K free: {card}")
            return card

        non_special_lead = [c for c in lead_cards if not c.is_special]
        pool = non_special_lead if non_special_lead else lead_cards
        if pool:
            card = max(pool, key=lambda c: c.rank_order)
            self._log(Strategy.LAST_TAKE, f"fallback najvyššia: {card}")
            return card

        return max(dctx.playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # OPEN
    # ------------------------------------------------------------------

    def _play_open(self, situation: str, dctx: DecisionContext) -> Card:
        if situation == Situation.FOLLOWER_VOID:
            return self._void_discard(dctx)
        if situation == Situation.LEADER_RISK:
            return self._risk_play(dctx)
        if situation in (Situation.LEADER_FORCED, Situation.FOLLOWER_WAIT):
            return self._open_play(dctx)
        return min(dctx.playable, key=lambda c: c.rank_order)

    def _risk_play(self, dctx: DecisionContext) -> Card:
        for suit in ("leaf", "acorn"):
            special = next(
                (c for c in dctx.playable if c.is_special and c.suit == suit), None
            )
            if special is None:
                continue
            remaining_higher = [
                c for c in self.memory.remaining[suit]
                if c.rank_order > special.rank_order and not c.is_special
            ]
            if remaining_higher:
                self._log(Strategy.RISK_SPECIAL, f"risk horník: {special}")
                return special
        return min(dctx.playable, key=lambda c: c.rank_order)

    def _void_discard(self, dctx: DecisionContext) -> Card:
        if dctx.game_ctx.my_declaration == "none":
            return self._void_discard_none(dctx.playable)
        if dctx.game_ctx.is_high_score:
            return self._void_discard_high_score(dctx)
        return self._void_discard_standard(dctx)

    def _void_discard_high_score(self, dctx: DecisionContext) -> Card:
        playable = dctx.playable
        trick = dctx.trick

        both_illuminated = (
                self.memory.illuminated_by["leaf"] is not None
                and self.memory.illuminated_by["acorn"] is not None
        )
        heart_multiplier = 2 if both_illuminated else 1

        trap_hearts_playable = [
            c for c in playable
            if c.suit == "heart" and self._is_trap(c, trick)
        ]
        expected_damage = len(trap_hearts_playable) * heart_multiplier
        near_loss = dctx.game_ctx.my_score + expected_damage >= 95

        if near_loss and trap_hearts_playable:
            card = max(trap_hearts_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"90+ near loss trap heart: {card}")
            return card

        specials = [c for c in playable if c.is_special]
        if specials:
            card = max(specials, key=lambda c: self._special_points(c))
            self._log(Strategy.DUMP_SPECIAL, f"90+ dump horník: {card}")
            return card

        if trap_hearts_playable:
            card = max(trap_hearts_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"90+ trap heart: {card}")
            return card

        non_safe_hearts = [
            c for c in playable
            if c.suit == "heart" and not self._is_safe_heart(c)
        ]
        if non_safe_hearts:
            card = max(non_safe_hearts, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"90+ non-safe heart: {card}")
            return card

        return self._void_discard_standard(dctx)

    def _is_safe_heart(self, card: Card) -> bool:
        """Najnižšia červeň v hre — garantovane neprehráme štich."""
        remaining_lower = [
            c for c in self.memory.remaining["heart"]
            if c.rank_order < card.rank_order
        ]
        return len(remaining_lower) == 0

    def _void_discard_none(self, playable: list[Card]) -> Card:
        non_special = [c for c in playable if not c.is_special]
        pool = non_special if non_special else playable
        card = max(pool, key=lambda c: c.rank_order)
        self._log(Strategy.DUMP_DANGEROUS, f"none záväzok void: {card}")
        return card

    def _void_discard_standard(self, dctx: DecisionContext) -> Card:
        playable = dctx.playable
        trick = dctx.trick

        specials = [c for c in playable if c.is_special]
        if specials:
            card = max(specials, key=lambda c: self._special_points(c))
            self._log(Strategy.DUMP_SPECIAL,
                      f"{dctx.someone_takes}: {card}")
            return card

        danger_trap = []
        for suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                continue
            suit_cards = [c for c in playable if c.suit == suit and not c.is_special]
            if not suit_cards:
                continue
            remaining_non_special = [
                c for c in self.memory.remaining[suit] if not c.is_special
            ]
            my_non_special = [
                c for c in suit_cards if c.rank not in ("ace", "king")
            ]
            remaining_sorted = sorted(
                remaining_non_special, key=lambda c: c.rank_order, reverse=True
            )
            available = sorted(
                my_non_special, key=lambda c: c.rank_order, reverse=True
            )
            all_covered = True
            for their in remaining_sorted:
                match = next(
                    (c for c in available if c.rank_order < their.rank_order), None
                )
                if match is None:
                    all_covered = False
                    break
                available.remove(match)
            if all_covered:
                continue
            danger_trap += [
                c for c in suit_cards
                if c.rank in ("ace", "king")
            ]

        if danger_trap:
            card = max(danger_trap, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_DANGEROUS, f"trap A/K živý horník: {card}")
            return card

        hearts = [c for c in playable if c.suit == "heart"]
        if hearts:
            card = max(hearts, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"{dctx.someone_takes}: {card}")
            return card

        trap_playable = [
            c for c in playable
            if not c.is_special
               and c.suit != "heart"
               and self._is_trap(c, trick)
        ]
        if trap_playable:
            card = max(trap_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_DANGEROUS, f"trap: {card}")
            return card

        bell_cards = [c for c in playable if c.suit == "bell"]
        if bell_cards:
            card = max(bell_cards, key=lambda c: c.rank_order)
            self._log(Strategy.WAIT, f"fallback bell: {card}")
            return card

        non_special_non_heart = [
            c for c in playable if not c.is_special and c.suit != "heart"
        ]
        pool = non_special_non_heart if non_special_non_heart else playable
        card = max(pool, key=lambda c: c.rank_order)
        self._log(Strategy.WAIT, f"fallback high: {card}")
        return card

    def _open_play(self, dctx: DecisionContext) -> Card:
        playable = dctx.playable
        hand_eval = dctx.hand_eval
        trick = dctx.trick

        if dctx.is_leader:
            single_suit = [
                suit for suit in SUITS
                if sum(1 for c in self.player.hand.cards
                       if c.suit == suit) == 1
                   and suit != "heart"
                   and suit not in dctx.protected_suits
            ]
            for suit in single_suit:
                suit_cards = [
                    c for c in playable
                    if c.suit == suit
                       and not c.is_special
                       and not self._is_trap(c)
                ]
                if suit_cards:
                    card = suit_cards[0]
                    self._log(Strategy.DUMP_SETUP, f"void setup: {card}")
                    return card

        escape_playable = [
            c for c in hand_eval.escape_cards
            if c in playable
               and not c.is_special
               and c.suit not in dctx.protected_suits
        ]
        if escape_playable:
            card = min(escape_playable, key=lambda c: c.rank_order)
            self._log(Strategy.WAIT, f"escape: {card}")
            return card

        if dctx.is_leader:
            exhaust_cards = [
                c for c in playable
                if not c.is_special
                   and c.suit in dctx.exhaustable_suits
            ]
            if exhaust_cards:
                card = min(exhaust_cards, key=lambda c: c.rank_order)
                self._log(Strategy.WAIT, f"exhaust: {card}")
                return card

        if not dctx.is_leader:
            pool = [c for c in dctx.lead_cards if not c.is_special] or dctx.lead_cards
            if pool:
                if not dctx.trick_has_penalty:
                    specials = [c for c in pool if c.is_special]
                    if specials:
                        card = specials[0]
                        self._log(Strategy.DUMP_SPECIAL, f"dump horník: {card}")
                        return card
                    traps = [c for c in pool if self._is_trap(c, trick)]
                    if traps:
                        card = min(traps, key=lambda c: c.rank_order)
                        self._log(Strategy.DUMP_DANGEROUS, f"dump trap: {card}")
                        return card
                    card = max(pool, key=lambda c: c.rank_order)
                    self._log(Strategy.DUMP_DANGEROUS, f"dump high: {card}")
                    return card
                else:
                    card = min(pool, key=lambda c: c.rank_order)
                    self._log(Strategy.WAIT, f"wait: {card}")
                    return card

        non_special = [
            c for c in playable
            if not c.is_special or self._special_is_safe_lead(c)
        ]
        pool = non_special if non_special else playable
        return min(pool, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # RISK
    # ------------------------------------------------------------------

    def _risk_trap(self, dctx: DecisionContext) -> Card:
        trap_high = [
            c for c in dctx.lead_cards
            if c.rank in ("ace", "king") and not c.is_special
        ]
        card = max(trap_high, key=lambda c: c.rank_order)
        self._log(Strategy.RISK_TRAP, f"risk trap: {card}")
        return card
    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------
    def _special_points(self, card: Card) -> int:
        suit = "leaf" if card.is_leaf_over else "acorn"
        illuminated = self.memory.illuminated_by[suit] is not None
        if card.is_leaf_over:
            return 16 if illuminated else 8
        else:
            return 8 if illuminated else 4

    def _is_last_escape_in_dangerous_suit(self, card: Card,
                                          dctx: DecisionContext) -> bool:
        suit = card.suit
        if suit not in ("leaf", "acorn"):
            return False
        if self.memory.is_special_gone(suit):
            return False
        holders = dctx.special_holders.get(suit, set())
        if not holders:
            return False
        i_have_special = any(
            c.is_special and c.suit == suit
            for c in self.player.hand.cards
        )
        if i_have_special:
            return False
        remaining_escapes = [
            c for c in dctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank not in ("ace", "king")
               and c != card
        ]
        high_cards = [
            c for c in dctx.playable
            if c.suit == suit
               and not c.is_special
               and c.rank in ("ace", "king")
               and self._is_trap(c, dctx.trick)
        ]
        result = not remaining_escapes and bool(high_cards)
        return result

    def _is_trap(self, card: Card, trick: Trick | None = None) -> bool:
        higher_opponents = [
            c for c in self.memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        # Karty v aktuálnom štichu tiež počítajú
        if trick:
            higher_in_trick = [
                c for _, c in trick.played_cards
                if c.suit == card.suit and c.rank_order > card.rank_order
            ]
            higher_opponents += higher_in_trick

        higher_own = [
            c for c in self.player.hand.cards
            if c.suit == card.suit
               and c.rank_order > card.rank_order
               and c != card
        ]
        return not higher_opponents and not higher_own

    def _special_is_safe_lead(self, card: Card) -> bool:
        remaining = self.memory.get_remaining(card.suit)
        if not remaining:
            return False
        return all(c.rank_order > card.rank_order for c in remaining)

    @staticmethod
    def _get_current_best(trick: Trick) -> Card | None:
        if not trick.played_cards:
            return None
        winner_idx = trick.get_winner_index()
        for idx, card in trick.played_cards:
            if idx == winner_idx:
                return card
        return None

    @staticmethod
    def _get_play_order(trick: Trick) -> list[int]:
        return [(trick.leader_index + i) % NUM_PLAYERS
                for i in range(NUM_PLAYERS)]
