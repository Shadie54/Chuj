# game/ai_v2/context.py

from dataclasses import dataclass
from game.card import Card
from game.trick import Trick
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval, GameContext, DecisionContext


# ------------------------------------------------------------------
# TrickOutcome — trojstav namiesto can_be_beaten + i_will_likely_win
# ------------------------------------------------------------------

class TrickOutcome:
    CERTAIN  = "CERTAIN"   # zoberiem štich na 100%
    UNKNOWN  = "UNKNOWN"   # neviem
    NEVER    = "NEVER"     # nezoberiem na 100%


def compute_trick_outcome(
    lead_cards: list[Card],
    players_after: list[int],
    trick: Trick,
    memory: AIMemory
) -> str:
    """
    Vypočíta trojstav TrickOutcome pre aktuálnu pozíciu.

    CERTAIN  — mám jedinú lead kartu a nikto vyšší neexistuje v remaining ani v štichu
    NEVER    — existuje vyššia karta v remaining a hráč po mne nie je void → niekto ma prebije
    UNKNOWN  — všetky ostatné prípady
    """
    non_special_lead = [c for c in lead_cards if not c.is_special]
    lead_cards = non_special_lead if non_special_lead else lead_cards

    if not lead_cards:
        return TrickOutcome.UNKNOWN

        # Ak som posledný — nikto po mne nehrá → len CERTAIN alebo NEVER
    is_last = len(players_after) == 0
    if is_last:
        # Mám kartu ktorá vyhráva štich?
        current_best = None
        if trick.played_cards:
            winner_idx = trick.get_winner_index()
            for idx, card in trick.played_cards:
                if idx == winner_idx:
                    current_best = card
                    break
        if current_best is None:
            return TrickOutcome.CERTAIN
        # Mám aspoň jednu kartu vyššiu než current_best?
        can_win = any(
            c.rank_order > current_best.rank_order
            for c in lead_cards
        )
        return TrickOutcome.CERTAIN if can_win else TrickOutcome.NEVER

    trick_suit_cards = [c for _, c in trick.played_cards if c.suit == lead_cards[0].suit]

    # CERTAIN — mám najvyššiu kartu, nikto ma neprebije
    my_highest = max(lead_cards, key=lambda c: c.rank_order)
    higher_remaining = [
        c for c in memory.remaining[my_highest.suit]
        if c.rank_order > my_highest.rank_order
           and c not in lead_cards
    ]
    higher_in_trick = [
        c for c in trick_suit_cards
        if c.rank_order > my_highest.rank_order
    ]
    if not higher_remaining and not higher_in_trick:
        return TrickOutcome.CERTAIN

    # NEVER — niekto ma určite prebije aj moju najnižšiu
    # (len ak som leader — inak nevieme, či vyššiu kartu drží práve
    # hráč po mne, alebo niekto kto už do štichu odohral)
    if not trick.played_cards:
        my_lowest = min(lead_cards, key=lambda c: c.rank_order)
        higher_remaining = [
            c for c in memory.remaining[my_lowest.suit]
            if c.rank_order > my_lowest.rank_order
               and c not in lead_cards
        ]
        if higher_remaining:
            non_void_after = [
                p for p in players_after
                if my_lowest.suit not in memory.void_suits[p]
            ]
            if non_void_after:
                return TrickOutcome.NEVER

    return TrickOutcome.UNKNOWN

    return TrickOutcome.UNKNOWN

def card_outcome(card: Card, trick: Trick, memory: AIMemory,
                 players_after: list[int]) -> str:
    """
    Vypočíta TrickOutcome pre konkrétnu kartu.
    """
    trick_suit_cards = [c for _, c in trick.played_cards if c.suit == card.suit]

    # Ak karta nie je v lead suit → nevyhráva štich
    if trick.lead_suit and card.suit != trick.lead_suit:
        return TrickOutcome.NEVER

    # Ak štich je prázdny (som leader) — current_best neexistuje
    # Karta môže vyhrať alebo nevyhrať → UNKNOWN ak existujú vyššie karty
    if not trick.played_cards:
        higher_remaining = [
            c for c in memory.remaining[card.suit]
            if c.rank_order > card.rank_order
        ]
        if not higher_remaining:
            return TrickOutcome.CERTAIN
        return TrickOutcome.UNKNOWN

    # Current best
    current_best = None
    if trick.played_cards:
        winner_idx = trick.get_winner_index()
        for idx, c in trick.played_cards:
            if idx == winner_idx:
                current_best = c
                break

    # Karta neprebije current_best → NEVER
    if current_best and card.rank_order <= current_best.rank_order:
        return TrickOutcome.NEVER

    # Posledný hráč: karta prebíja current_best → CERTAIN, netreba
    # kontrolovať remaining (súper mohol mať viac kariet farby a zahral
    # len jednu — tie v remaining nie sú súčasťou tohto štichu)
    if not players_after:
        return TrickOutcome.CERTAIN

    # Nikto vyšší vonku → CERTAIN
    higher_remaining = [
        c for c in memory.remaining[card.suit]
        if c.rank_order > card.rank_order
    ]
    higher_in_trick = [
        c for c in trick_suit_cards
        if c.rank_order > card.rank_order
    ]
    if not higher_remaining and not higher_in_trick:
        return TrickOutcome.CERTAIN

    # Niekto vyšší existuje + hráč po mne nie je void → NEVER
    # (len ak som leader — inak nevieme, či vyššiu kartu drží práve
    # hráč po mne, alebo niekto kto už do štichu odohral)
    if not trick.played_cards:
        non_void_after = [
            p for p in players_after
            if card.suit not in memory.void_suits[p]
        ]
        if non_void_after:
            return TrickOutcome.NEVER

    return TrickOutcome.UNKNOWN

# ------------------------------------------------------------------
# AIContext — zabalenie všetkých kontextov pre stratégie
# ------------------------------------------------------------------

@dataclass
class AIContext:
    # Existujúce kontexty — nezmenené
    decision: DecisionContext
    game: GameContext

    # Pohodlné skratky — vypočítané pri build()
    trick_cards: list[Card]       # karty v aktuálnom štichu
    current_best: Card | None     # aktuálny víťaz štichu

    # Trojstav
    trick_outcome: str            # TrickOutcome.CERTAIN / UNKNOWN / NEVER

    @staticmethod
    def build(
        player: Player,
        memory: AIMemory,
        hand_eval: HandEval,
        game_ctx: GameContext,
        playable: list[Card],
        trick: Trick
    ) -> "AIContext":

        # Zostav DecisionContext štandardnou cestou
        decision = DecisionContext.build(
            player, memory, hand_eval, game_ctx, playable, trick
        )

        # Karty v štichu
        trick_cards = [c for _, c in trick.played_cards]

        # Aktuálny víťaz štichu
        current_best: Card | None = None
        if trick.played_cards:
            winner_idx = trick.get_winner_index()
            for idx, card in trick.played_cards:
                if idx == winner_idx:
                    current_best = card
                    break

        # Trojstav
        trick_outcome = compute_trick_outcome(
            decision.lead_cards,
            decision.players_after,
            trick,
            memory
        )

        return AIContext(
            decision=decision,
            game=game_ctx,
            trick_cards=trick_cards,
            current_best=current_best,
            trick_outcome=trick_outcome,
        )

    # ------------------------------------------------------------------
    # Pohodlné skratky pre stratégie
    # ------------------------------------------------------------------

    @property
    def is_leader(self) -> bool:
        return self.decision.is_leader

    @property
    def is_last(self) -> bool:
        return self.decision.is_last

    @property
    def is_void(self) -> bool:
        return not self.decision.lead_cards

    @property
    def lead_suit(self) -> str | None:
        return self.decision.lead_suit

    @property
    def lead_cards(self) -> list[Card]:
        return self.decision.lead_cards

    @property
    def playable(self) -> list[Card]:
        return self.decision.playable

    @property
    def someone_takes(self) -> str:
        return self.decision.someone_takes

    @property
    def trick_has_penalty(self) -> bool:
        return self.decision.trick_has_penalty

    @property
    def is_high_score(self) -> bool:
        return self.game.is_high_score

    @property
    def all_scores(self) -> list[int]:
        return self.game.all_scores