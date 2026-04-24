# game/ai.py

from dataclasses import dataclass
from game.player import Player
from game.card import Card
from game.trick import Trick
from game.ai_memory import AIMemory
from game.ai_strategies_const import Strategy, Situation, Mode
from config import NUM_PLAYERS, SUITS


# ------------------------------------------------------------------
# HandEval — snapshot ruky pred každým ťahom
# ------------------------------------------------------------------

@dataclass
class HandEval:
    profiles: dict                # dict[str, SuitProfile] — per farba
    void_suits: list[str]         # farby kde som void
    trap_cards: list[Card]        # všetky trap karty naprieč farbami
    escape_cards: list[Card]      # všetky escape karty naprieč farbami
    tricks_remaining: int
    i_will_be_leader: bool        # ak vyhrám tento štich, budem leader


# ------------------------------------------------------------------
# AI
# ------------------------------------------------------------------

class AI:
    def __init__(self, player: Player, difficulty: str = "hard",
                 logger=None):
        self.player = player
        self.difficulty = difficulty
        self.logger = logger
        self.player_name = player.name

        self.memory = AIMemory(player.index)

        # Záväzok
        self.declaration_player: int | None = None
        self.declaration_type: str | None = None

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player_name, strategy, details)

    # ------------------------------------------------------------------
    # Záväzok a vysvietenie (vlastný pipeline neskôr)
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

    def decide_illumination(self) -> tuple[bool, bool]:
        if self.difficulty == "easy":
            return False, False

        hand = self.player.hand.cards
        illuminate_leaf = False
        illuminate_acorn = False

        if self.difficulty in ("medium", "hard"):
            illuminate_leaf = self._should_illuminate(hand, "leaf")
            illuminate_acorn = self._should_illuminate(hand, "acorn")

        return illuminate_leaf, illuminate_acorn

    @staticmethod
    def _should_illuminate(hand: list[Card], suit: str) -> bool:
        """
        Má zmysel vysvietiť horníka danej farby?

        Logika:
        - Mám horníka? (inak False)
        - Mám rezervy?
          0 rezerv → False (plonkový horník = samovražda)
          1 rezerva → True len ak je nízka (nie A, K)
          2+ rezervy → True
        """
        # Mám horníka?
        special = next(
            (c for c in hand if c.is_special and c.suit == suit), None
        )
        if special is None:
            return False

        # Rezervy = ostatné karty tej farby okrem horníka
        reserves = [
            c for c in hand
            if c.suit == suit and not c.is_special
        ]

        if len(reserves) == 0:
            return False  # plonkový horník

        if len(reserves) == 1:
            # Nízka rezerva → True, vysoká → False
            return reserves[0].rank not in ("ace", "king")

        # 2+ rezervy → True
        return True

    # ------------------------------------------------------------------
    # Hlavný vstupný bod
    # ------------------------------------------------------------------

    def decide_card(self, playable: list[Card],
                    current_trick: Trick,
                    trick_number: int) -> Card:
        import random
        if self.difficulty == "easy":
            return random.choice(playable)

        hand = self.player.hand.cards
        tricks_remaining = 8 - trick_number

        # Karty v aktuálnom štichu (pre coverage výpočet)
        trick_cards = [c for _, c in current_trick.played_cards]

        # --- KROK 1: HAND_EVAL ---
        hand_eval = self._evaluate_hand(hand, tricks_remaining,
                                         trick_cards, current_trick)

        # --- KROK 2: SITUATION ---
        situation = self._determine_situation(hand_eval, playable, current_trick)

        # --- KROK 3: MODE ---
        mode = self._situation_to_mode(situation,current_trick)

        # --- KROK 4: CARD ---
        card = self._select_card(
            mode, situation, hand_eval, playable, current_trick
        )

        self._log(f"{situation}/{mode}", str(card))
        return card

    # ------------------------------------------------------------------
    # KROK 1: HAND_EVAL
    # ------------------------------------------------------------------

    def _evaluate_hand(self, hand: list[Card],
                        tricks_remaining: int,
                        trick_cards: list[Card],
                        trick: Trick) -> HandEval:
        """
        Snapshot stavu ruky cez SuitProfile.
        Každá farba sa hodnotí samostatne s coverage = remaining + trick karty.
        """
        profiles = self.memory.build_all_profiles(hand, trick_cards)

        void_suits = [s for s, p in profiles.items() if p.is_void]

        trap_cards = [
            c for p in profiles.values()
            for c in p.trap_cards
        ]
        escape_cards = [
            c for p in profiles.values()
            for c in p.escape_cards
        ]

        # Ak vyhrám tento štich, budem leader v ďalšom
        i_will_be_leader = len(trick.played_cards) == NUM_PLAYERS - 1

        return HandEval(
            profiles=profiles,
            void_suits=void_suits,
            trap_cards=trap_cards,
            escape_cards=escape_cards,
            tricks_remaining=tricks_remaining,
            i_will_be_leader=i_will_be_leader
        )

    # ------------------------------------------------------------------
    # KROK 2: SITUATION
    # ------------------------------------------------------------------

    def _determine_situation(self, hand_eval: HandEval,
                              playable: list[Card],
                              trick: Trick,) -> str:
        is_leader = len(trick.played_cards) == 0

        if is_leader:
            return self._determine_leader_situation(hand_eval, playable)
        else:
            return self._determine_follower_situation(playable, trick)

    def _determine_leader_situation(self, hand_eval: HandEval,
                                     playable: list[Card]) -> str:
        # LEADER_AGGRESSIVE: viem kto má horníka a mám kartu na jeho vytiahnutie
        if self.difficulty == "hard":
            for suit in SUITS:
                if self.memory.is_special_gone(suit):
                    continue
                holders = self.memory.who_has_special(suit)
                if not holders:
                    continue
                if self.player.index in holders:
                    continue
                suit_cards = [
                    c for c in playable
                    if c.suit == suit
                       and not c.is_special
                       and c.rank not in ("ace", "king")
                ]
                if suit_cards:
                    return Situation.LEADER_AGGRESSIVE

        # LEADER_SAFE: mám escape karty (nie červeň)
        non_heart_escape = [
            c for c in hand_eval.escape_cards
            if c.suit != "heart" and c in playable
        ]
        if non_heart_escape:
            return Situation.LEADER_SAFE

        # LEADER_FORCED: nemám bezpečnú možnosť
        return Situation.LEADER_FORCED

    def _determine_follower_situation(self, playable: list[Card],
                                      trick: Trick) -> str:
        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]

        # FOLLOWER_VOID: nemám lead farbu
        if not lead_cards:
            return Situation.FOLLOWER_VOID

        # Môžem podliezť?
        current_best = self._get_current_best(trick)
        can_underplay = any(
            c.rank_order < current_best.rank_order
            for c in lead_cards
        ) if current_best else False

        if can_underplay:
            return Situation.FOLLOWER_SAFE

        # Nemôžem podliezť — zistím kontext
        trick_has_penalty = self._trick_has_penalty(trick)
        is_last = len(trick.played_cards) == NUM_PLAYERS - 1

        if not trick_has_penalty:
            if is_last:
                return Situation.FOLLOWER_CONTROLLED
            else:
                return Situation.FOLLOWER_WAIT

        else:
            # štich má trestné body
            if is_last:
                return Situation.FOLLOWER_FORCED
            else:
                # Môže ma niekto po mne prebiť?
                players_after = self._get_players_after_me(trick)
                trick_cards = [c for _, c in trick.played_cards]
                my_lowest_lead = min(lead_cards, key=lambda c: c.rank_order)
                if self.memory.can_anyone_beat(my_lowest_lead,
                                               players_after,
                                               trick_cards):
                    return Situation.FOLLOWER_WAIT
                else:
                    return Situation.FOLLOWER_FORCED

    # ------------------------------------------------------------------
    # KROK 3: MODE
    # ------------------------------------------------------------------

    def _situation_to_mode(self, situation: str, trick: Trick) -> str:
        mapping = {
            Situation.LEADER_SAFE:        Mode.SAFE,
            Situation.LEADER_FORCED:      Mode.OPEN,
            Situation.LEADER_AGGRESSIVE:  Mode.TAKE,
            Situation.FOLLOWER_SAFE:      Mode.SAFE,
            Situation.FOLLOWER_VOID:      Mode.OPEN,
            Situation.FOLLOWER_FORCED:    Mode.TAKE,
            Situation.FOLLOWER_WAIT:      Mode.OPEN,
            Situation.FOLLOWER_CONTROLLED: None,
        }

        mode = mapping.get(situation)

        # FOLLOWER_CONTROLLED: rozhodne post-win riziko
        if mode is None:
            worst = self._evaluate_post_win_risk(trick)
            return Mode.TAKE if worst <= 4 else Mode.SAFE

        return mode

    # ------------------------------------------------------------------
    # KROK 4: SELECT_CARD
    # ------------------------------------------------------------------

    def _select_card(self, mode: str, situation: str,
                     hand_eval: HandEval,
                     playable: list[Card],
                     trick: Trick) -> Card:
        is_leader = len(trick.played_cards) == 0

        if mode == Mode.SAFE:
            return self._play_safe(playable, trick, is_leader, hand_eval)
        elif mode == Mode.TAKE:
            return self._play_take(playable, trick, situation)
        elif mode == Mode.OPEN:
            return self._play_open(playable, trick, situation, hand_eval)

        return min(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # MODE: SAFE
    # ------------------------------------------------------------------

    def _play_safe(self, playable: list[Card],
                   trick: Trick, is_leader: bool,
                   hand_eval: HandEval) -> Card:
        """
        Cieľ: nezobrať štich.
        Leader: najnižšia escape karta.
        Follower: najvyššia karta ktorou ešte podliezam.
        """
        if is_leader:
            escape_playable = [
                c for c in hand_eval.escape_cards
                if c in playable
                   and (not c.is_special or self._special_is_safe_lead(c))
            ]
            if escape_playable:
                card = min(escape_playable, key=lambda c: c.rank_order)
                self._log(Strategy.SAFE_LEAD, f"escape: {card}")
                return card

            # Fallback: najnižšia non-special karta
            non_special = [
                c for c in playable
                if not c.is_special or self._special_is_safe_lead(c)
            ]
            pool = non_special if non_special else playable
            card = min(pool, key=lambda c: c.rank_order)
            self._log(Strategy.SAFE_LEAD, f"fallback: {card}")
            return card

        else:
            # Follower — najvyššia karta ktorou ešte podliezam
            lead_suit = trick.lead_suit
            current_best = self._get_current_best(trick)
            lead_cards = [c for c in playable if c.suit == lead_suit]
            underplay = [
                c for c in lead_cards
                if current_best and c.rank_order < current_best.rank_order
            ]
            if underplay:
                card = max(underplay, key=lambda c: c.rank_order)
                self._log(Strategy.UNDERPLAY, f"podliezam: {card}")
                return card
            return min(playable, key=lambda c: c.rank_order)

    def _special_is_safe_lead(self, card: Card) -> bool:
        """
        Horník je bezpečný lead len ak všetky ostávajúce karty
        tejto farby sú vyššie, ako horník → niekto musí prebiť.
        """
        remaining = self.memory.get_remaining(card.suit)
        if not remaining:
            return False
        return all(c.rank_order > card.rank_order for c in remaining)

    # ------------------------------------------------------------------
    # MODE: TAKE
    # ------------------------------------------------------------------

    def _play_take(self, playable: list[Card],
                   trick: Trick, situation: str) -> Card:
        """
        Cieľ: zobrať štich kontrolovane.
        LEADER_AGGRESSIVE: vytiahni horníka.
        FOLLOWER_FORCED: najvyššia lead (nie horník ak možné).
        """
        if situation == Situation.LEADER_AGGRESSIVE:
            for suit in SUITS:
                if self.memory.is_special_gone(suit):
                    continue
                holders = self.memory.who_has_special(suit)
                if len(holders) == 1:
                    suit_cards = [c for c in playable
                                  if c.suit == suit and not c.is_special]
                    if suit_cards:
                        card = min(suit_cards, key=lambda c: c.rank_order)
                        self._log(Strategy.FORCE_SPECIAL,
                                  f"vytiahni horníka {suit}: {card}")
                        return card

        # FOLLOWER_FORCED: zoberiem štich — najvyššia nie-horník
        lead_suit = trick.lead_suit
        lead_cards = [c for c in playable if c.suit == lead_suit]
        non_special_lead = [c for c in lead_cards if not c.is_special]

        if non_special_lead:
            card = max(non_special_lead, key=lambda c: c.rank_order)
            self._log(Strategy.FORCED_TAKE, f"najvyššia lead: {card}")
            return card

        if lead_cards:
            return max(lead_cards, key=lambda c: c.rank_order)

        return max(playable, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # MODE: OPEN
    # ------------------------------------------------------------------

    def _play_open(self, playable: list[Card],
                   trick: Trick, situation: str,
                   hand_eval: HandEval) -> Card:
        """
        Cieľ: zlepšiť budúcu pozíciu.
        """
        if situation == Situation.FOLLOWER_VOID:
            return self._void_discard(playable, trick)

        if situation in (Situation.LEADER_FORCED,
                          Situation.FOLLOWER_WAIT):
            return self._open_play(playable, hand_eval, trick)

        return min(playable, key=lambda c: c.rank_order)

    def _void_discard(self, playable: list[Card], trick: Trick) -> Card:
        players_after = self._get_players_after_me(trick)
        takes = self.memory.will_someone_else_take(
            trick.played_cards, players_after
        )

        # yes aj maybe → hoď nebezpečnú kartu
        # Priorita 1: horník
        specials = [c for c in playable if c.is_special]
        if specials:
            card = max(specials, key=lambda c: 8 if c.is_leaf_over else 4)
            self._log(Strategy.DUMP_SPECIAL, f"{takes}: {card}")
            return card

        # Priorita 2: najvyššia červeň
        hearts = [c for c in playable if c.suit == "heart"]
        if hearts:
            card = max(hearts, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_HEART, f"{takes}: {card}")
            return card

        # Priorita 3: trap karta (zoberiem štich ak leadujem)
        trap_playable = [
            c for c in playable
            if not c.is_special
               and c.suit != "heart"
               and self._is_trap(c)
        ]
        if trap_playable:
            card = max(trap_playable, key=lambda c: c.rank_order)
            self._log(Strategy.DUMP_DANGEROUS, f"trap: {card}")
            return card

        # Fallback: najnižšia
        card = min(playable, key=lambda c: c.rank_order)
        self._log(Strategy.WAIT, f"fallback: {card}")
        return card

    def _open_play(self, playable: list[Card],
                   hand_eval: HandEval, trick: Trick) -> Card:
        is_leader = len(trick.played_cards) == 0

        # Priorita 1: void creation (len leader) — len escape karta nie trap
        if is_leader:
            single_suit = [
                suit for suit in SUITS
                if sum(1 for c in self.player.hand.cards
                       if c.suit == suit) == 1
                   and suit != "heart"
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
                    self._log(Strategy.DUMP_SETUP, f"void: {card}")
                    return card

        # Priorita 2: najnižšia escape karta
        escape_playable = [
            c for c in hand_eval.escape_cards
            if c in playable
               and (not c.is_special or self._special_is_safe_lead(c))
        ]
        if escape_playable:
            card = min(escape_playable, key=lambda c: c.rank_order)
            self._log(Strategy.WAIT, f"escape: {card}")
            return card

        # Priorita 3: najnižšia lead karta (follower) — nie horník
        if not is_leader:
            lead_cards = [c for c in playable if c.suit == trick.lead_suit]
            non_special_lead = [c for c in lead_cards if not c.is_special]
            pool = non_special_lead if non_special_lead else lead_cards
            if pool:
                card = min(pool, key=lambda c: c.rank_order)
                self._log(Strategy.WAIT, f"wait: {card}")
                return card

        # Fallback: najnižšia non-special karta (trap je posledná možnosť)
        non_special = [
            c for c in playable
            if not c.is_special or self._special_is_safe_lead(c)
        ]
        pool = non_special if non_special else playable
        return min(pool, key=lambda c: c.rank_order)

    # ------------------------------------------------------------------
    # Post-win risk
    # ------------------------------------------------------------------

    def _evaluate_post_win_risk(self, trick: Trick) -> int:
        """
        Ak zoberiem tento štich, čo najhoršie mi môže padnúť?

        Vracia maximálne možné body (nie float ale reálne body).
        Používa worst_possible_discard z pamäte.

        Prahová hodnota pre FOLLOWER_CONTROLLED:
            <= 4b → TAKE (oplatí sa zobrať)
            >  4b → SAFE (príliš rizikové)
        """
        lead_suit = trick.lead_suit
        if not lead_suit:
            return 0

        players_after = self._get_players_after_me(trick)
        return self.memory.worst_possible_discard(lead_suit, players_after)

    # ------------------------------------------------------------------
    # Hra proti záväzku
    # ------------------------------------------------------------------

    def _play_against_declaration(self, playable: list[Card],
                                   trick: Trick,
                                   decl_type: str) -> Card | None:
        is_leader = len(trick.played_cards) == 0

        if decl_type == "all":
            current_best = self._get_current_best(trick)
            can_beat = [c for c in playable
                        if self._beats(c, current_best, trick)]
            if can_beat:
                self._log(Strategy.BREAK_ALL, "pokazím all")
                return min(can_beat, key=lambda c: c.rank_order)

        elif decl_type == "none":
            if is_leader:
                for suit in ["heart", "leaf", "acorn"]:
                    suit_cards = [c for c in playable if c.suit == suit]
                    if suit_cards:
                        self._log(Strategy.BREAK_NONE, f"tlačím: {suit}")
                        return min(suit_cards, key=lambda c: c.rank_order)
            else:
                lead_cards = [c for c in playable
                              if c.suit == trick.lead_suit]
                if lead_cards:
                    return max(lead_cards, key=lambda c: c.rank_order)
                penalty = [c for c in playable if c.is_penalty_card]
                if penalty:
                    return max(penalty, key=lambda c: c.rank_order)

        return None

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------

    def _is_trap(self, card: Card) -> bool:
        """
        Je karta trap — nikto vyšší vonku?
        Porovnáva voči remaining (súperi) aj voči vlastnej ruke.
        """
        higher_opponents = [
            c for c in self.memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        higher_own = [
            c for c in self.player.hand.cards
            if c.suit == card.suit
               and c.rank_order > card.rank_order
               and c != card
        ]
        return not higher_opponents and not higher_own

    @staticmethod
    def _trick_has_penalty(trick: Trick) -> bool:
        return trick.total_base_points > 0 or any(
            c.is_special for _, c in trick.played_cards
        )

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

    def _get_players_after_me(self, trick: Trick) -> list[int]:
        """Vráti indexy hráčov ktorí ešte nehrajú v tomto štichu."""
        played_indices = {idx for idx, _ in trick.played_cards}
        order = self._get_play_order(trick)
        return [
            i for i in order
            if i not in played_indices and i != self.player.index
        ]

    @staticmethod
    def _can_take_none(hand: list[Card]) -> bool:
        has_penalty = any(card.is_penalty_card for card in hand)
        has_special = any(card.is_special for card in hand)
        if has_penalty or has_special:
            return False
        return not any(c.rank in ("ace", "king") for c in hand)

    def _can_take_all(self, hand: list[Card]) -> bool:
        for suit in SUITS:
            suit_cards = [c for c in hand if c.suit == suit]
            if not suit_cards:
                continue
            highest_in_hand = max(suit_cards, key=lambda c: c.rank_order)
            unplayed = [c for c in self.memory.get_remaining(suit)
                        if c not in hand]
            if not unplayed:
                continue
            highest_unplayed = max(unplayed, key=lambda c: c.rank_order)
            if highest_in_hand.rank_order < highest_unplayed.rank_order:
                return False
        return True

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

    # ------------------------------------------------------------------
    # Verejné rozhranie — pamäť
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