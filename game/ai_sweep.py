# game/ai_sweep.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_hand_eval import HandEval
from config import SUITS, NUM_PLAYERS


# ------------------------------------------------------------------
# Enums — stavy a výstupy
# ------------------------------------------------------------------

class SweepState(Enum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    COMMITTED_SAFE = "COMMITTED_SAFE"
    COMMITTED_FULL = "COMMITTED_FULL"


class SweepDecision(Enum):
    YES = "ÁNO"
    WATCHING = "WATCHING"
    NO = "NIE"


# ------------------------------------------------------------------
# Dataclasses — výstupy vrstiev
# ------------------------------------------------------------------

@dataclass
class Layer1Result:
    passed: bool
    max_state: str          # "WATCHING" | "COMMITTED"
    scenario: str           # "hearts-driven" | "control-driven" | "hornik-bait"
    reason: str = ""        # prečo prepadol (ak passed=False)


@dataclass
class SuitEval:
    suit: str
    control: int            # guaranteed wins
    length: int             # počet kariet v ruke
    cards_outside: int      # žijúce karty vonku
    risk_points: int        # body vonku v tejto farbe
    # Hearts specific
    high_heart_count: int = 0
    low_heart_count: int = 0
    consecutive_top: int = 0
    # Leaf/Acorn specific
    hornik_owner: str = "unknown"   # "me" | "opponent" | "unknown" | "gone"
    hornik_lit: bool = False
    hornik_capturable: bool = False


@dataclass
class Layer2Result:
    passed: bool
    strength: str           # "STRONG" | "MEDIUM" | "WEAK"
    profile: str            # "HEARTS_DRIVEN" | "CONTROL_DRIVEN" | "MIXED" | "HORNIK_BAIT"
    per_suit: dict[str, SuitEval] = field(default_factory=dict)
    weaknesses: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommended_state: str = "NIE"  # "NIE" | "WATCHING" | "pokračuj"


@dataclass
class SweepResult:
    decision: SweepDecision
    state: SweepState
    recommended_card: Card | None
    sweep_probability: float = 0.0
    expected_value: float = 0.0
    reasoning_chain: list[str] = field(default_factory=list)
    escape_plan: list[str] = field(default_factory=list)

@dataclass
class SuitTimeline:
    suit: str
    guaranteed_wins: int
    conditional_wins: int
    risky_tricks: int
    cards_to_clear: int  # koľko štichov potrebujem na vyčistenie farby
    void_creation_round: int  # kedy budem void (ak vôbec)

@dataclass
class CrossSuitAnalysis:
    lead_retention_estimate: int  # % šanca že udržím lead
    forced_void_risks: list[str]  # farby kde hrozí forced void
    discard_options: list[Card]  # karty ktoré môžem bezpečne odhodiť

@dataclass
class CriticalEvent:
    event: str
    event_type: str  # "card_falls" | "distribution" | "order"
    probability: float = 0.0  # doplní Vrstva 4

@dataclass
class Layer3Result:
    passed: bool
    per_suit_timeline: dict[str, SuitTimeline]
    cross_suit: CrossSuitAnalysis
    critical_events: list[CriticalEvent]
    recommended_lead_order: list[str]  # odporúčané poradie farieb
    reason: str = ""
@dataclass
class CardLocationProb:
    card: Card
    probabilities: dict[int, float]  # player_index → pravdepodobnosť

@dataclass
class DistributionProb:
    suit: str
    cards_outside: int
    ideal_per_opponent: float
    p_favorable: float  # P(rozdelenie priaznivé pre sweep)
    worst_case_one_opponent: int  # max kariet u jedného súpera

@dataclass
class Layer4Result:
    passed: bool
    card_locations: dict[str, CardLocationProb]  # card_str → prob
    distribution_probs: dict[str, DistributionProb]  # suit → prob
    critical_event_probs: list[CriticalEvent]  # s doplnenými pravdepodobnosťami
    reason: str = ""

@dataclass
class CandidateResult:
    first_card: Card
    sweep_probability: float
    critical_events_status: list[CriticalEvent]
    failure_modes: list[str]


@dataclass
class Layer5Result:
    passed: bool
    candidates: list[CandidateResult]
    best_candidate: CandidateResult | None
    reason: str = ""

@dataclass
class EscapeRoute:
    card: Card
    quality: str        # "CLEAN" | "CONTAINED" | "MESSY" | "DISASTER"
    damage: int         # body ktoré stratím ak escape použijem
    description: str


@dataclass
class CandidateEvaluation:
    first_card: Card
    sweep_probability: float
    escape_quality: str
    expected_value: float
    commit_type: str    # "COMMITTED_FULL" | "COMMITTED_SAFE" | "WATCHING" | "NIE"
    escape_plan: list[str]


@dataclass
class Layer6Result:
    passed: bool
    evaluations: list[CandidateEvaluation]
    best_candidate: CandidateEvaluation | None
    recommended_state: str
    reason: str = ""
# ------------------------------------------------------------------
# SweepPipeline
# ------------------------------------------------------------------

class SweepPipeline:
    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

        # Stav medzi štichmi
        self.state: SweepState = SweepState.IDLE
        self.committed_card: Card | None = None

    def _log(self, strategy: str, details: str = ""):
        if self.logger:
            self.logger.log_strategy(self.player.name, strategy, details)

    def reset(self):
        self.state = SweepState.IDLE
        self.committed_card = None

    # ------------------------------------------------------------------
    # Hlavný vstupný bod
    # ------------------------------------------------------------------

    def evaluate(self, hand_eval: HandEval,
                 trick_number: int) -> SweepResult:

        reasoning = []

        # --- VRSTVA 1 ---
        l1 = self._layer1(trick_number)
        reasoning.append(
            f"L1: {l1.scenario if l1.passed else 'FAIL — ' + l1.reason}"
        )
        if not l1.passed:
            self._transition(SweepState.IDLE)
            return SweepResult(
                decision=SweepDecision.NO,
                state=SweepState.IDLE,
                recommended_card=None,
                reasoning_chain=reasoning
            )

        # --- VRSTVA 2 ---
        l2 = self._layer2(hand_eval)
        reasoning.append(
            f"L2: strength={l2.strength}, profile={l2.profile}"
        )
        if not l2.passed:
            target = (SweepState.WATCHING
                      if l2.recommended_state == "WATCHING"
                      else SweepState.IDLE)
            self._transition(target)
            return SweepResult(
                decision=(SweepDecision.WATCHING
                          if l2.recommended_state == "WATCHING"
                          else SweepDecision.NO),
                state=target,
                recommended_card=None,
                reasoning_chain=reasoning
            )

        # --- VRSTVA 3 ---
        l3 = self._layer3(l2, trick_number)
        reasoning.append(
            f"L3: passed={l3.passed}, "
            f"lead_order={l3.recommended_lead_order}, "
            f"critical_events={len(l3.critical_events)}"
        )
        if not l3.passed:
            self._transition(SweepState.IDLE)
            return SweepResult(
                decision=SweepDecision.NO,
                state=SweepState.IDLE,
                recommended_card=None,
                reasoning_chain=reasoning
            )

        # --- VRSTVA 4 ---
        l4 = self._layer4(l2, l3)
        reasoning.append(
            f"L4: passed={l4.passed}, "
            f"critical_events={[(e.event, round(e.probability, 2)) for e in l4.critical_event_probs]}"
        )
        if not l4.passed:
            self._transition(SweepState.IDLE)
            return SweepResult(
                decision=SweepDecision.NO,
                state=SweepState.IDLE,
                recommended_card=None,
                reasoning_chain=reasoning
            )
        # --- VRSTVA 5 ---
        l5 = self._layer5(hand_eval, l2, l3, l4)
        reasoning.append(
            f"L5: passed={l5.passed}, "
            f"best_card={l5.best_candidate.first_card if l5.best_candidate else None}, "
            f"P(sweep)={l5.best_candidate.sweep_probability if l5.best_candidate else 0}"
        )
        if not l5.passed:
            self._transition(SweepState.WATCHING
                             if l5.best_candidate
                                and l5.best_candidate.sweep_probability >= 0.3
                             else SweepState.IDLE)
            return SweepResult(
                decision=SweepDecision.WATCHING
                if l5.best_candidate
                   and l5.best_candidate.sweep_probability >= 0.3
                else SweepDecision.NO,
                state=self.state,
                recommended_card=None,
                reasoning_chain=reasoning
            )

        # --- VRSTVA 6 ---
        l6 = self._layer6(l3, l4, l5)
        reasoning.append(
            f"L6: passed={l6.passed}, "
            f"best={l6.best_candidate.first_card if l6.best_candidate else None}, "
            f"EV={l6.best_candidate.expected_value if l6.best_candidate else None}, "
            f"escape={l6.best_candidate.escape_quality if l6.best_candidate else None}"
        )
        if not l6.passed:
            self._transition(SweepState.WATCHING
                             if l6.recommended_state == "WATCHING"
                             else SweepState.IDLE)
            return SweepResult(
                decision=SweepDecision.WATCHING
                if l6.recommended_state == "WATCHING"
                else SweepDecision.NO,
                state=self.state,
                recommended_card=None,
                reasoning_chain=reasoning
            )

        # --- VRSTVA 7 ---
        decision, new_state, recommended_card = self._layer7(l1, l2, l5, l6)
        reasoning.append(
            f"L7: decision={decision.value}, "
            f"state={new_state.value}, "
            f"card={recommended_card}"
        )
        self._transition(new_state)

        return SweepResult(
            decision=decision,
            state=new_state,
            recommended_card=recommended_card,
            sweep_probability=l5.best_candidate.sweep_probability
            if l5.best_candidate else 0.0,
            expected_value=l6.best_candidate.expected_value
            if l6.best_candidate else 0.0,
            reasoning_chain=reasoning
        )

    # ------------------------------------------------------------------
    # VRSTVA 1: HARD GATES
    # ------------------------------------------------------------------

    def _layer1(self, trick_number: int) -> Layer1Result:
        """
        Lacné deterministické kontroly.
        Poradie: Gate1 → Gate4 → Gate2 → Gate3
        """
        hand = self.player.hand.cards

        # Gate 1: Žiadny súper nezískal trestnú kartu
        result = self._gate1_no_opponent_penalty()
        if not result[0]:
            return Layer1Result(
                passed=False,
                max_state="WATCHING",
                scenario="",
                reason=result[1]
            )

        # Gate 4: Phase constraint
        max_state = self._gate4_phase_constraint(trick_number)

        # Gate 2: Minimálna sila ruky
        scenario = self._gate2_min_hand_strength(hand)
        if scenario is None:
            return Layer1Result(
                passed=False,
                max_state=max_state,
                scenario="",
                reason="gate2: žiadny scenár nesplnený"
            )

        # Gate 3: Lethal void
        lethal = self._gate3_lethal_void(hand)
        if lethal:
            return Layer1Result(
                passed=False,
                max_state=max_state,
                scenario=scenario,
                reason="gate3: lethal void"
            )

        return Layer1Result(
            passed=True,
            max_state=max_state,
            scenario=scenario
        )

    def _gate1_no_opponent_penalty(self) -> tuple[bool, str]:
        # Trestné karty v mojej ruke (ešte nezobral som ich v štichu)
        hand = self.player.hand.cards
        my_hand_penalty = sum(
            1 for c in hand
            if c.suit == "heart"
            or (c.is_special and c.suit in ("leaf", "acorn"))
        )

        # Remaining penalty u súperov
        remaining_penalty = len(self.memory.remaining["heart"])
        if not self.memory.is_special_gone("leaf"):
            # Je horník v mojej ruke alebo u súperov?
            i_have_leaf = any(
                c.is_special and c.suit == "leaf" for c in hand
            )
            if not i_have_leaf:
                remaining_penalty += 1
        if not self.memory.is_special_gone("acorn"):
            i_have_acorn = any(
                c.is_special and c.suit == "acorn" for c in hand
            )
            if not i_have_acorn:
                remaining_penalty += 1

        # Moje zozbierané penalty karty (zo štichov)
        my_taken_penalty = len(self.player.penalty_cards)

        # Total = moja ruka + remaining + zozbierané
        total_accounted = my_hand_penalty + remaining_penalty + my_taken_penalty

        # Already taken by others = čo chýba
        # Celkové trestné karty v hre
        total_in_game = 10  # 8 hearts + 2 horníci
        already_taken_by_others = total_in_game - total_accounted

        if self.logger:
            self.logger.log_strategy(
                self.player.name,
                "SWEEP_GATE1_DEBUG",
                f"hand_penalty={my_hand_penalty}, remaining={remaining_penalty}, "
                f"my_taken={my_taken_penalty}, already_taken={already_taken_by_others}"
            )

        if already_taken_by_others > 0:
            return False, f"gate1: súper má {already_taken_by_others} trestných kariet"

        return True, ""

    @staticmethod
    def _gate4_phase_constraint(trick_number: int) -> str:
        """Vráti max_state podľa fázy hry."""
        if trick_number <= 1:
            return "WATCHING"
        return "COMMITTED"

    def _gate2_min_hand_strength(self, hand: list[Card]) -> str | None:
        """
        Overí minimálnu silu ruky.
        Vracia scenár alebo None ak nesplnené.
        """
        hearts = [c for c in hand if c.suit == "heart"]
        heart_remaining = self.memory.remaining["heart"]
        all_hearts_alive = hearts + heart_remaining
        if all_hearts_alive:
            highest_alive = max(all_hearts_alive, key=lambda c: c.rank_order)
            i_have_highest = highest_alive in hearts
        else:
            i_have_highest = False

        # Scenár 2a: Hearts-driven
        if i_have_highest:
            return "hearts-driven"

        # Scenár 2b: Control-driven
        if not hearts:
            # Mám kontrolu v non-heart farbách?
            for suit in ("leaf", "acorn", "bell"):
                suit_cards = [c for c in hand if c.suit == suit]
                remaining = self.memory.remaining[suit]
                all_alive = suit_cards + remaining
                if all_alive:
                    highest = max(all_alive, key=lambda c: c.rank_order)
                    if highest in suit_cards:
                        return "control-driven"

        # Scenár 2c: Horník-bait
        for suit in ("leaf", "acorn"):
            special = next(
                (c for c in hand if c.is_special and c.suit == suit), None
            )
            if special:
                high_in_suit = [
                    c for c in hand
                    if c.suit == suit
                       and not c.is_special
                       and c.rank in ("ace", "king")
                ]
                if not high_in_suit:
                    return "hornik-bait"

        return None

    def _gate3_lethal_void(self, hand: list[Card]) -> bool:
        """
        Lethal void = scenár kde matematicky NIE JE možné zobrať všetky
        trestné karty.

        V1 (pôvodná) kontrolovala: void v farbe + trestné karty vonku → fail.
        Ale to je príliš agresívne — AI s dobrou kontrolou v iných farbách
        môže void farbu vynútiť cez sub-leaders, alebo súperi sami môžu
        viesť tú farbu a my chytíme cez horníka.

        V2 (aktuálna): vypnuté. Sweep šance ohodnotí L4/L5/L7 cez reálne
        pravdepodobnosti. L1 zostáva len na fyzicky nemožné scenáre
        (Gate 1, Gate 2, Gate 4).
        """
        return False

    # ------------------------------------------------------------------
    # VRSTVA 2: HAND EVALUATION
    # ------------------------------------------------------------------

    def _layer2(self, hand_eval: HandEval) -> Layer2Result:
        """
        Per-suit hodnotenie + agregácia do hand summary.
        """
        hand = self.player.hand.cards
        per_suit = {}

        for suit in SUITS:
            per_suit[suit] = self._evaluate_suit(suit, hand)

        strength, profile, weaknesses, strengths = \
            self._hand_summary(per_suit)

        if strength == "WEAK":
            return Layer2Result(
                passed=False,
                strength=strength,
                profile=profile,
                per_suit=per_suit,
                weaknesses=weaknesses,
                strengths=strengths,
                recommended_state="NIE"
            )

        if strength == "MEDIUM":
            # MEDIUM teraz pokračuje k Layer 3+, ale finálny stav bude
            # downgradnutý na WATCHING v Layer 7 (cez recommended_state).
            # Tým dostane Layer 3 šancu vyradiť scenár ako úplne nemožný
            # (napr. uncapturable horník u súpera).
            return Layer2Result(
                passed=True,
                strength=strength,
                profile=profile,
                per_suit=per_suit,
                weaknesses=weaknesses,
                strengths=strengths,
                recommended_state="WATCHING"
            )

        # STRONG → pokračuj
        return Layer2Result(
            passed=True,
            strength=strength,
            profile=profile,
            per_suit=per_suit,
            weaknesses=weaknesses,
            strengths=strengths,
            recommended_state="pokračuj"
        )

    def _evaluate_suit(self, suit: str, hand: list[Card]) -> SuitEval:
        """Vyhodnotí jednu farbu."""
        my_cards = [c for c in hand if c.suit == suit]
        remaining = self.memory.remaining[suit]

        # Guaranteed wins — koľko najvyšších v rade mám ja
        all_alive = sorted(
            my_cards + remaining,
            key=lambda c: c.rank_order,
            reverse=True
        )
        control = 0
        for card in all_alive:
            if card in my_cards:
                control += 1
            else:
                break

        # Risk points
        risk = 0
        leaf_lit = self.memory.illuminated_by.get("leaf") is not None
        acorn_lit = self.memory.illuminated_by.get("acorn") is not None
        both_lit = leaf_lit and acorn_lit

        if suit == "heart":
            multiplier = 2 if both_lit else 1
            risk = len(remaining) * multiplier
        elif suit == "leaf":
            if not self.memory.is_special_gone("leaf"):
                risk = 16 if leaf_lit else 8
        elif suit == "acorn":
            if not self.memory.is_special_gone("acorn"):
                risk = 8 if acorn_lit else 4

        # Hearts specific
        high_heart_count = 0
        low_heart_count = 0
        consecutive_top = 0

        if suit == "heart":
            high_heart_count = sum(
                1 for c in my_cards
                if c.rank in ("ace", "king", "queen", "under", "ten")
            )
            low_heart_count = sum(
                1 for c in my_cards
                if c.rank in ("seven", "eight", "nine")
            )
            # Consecutive top
            all_alive_sorted = sorted(
                my_cards + remaining,
                key=lambda c: c.rank_order,
                reverse=True
            )
            for card in all_alive_sorted:
                if card in my_cards:
                    consecutive_top += 1
                else:
                    break

        # Leaf/Acorn specific
        hornik_owner = "unknown"
        hornik_lit = False
        hornik_capturable = False

        if suit in ("leaf", "acorn"):
            if self.memory.is_special_gone(suit):
                # Kto ho zobral?
                my_penalty = [c for c in self.player.penalty_cards
                              if c.is_special and c.suit == suit]
                hornik_owner = "me" if my_penalty else "opponent"
            else:
                illuminated_by = self.memory.illuminated_by.get(suit)
                if illuminated_by is not None:
                    hornik_owner = ("me" if illuminated_by == self.player.index
                                    else "opponent")
                    hornik_lit = True
                else:
                    my_special = any(
                        c.is_special and c.suit == suit for c in my_cards
                    )
                    hornik_owner = "me" if my_special else "unknown"

            hornik_capturable = any(
                c.rank in ("ace", "king") for c in my_cards
                if not c.is_special
            )

        return SuitEval(
            suit=suit,
            control=control,
            length=len(my_cards),
            cards_outside=len(remaining),
            risk_points=risk,
            high_heart_count=high_heart_count,
            low_heart_count=low_heart_count,
            consecutive_top=consecutive_top,
            hornik_owner=hornik_owner,
            hornik_lit=hornik_lit,
            hornik_capturable=hornik_capturable
        )

    def _count_heart_killers(self, hand: list[Card]) -> int:
        """
        Spočíta hearts v ruke ktoré reálne NEvyhrajú (sú killer).

        Killer = moja heart ktorá nie je win cez extended trick-by-trick
        simuláciu (smart súperi šetria vyššie karty, takže moja stredná
        karta môže prehrať keď vyššie cudzie zostávajú v hre).

        Konzistentné s _suit_extended_wins ktoré počíta capacity.

        Príklad: my=[A, K, 9], outside=[Q, J, 10, 8, 7]
        - extended wins = 3 (A vyžerie 7,8,10; K vyžerie Q+J; 9 je top)
        - killers = 3 - 3 = 0

        Príklad: my=[K, 10], outside=[A, Q, J, 9, 8, 7]
        - extended wins = 0 (A je vonku, K nie je top)
        - killers = 2 - 0 = 2

        Príklad: my=[A, 10], outside=[K, Q, J, 9, 8, 7]
        - extended wins = 1 (A vyžerie 7,8,9; 10 nie je top, KQJ vonku)
        - killers = 2 - 1 = 1
        """
        my_hearts = [c for c in hand if c.suit == "heart"]
        if not my_hearts:
            return 0

        hearts_outside = self.memory.remaining["heart"]
        wins = self._suit_extended_wins(my_hearts, hearts_outside)
        return len(my_hearts) - wins

    def _compute_remaining_to_capture(self, hand: list[Card]) -> int:
        """
        Spočíta koľko trestných bodov ZOSTÁVA chytiť pre úplný sweep.

        Ignoruje karty ktoré som už zachytil (sú v `player.penalty_cards`)
        — tie sú v safe.

        Počíta:
        - hearts vonku × 1 (alebo × 2 ak obaja horníci vysvietení)
        - leaf horník vonku × 8 (alebo × 16 vysvietený) AK ho neviem zobrať
        - acorn horník vonku × 4 (alebo × 8 vysvietený) AK ho neviem zobrať

        "Viem zobrať" = mám ho v ruke ALEBO mám aspoň 1 win v tej farbe.
        """
        leaf_lit = self.memory.illuminated_by.get("leaf") is not None
        acorn_lit = self.memory.illuminated_by.get("acorn") is not None
        both_lit = leaf_lit and acorn_lit

        # Hearts vonku
        hearts_outside_count = len(self.memory.remaining["heart"])
        heart_multiplier = 2 if both_lit else 1
        hearts_pts = hearts_outside_count * heart_multiplier

        # Leaf horník
        leaf_pts = 0
        if not self.memory.is_special_gone("leaf"):
            i_have_leaf_q = any(c.is_leaf_over for c in hand)
            my_leaf_cards = [c for c in hand if c.suit == "leaf"]
            leaf_remaining = self.memory.remaining["leaf"]
            # Mám control v leaf? (najvyššie alive karty sú moje)
            leaf_control = self._suit_control_count(my_leaf_cards, leaf_remaining)

            if not i_have_leaf_q and leaf_control == 0:
                # Nemám Q♠ ani control → riskantné, ráta sa do remaining
                leaf_pts = 16 if leaf_lit else 8

        # Acorn horník
        acorn_pts = 0
        if not self.memory.is_special_gone("acorn"):
            i_have_acorn_q = any(c.is_acorn_over for c in hand)
            my_acorn_cards = [c for c in hand if c.suit == "acorn"]
            acorn_remaining = self.memory.remaining["acorn"]
            acorn_control = self._suit_control_count(my_acorn_cards, acorn_remaining)

            if not i_have_acorn_q and acorn_control == 0:
                acorn_pts = 8 if acorn_lit else 4

        return hearts_pts + leaf_pts + acorn_pts

    @staticmethod
    def _suit_control_count(my_cards: list[Card],
                            remaining: list[Card]) -> int:
        """
        Spočíta koľko najvyšších v rade kariet danej farby je MOJICH.
        (Guaranteed wins — pokým je v rade, vyhrám lead-om tej farby.)
        """
        all_alive = sorted(
            my_cards + remaining,
            key=lambda c: c.rank_order,
            reverse=True,
        )
        count = 0
        for card in all_alive:
            if card in my_cards:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _suit_extended_wins(my_cards: list[Card],
                            remaining: list[Card]) -> int:
        """
        Realisticky spočíta koľko štichov vyhrám v danej farbe.

        Trick-by-trick simulácia:
        - Postupne vediem moju top alive kartu
        - Každý win vyžerie 3 najnižšie outside karty
          (predpoklad: smart súperi šetria vyššie karty)
        - Karta vyhrá keď je top alive v moment hraní

        Príklad: my=[A, K, 9], outside=[Q, J, 10, 8, 7]
        - A je top → win, outside=[Q] (vyžrali 7,8,10)
        - K je top alive (K>Q) → win, outside=[]
        - 9 je top alive (jediná) → win
        Wins = 3

        Príklad: my=[K, 10], outside=[A, Q, J, 9, 8, 7]
        - K nie je top (A vyššia) → nemôžem viesť, break
        - 10 nemôžem testovať
        Wins = 0 (cudzia A je vždy nad K)

        Použitie: pre hearts (chytá priamo) aj non-heart (generuje discardy).
        """
        my_remaining = sorted(my_cards, key=lambda c: c.rank_order, reverse=True)
        outside_remaining = list(remaining)

        wins = 0
        while my_remaining:
            all_alive = my_remaining + outside_remaining
            if not all_alive:
                break

            top_card = max(all_alive, key=lambda c: c.rank_order)

            if top_card in my_remaining:
                wins += 1
                my_remaining.remove(top_card)
                # Vyžerem 3 najnižšie outside (smart súperi šetria vyššie)
                outside_remaining = sorted(
                    outside_remaining, key=lambda c: c.rank_order
                )[3:]
            else:
                # Cudzia karta je top alive — moje budú prehrávať
                # Konzervatívne: prerušujem (žiadne ďalšie wins už nepripočítam)
                break

        return wins

    def _compute_total_capacity(self, hand: list[Card]) -> int:
        """
        Spočíta celkovú schopnosť chytiť zostávajúce trestné karty.

        Používa _suit_extended_wins (trick-by-trick simulácia) namiesto
        _suit_control_count, aby zachytila aj wins typu "moja nízka
        karta vyhrá keď padnú vyššie".

        Hearts wins × 4 — chytajú hearts priamo (1 moja + 3 cudzie).
        Non-heart wins × 2 — generujú discardy (konzervatívne).
        """
        hearts_wins = self._suit_extended_wins(
            [c for c in hand if c.suit == "heart"],
            self.memory.remaining["heart"],
        )
        hearts_coverage = hearts_wins * 4

        non_heart_wins = 0
        for suit in ("leaf", "acorn", "bell"):
            my_cards = [c for c in hand if c.suit == suit]
            remaining = self.memory.remaining[suit]
            non_heart_wins += self._suit_extended_wins(my_cards, remaining)
        non_heart_coverage = non_heart_wins * 2

        return hearts_coverage + non_heart_coverage

    def _hand_summary(self, per_suit: dict[str, SuitEval]) -> tuple:
        """
        Agreguje per-suit hodnotenia do hand summary.

        Nový adaptívny model:
        - capacity = koľko discardov môžem vynútiť cez wins
        - to_capture = koľko trestných bodov ostáva chytiť (ignoruje my_taken)
        - heart_killers = počet mojich hearts ktoré ma môžu potopiť (pesimistický)

        STRONG: ratio >= 1.5 a 0 heart killers
        MEDIUM: ratio >= 1.0 a <= 1 heart killer
        WEAK: inak

        Vracia (strength, profile, weaknesses, strengths).
        """
        weaknesses = []
        strengths = []

        hand = self.player.hand.cards

        # --- Adaptívne metriky ---
        capacity = self._compute_total_capacity(hand)
        to_capture = self._compute_remaining_to_capture(hand)
        heart_killers = self._count_heart_killers(hand)

        # Bezpečnostný margin (ratio)
        if to_capture == 0:
            # Triviálny prípad — niet čo chytiť (všetko mám alebo padlo)
            ratio = float("inf")
        else:
            ratio = capacity / to_capture

        # --- Strength rozhodnutie ---
        if ratio >= 1.5 and heart_killers == 0:
            strength = "STRONG"
            strengths.append(f"capacity_ratio={ratio:.2f}")
            strengths.append("no_heart_killers")
        elif ratio >= 1.0 and heart_killers <= 1:
            strength = "MEDIUM"
            if heart_killers == 1:
                weaknesses.append("one_heart_killer")
            if ratio < 1.5:
                weaknesses.append(f"capacity_ratio={ratio:.2f}")
        else:
            strength = "WEAK"
            if ratio < 1.0:
                weaknesses.append(f"insufficient_capacity_{ratio:.2f}")
            if heart_killers >= 2:
                weaknesses.append(f"heart_killers={heart_killers}")

        # --- Profile detection (pre debug, neovplyvňuje strength) ---
        hearts = per_suit["heart"]
        leaf = per_suit["leaf"]
        acorn = per_suit["acorn"]

        if hearts.consecutive_top >= 2 and hearts.high_heart_count >= 3:
            profile = "HEARTS_DRIVEN"
        elif hearts.length == 0:
            profile = "CONTROL_DRIVEN"
        elif (leaf.control >= 1 or acorn.control >= 1) and hearts.consecutive_top >= 1:
            profile = "MIXED"
        else:
            profile = "HORNIK_BAIT"

        return strength, profile, weaknesses, strengths

    # ------------------------------------------------------------------
    # VRSTVA 3: SUIT CONTROL ANALYSIS
    # ------------------------------------------------------------------

    def _layer3(self, l2: Layer2Result, trick_number: int) -> Layer3Result:
        """
        Suit control analysis — timeline + critical events.
        """
        hand = self.player.hand.cards
        timelines = {}
        critical_events = []

        # --- A. Per-suit timeline ---
        for suit in SUITS:
            timelines[suit] = self._suit_timeline(suit, hand, l2.per_suit[suit])

        # --- B. Critical events ---
        # Len pre karty kde nemáme 100% garantiu
        for suit in ("leaf", "acorn"):
            suit_eval = l2.per_suit[suit]
            if suit_eval.hornik_owner == "opponent":
                # Horník u súpera → card_falls event
                critical_events.append(CriticalEvent(
                    event=f"horník {suit} musí padnúť",
                    event_type="card_falls"
                ))
            elif suit_eval.hornik_owner == "unknown":
                # Nevieme kto má horníka → card_falls event
                critical_events.append(CriticalEvent(
                    event=f"horník {suit} musí padnúť (unknown owner)",
                    event_type="card_falls"
                ))

        # Hearts distribution event len ak mám conditional wins
        hearts_tl = timelines["heart"]
        if hearts_tl.conditional_wins > 0:
            hearts_outside = l2.per_suit["heart"].cards_outside
            critical_events.append(CriticalEvent(
                event=f"hearts rozdelené — {hearts_outside} vonku",
                event_type="distribution"
            ))

        # --- C. Cross-suit analysis ---
        cross = self._cross_suit_analysis(hand, timelines, l2)

        # --- D. Odporúčané poradie farieb ---
        lead_order = self._recommend_lead_order(timelines, l2, trick_number)

        # --- E. Je sweep vôbec možný? ---
        # Ak mám 0 guaranteed wins v nejakej farbe kde je trestná karta
        # a horník je u súpera bez možnosti zobrania → impossible
        for suit in ("leaf", "acorn"):
            suit_eval = l2.per_suit[suit]
            tl = timelines[suit]
            if (suit_eval.hornik_owner == "opponent"
                    and not suit_eval.hornik_capturable
                    and tl.guaranteed_wins == 0):
                return Layer3Result(
                    passed=False,
                    per_suit_timeline=timelines,
                    cross_suit=cross,
                    critical_events=critical_events,
                    recommended_lead_order=lead_order,
                    reason=f"L3: horník {suit} u súpera, nedokážem zobrať"
                )

        return Layer3Result(
            passed=True,
            per_suit_timeline=timelines,
            cross_suit=cross,
            critical_events=critical_events,
            recommended_lead_order=lead_order
        )

    def _suit_timeline(self, suit: str, hand: list[Card],
                       suit_eval: SuitEval) -> SuitTimeline:
        """
        Vypočíta timeline pre jednu farbu.
        """
        my_cards = sorted(
            [c for c in hand if c.suit == suit],
            key=lambda c: c.rank_order,
            reverse=True
        )
        remaining = self.memory.remaining[suit]

        # Guaranteed wins — najvyššie karty v rade
        guaranteed = suit_eval.control

        # Conditional wins — karty kde môžem vyhrať
        # ak vyššie karty padnú skôr
        conditional = 0
        all_alive = sorted(
            my_cards + remaining,
            key=lambda c: c.rank_order,
            reverse=True
        )

        passed_guaranteed = 0
        for card in all_alive:
            if passed_guaranteed < guaranteed:
                if card in my_cards:
                    passed_guaranteed += 1
                continue
            # Za guaranteed zonou
            if card in my_cards:
                # Táto karta môže byť win ak vyššie padnú
                higher_remaining = [
                    c for c in remaining
                    if c.rank_order > card.rank_order
                ]
                if higher_remaining:
                    conditional += 1

        # Risky tricks — karty ktoré pravdepodobne zoberú súperi
        total_my = len(my_cards)
        risky = max(0, total_my - guaranteed - conditional)

        # Cards to clear — koľko štichov potrebujem na vyčistenie farby
        # = koľko kariet je vonku / 3 súperi (zaokrúhlené nahor)
        cards_outside = len(remaining)
        cards_to_clear = -(-cards_outside // 3) if cards_outside > 0 else 0

        # Void creation round — kedy budem void
        if not my_cards:
            void_creation_round = 0  # som už void
        else:
            void_creation_round = len(my_cards)  # po N štichoch tej farby

        return SuitTimeline(
            suit=suit,
            guaranteed_wins=guaranteed,
            conditional_wins=conditional,
            risky_tricks=risky,
            cards_to_clear=cards_to_clear,
            void_creation_round=void_creation_round
        )

    def _cross_suit_analysis(self, hand: list[Card],
                             timelines: dict[str, SuitTimeline],
                             l2: Layer2Result) -> CrossSuitAnalysis:
        """
        Analyzuje interakcie medzi farbami.
        """
        # Lead retention — ak mám guaranteed wins vo všetkých farbách
        # → lead retention je vysoký
        total_guaranteed = sum(
            tl.guaranteed_wins for tl in timelines.values()
        )
        total_my_cards = len(hand)

        # Jednoduchý odhad: % štichov kde mám garantovaný win
        if total_my_cards > 0:
            lead_retention = int(
                (total_guaranteed / total_my_cards) * 100
            )
        else:
            lead_retention = 0

        # Forced void risks — farby kde som void a sú trestné karty
        forced_void_risks = []
        for suit in ("heart", "leaf", "acorn"):
            my_suit = [c for c in hand if c.suit == suit]
            if not my_suit:
                has_penalty = (
                        suit == "heart" and self.memory.remaining["heart"]
                        or suit == "leaf" and not self.memory.is_special_gone("leaf")
                        or suit == "acorn" and not self.memory.is_special_gone("acorn")
                )
                if has_penalty:
                    forced_void_risks.append(suit)

        # Discard options — karty ktoré môžem bezpečne odhodiť
        # (nie trestné, nie potrebné na kontrolu)
        discard_options = []
        for card in hand:
            if card.suit == "heart":
                continue
            if card.is_special:
                continue
            suit_eval = l2.per_suit[card.suit]
            # Karta je discard option ak je escape (nie guaranteed win)
            if card in [c for c in hand
                        if c.suit == card.suit]:
                tl = timelines[card.suit]
                # Ak mám viac kariet ako guaranteed wins → môžem odhodiť
                my_suit_count = sum(
                    1 for c in hand if c.suit == card.suit
                )
                if my_suit_count > tl.guaranteed_wins:
                    discard_options.append(card)

        return CrossSuitAnalysis(
            lead_retention_estimate=lead_retention,
            forced_void_risks=forced_void_risks,
            discard_options=discard_options
        )

    @staticmethod
    def _recommend_lead_order(timelines: dict[str, SuitTimeline],
                              l2: Layer2Result,
                              trick_number: int) -> list[str]:
        """
        Odporúča poradie farieb pre štich sequence.

        Princíp:
        1. Najprv farby kde mám 100% kontrolu (guaranteed wins)
           → môžu pristáť trestné karty od voidov
        2. Horníkové farby (leaf/acorn) skôr ak horník u súpera
        3. Hearts neskôr — po vyčistení ostatných farieb
        4. V tricku 1 sa hearts NIKDY nevedie (pravidlo hry).
        """
        order = []

        # Farby s guaranteed wins (okrem hearts)
        non_heart_guaranteed = [
            suit for suit in ("leaf", "acorn", "bell")
            if timelines[suit].guaranteed_wins > 0
        ]
        # Zoraď podľa počtu guaranteed wins (zostupne)
        non_heart_guaranteed.sort(
            key=lambda s: timelines[s].guaranteed_wins,
            reverse=True
        )
        order.extend(non_heart_guaranteed)

        # Hearts placement — v tricku 1 ich vždy posuň na koniec
        # (pravidlo hry: v 1. štichu sa nesmie viesť červeň).
        if trick_number > 1:
            hearts_tl = timelines["heart"]
            if hearts_tl.conditional_wins == 0 and hearts_tl.guaranteed_wins > 0:
                order.insert(0, "heart")  # hearts skôr ak 100% kontrola
            else:
                order.append("heart")  # hearts neskôr
        # Pre trick 1 sa hearts pridajú až s remaining_suits na koniec.

        # Farby bez guaranteed wins na koniec
        remaining_suits = [
            s for s in SUITS
            if s not in order
        ]
        order.extend(remaining_suits)

        return order

    # ------------------------------------------------------------------
    # VRSTVA 4: Opponent modeling
    # ------------------------------------------------------------------

    def _layer4(self, l2: Layer2Result,
                l3: Layer3Result) -> Layer4Result:
        """
        Opponent modeling — pravdepodobnosti umiestnenia kariet.
        """
        hand = self.player.hand.cards
        opponents = [
            i for i in range(NUM_PLAYERS)
            if i != self.player.index
        ]

        # --- A. Card location probabilities ---
        card_locations = {}

        # Trestné karty ktoré nás zaujímajú
        penalty_cards_to_track = []

        # Hearts
        for card in self.memory.remaining["heart"]:
            penalty_cards_to_track.append(card)

        # Horníci
        for suit in ("leaf", "acorn"):
            if not self.memory.is_special_gone(suit):
                my_special = any(
                    c.is_special and c.suit == suit for c in hand
                )
                if not my_special:
                    # Horník je u súpera
                    special_card = next(
                        (c for c in self.memory.remaining[suit]
                         if c.is_special),
                        None
                    )
                    if special_card:
                        penalty_cards_to_track.append(special_card)

        for card in penalty_cards_to_track:
            probs = self._card_location_prob(card, opponents)
            card_locations[str(card)] = CardLocationProb(
                card=card,
                probabilities=probs
            )

        # --- B. Distribution probabilities ---
        distribution_probs = {}

        for suit in ("heart", "leaf", "acorn"):
            remaining = self.memory.remaining[suit]
            if not remaining:
                continue

            dist_prob = self._distribution_prob(suit, remaining, opponents)
            distribution_probs[suit] = dist_prob

        # --- C. Critical events — doplníme pravdepodobnosti ---
        updated_events = []
        for event in l3.critical_events:
            prob = self._estimate_critical_event_prob(
                event, card_locations, distribution_probs
            )
            updated_events.append(CriticalEvent(
                event=event.event,
                event_type=event.event_type,
                probability=prob
            ))

        # --- D. Je sweep stále možný? ---
        # Ak P(favorable) príliš nízka pre kritické farby → NIE
        for suit in ("heart",):
            if suit in distribution_probs:
                dist = distribution_probs[suit]
                if dist.p_favorable < 0.2:
                    return Layer4Result(
                        passed=False,
                        card_locations=card_locations,
                        distribution_probs=distribution_probs,
                        critical_event_probs=updated_events,
                        reason=f"L4: P(favorable hearts) = {dist.p_favorable:.2f} < 0.2"
                    )

        return Layer4Result(
            passed=True,
            card_locations=card_locations,
            distribution_probs=distribution_probs,
            critical_event_probs=updated_events
        )

    def _card_location_prob(self, card: Card,
                            opponents: list[int]) -> dict[int, float]:
        """
        Odhadne pravdepodobnosť že daná karta je u každého súpera.

        Default: rovnomerné rozdelenie.
        Korekcie: void suits, vysvietenie.
        """
        # Začneme s rovnomerným rozdelením
        base_prob = 1.0 / len(opponents) if opponents else 0.0
        probs = {i: base_prob for i in opponents}

        # Korekcia 1: void suits
        void_opponents = [
            i for i in opponents
            if card.suit in self.memory.void_suits[i]
        ]
        non_void_opponents = [
            i for i in opponents
            if card.suit not in self.memory.void_suits[i]
        ]

        if void_opponents:
            # Void súperi nemôžu mať túto kartu
            for i in void_opponents:
                probs[i] = 0.0

            # Prerozdelíme na non-void
            if non_void_opponents:
                redistributed = 1.0 / len(non_void_opponents)
                for i in non_void_opponents:
                    probs[i] = redistributed
            else:
                # Všetci void — karta musí byť niekde (chyba v dátach)
                for i in opponents:
                    probs[i] = base_prob

        # Korekcia 2: vysvietenie — vieme presne kto má horníka
        if card.is_special:
            illuminated_by = self.memory.illuminated_by.get(card.suit)
            if illuminated_by is not None and illuminated_by in opponents:
                # 100% u tohto súpera
                for i in opponents:
                    probs[i] = 0.0
                probs[illuminated_by] = 1.0

        # Korekcia 3: possible holders
        if card.is_special:
            possible = self.memory.who_has_special(card.suit)
            possible_opponents = [i for i in opponents if i in possible]
            if possible_opponents and len(possible_opponents) < len(opponents):
                for i in opponents:
                    probs[i] = 0.0
                for i in possible_opponents:
                    probs[i] = 1.0 / len(possible_opponents)

        return probs

    def _distribution_prob(self, suit: str,
                           remaining: list[Card],
                           opponents: list[int]) -> DistributionProb:
        """
        Odhadne pravdepodobnosť priaznivého rozdelenia kariet.

        Priaznivé = karty rozdelené čo najpravidelnejšie.
        Nepriaznivé = jeden súper má príliš veľa kariet.

        Špeciálne prípady pre málo kariet vonku — distribúcia nie je
        problém keď je vonku len 0-2 kariet.
        """
        n = len(remaining)
        n_opponents = len(opponents)

        if n_opponents == 0:
            return DistributionProb(
                suit=suit,
                cards_outside=n,
                ideal_per_opponent=0.0,
                p_favorable=1.0,
                worst_case_one_opponent=0,
            )

        active_opponents = [
            i for i in opponents
            if suit not in self.memory.void_suits[i]
        ]

        if not active_opponents:
            # Všetci void — nikto nemá túto farbu
            return DistributionProb(
                suit=suit,
                cards_outside=n,
                ideal_per_opponent=0.0,
                p_favorable=1.0,
                worst_case_one_opponent=0,
            )

        # NOVÉ: málo kariet vonku → distribúcia nie je problém
        if n == 0:
            # Žiadne karty vonku — triviálne priaznivé
            return DistributionProb(
                suit=suit,
                cards_outside=0,
                ideal_per_opponent=0.0,
                p_favorable=1.0,
                worst_case_one_opponent=0,
            )

        if n == 1:
            # Iba 1 karta vonku — môže byť u kohokoľvek z active,
            # ale jedna karta nikdy netvorí "zlé rozdelenie"
            return DistributionProb(
                suit=suit,
                cards_outside=1,
                ideal_per_opponent=1.0 / len(active_opponents),
                p_favorable=1.0,
                worst_case_one_opponent=1,
            )

        # Prerozdelenie len na active opponents
        ideal_active = n / len(active_opponents)
        worst_case = n  # všetky u jedného

        # P(favorable) — zohľadňuje aj počet active opponents aj počet kariet
        if len(active_opponents) == 1:
            # Jeden aktívny súper má všetky → distribúcia istá ale
            # otázka je či nás jeho karty môžu potopiť. Pre 1-2 karty
            # je to OK, pre veľa kariet horšie.
            if n <= 2:
                p_favorable = 0.8  # 1-2 karty u jedného hráča sa zvládnu
            elif n <= 4:
                p_favorable = 0.4  # stredné
            else:
                p_favorable = 0.1  # veľa kariet u jedného → zlé
        elif n <= len(active_opponents):
            # Každý môže mať max 1 → priaznivé
            p_favorable = 0.9
        elif n <= len(active_opponents) * 2:
            # Max 2 na súpera → celkom priaznivé
            p_favorable = 0.7
        elif n <= len(active_opponents) * 3:
            # Max 3 na súpera → stredné
            p_favorable = 0.5
        else:
            # Veľa kariet na súpera → nepriaznivé
            p_favorable = 0.3

        return DistributionProb(
            suit=suit,
            cards_outside=n,
            ideal_per_opponent=ideal_active,
            p_favorable=p_favorable,
            worst_case_one_opponent=worst_case,
        )

    @staticmethod
    def _estimate_critical_event_prob(
            event: CriticalEvent,
            card_locations: dict[str, CardLocationProb],
            distribution_probs: dict[str, DistributionProb]) -> float:
        """
        Odhadne pravdepodobnosť critical eventu.
        """
        if event.event_type == "card_falls":
            # P že karta padne = P že ju máme pod kontrolou.
            # event.event obsahuje meno suite, napr. "horník leaf musí padnúť".
            # Hľadáme card_locations podľa suite — special karty (horníci).
            # POZN: predošlá verzia robila `event.event in card_str`,
            # čo nikdy neprešlo (card_str je napr. "O♠"), takže všetky
            # card_falls eventy mali implicitne P=0.5.
            for card_str, loc in card_locations.items():
                if loc.card.is_special and loc.card.suit in event.event:
                    max_prob = max(loc.probabilities.values())
                    if max_prob >= 1.0:
                        # Vieme presne kto má → závisí od našej kontroly
                        return 0.75
                    return 0.6
            return 0.5

        elif event.event_type == "distribution":
            # Použijeme distribution_prob
            for suit, dist in distribution_probs.items():
                if suit in event.event:
                    return dist.p_favorable
            return 0.5

        elif event.event_type == "order":
            # Order events sú najťažšie odhadnúť → konzervatívny odhad
            return 0.5

        return 0.5

    # ------------------------------------------------------------------
    # VRSTVA 5: Targeted Simulation
    # ------------------------------------------------------------------
    def _layer5(self, hand_eval: HandEval,
                l2: Layer2Result,
                l3: Layer3Result,
                l4: Layer4Result) -> Layer5Result:
        """
        Targeted simulation — P(sweep) per kandidát.
        Independence assumption: P(sweep) = P(e1) × P(e2) × ... × P(eN)
        """
        hand = self.player.hand.cards

        # --- Kandidátne first cards ---
        candidates = []

        for suit in l3.recommended_lead_order:
            # POZN: Horníky (special karty) sú zahrnuté ako kandidáti.
            # V poslednom štyche/štychoch je horník často top alive
            # a jediný spôsob ako ho zachrániť pred discardom.
            my_suit_cards = sorted(
                [c for c in hand if c.suit == suit],
                key=lambda c: c.rank_order,
                reverse=True,
            )
            if not my_suit_cards:
                continue

            tl = l3.per_suit_timeline[suit]

            # Len karty kde mám guaranteed win
            if tl.guaranteed_wins == 0:
                continue

            # Najvyššia karta v tejto farbe = kandidát
            best_card = my_suit_cards[0]
            candidates.append(best_card)

            # Max 4 kandidáti
            if len(candidates) >= 4:
                break

        if not candidates:
            return Layer5Result(
                passed=False,
                candidates=[],
                best_candidate=None,
                reason="L5: žiadni kandidáti"
            )

        # --- P(sweep) pre každého kandidáta ---
        results = []
        for card in candidates:
            result = self._simulate_candidate(card, l4)
            results.append(result)

        # --- Vyber best kandidáta ---
        # Najvyššia P(sweep)
        best = max(results, key=lambda r: r.sweep_probability)

        # --- Filter podľa threshold ---
        if best.sweep_probability < 0.5:
            return Layer5Result(
                passed=False,
                candidates=results,
                best_candidate=best,
                reason=f"L5: P(sweep)={best.sweep_probability:.2f} < 0.5"
            )

        return Layer5Result(
            passed=True,
            candidates=results,
            best_candidate=best
        )

    def _simulate_candidate(self, first_card: Card,
                            l4: Layer4Result) -> CandidateResult:
        """
        Simuluje P(sweep) pre daného kandidáta.
        Independence assumption.
        """
        # Ak žiadne critical events → P(sweep) = 1.0
        if not l4.critical_event_probs:
            return CandidateResult(
                first_card=first_card,
                sweep_probability=1.0,
                critical_events_status=[],
                failure_modes=[]
            )

        # P(sweep) = produkt pravdepodobností všetkých critical events
        p_sweep = 1.0
        failure_modes = []

        for event in l4.critical_event_probs:
            p_sweep *= event.probability
            if event.probability < 0.7:
                failure_modes.append(
                    f"{event.event} → P={event.probability:.2f}"
                )

        return CandidateResult(
            first_card=first_card,
            sweep_probability=round(p_sweep, 3),
            critical_events_status=l4.critical_event_probs,
            failure_modes=failure_modes
        )

    # ------------------------------------------------------------------
    # VRSTVA 6: Escape evaluation
    # ------------------------------------------------------------------
    def _layer6(self, l3: Layer3Result,
                l4: Layer4Result,
                l5: Layer5Result) -> Layer6Result:
        """
        Escape evaluation — kvalita escape + EV výpočet.
        """
        hand = self.player.hand.cards
        evaluations = []

        for candidate in l5.candidates:
            if candidate.sweep_probability < 0.5:
                continue

            # Escape routes pre tohto kandidáta
            escape = self._find_escape(candidate, hand, l3)

            # EV = P(sweep) × benefit − (1 − P(sweep)) × damage
            sweep_benefit = -10  # sweep bonus
            ev = (candidate.sweep_probability * sweep_benefit
                  - (1 - candidate.sweep_probability) * escape.damage)

            # Commit type
            commit_type = self._determine_commit_type(
                candidate.sweep_probability,
                escape.quality
            )

            evaluations.append(CandidateEvaluation(
                first_card=candidate.first_card,
                sweep_probability=candidate.sweep_probability,
                escape_quality=escape.quality,
                expected_value=round(ev, 2),
                commit_type=commit_type,
                escape_plan=[escape.description] if escape.description else []
            ))

        if not evaluations:
            return Layer6Result(
                passed=False,
                evaluations=[],
                best_candidate=None,
                recommended_state="NIE",
                reason="L6: žiadni kandidáti po escape eval"
            )

        # Vyber best — najnižšie EV (záporné = dobré)
        best = min(evaluations, key=lambda e: e.expected_value)

        # Ak všetci DISASTER → NIE
        if all(e.commit_type == "NIE" for e in evaluations):
            return Layer6Result(
                passed=False,
                evaluations=evaluations,
                best_candidate=best,
                recommended_state="NIE",
                reason="L6: všetci kandidáti DISASTER"
            )

        recommended = best.commit_type
        if recommended == "NIE":
            recommended = "WATCHING"

        return Layer6Result(
            passed=True,
            evaluations=evaluations,
            best_candidate=best,
            recommended_state=recommended
        )

    def _find_escape(self, candidate: CandidateResult,
                     hand: list[Card],
                     l3: Layer3Result) -> EscapeRoute:
        """
        Nájde escape route pre daného kandidáta.

        Najprv skontroluje či escape vôbec potrebujem — ak mám plnú
        kontrolu nad zvyšnými štichmi (extended_wins >= remaining_tricks),
        vrátim NOT_NEEDED quality.

        Inak hľadám klasické escape cards (nízke non-heart non-special).
        """
        # Spočítaj reálne extended wins cez všetky farby
        total_extended_wins = 0
        for suit in SUITS:
            my_cards = [c for c in hand if c.suit == suit]
            remaining = self.memory.remaining[suit]
            total_extended_wins += self._suit_extended_wins(my_cards, remaining)

        remaining_tricks = len(hand)

        if total_extended_wins >= remaining_tricks:
            # Plnú kontrolu — escape nepotrebný
            return EscapeRoute(
                card=candidate.first_card,
                quality="NOT_NEEDED",
                damage=0,
                description=f"plnú kontrolu ({total_extended_wins} wins na "
                            f"{remaining_tricks} štichov)",
            )

        # Escape cez bell (najjednoduchšie — bell nie je trestný)
        escape_cards = [
            c for c in hand
            if c.suit == "bell"
               and not c.is_special
               and l3.per_suit_timeline["bell"].guaranteed_wins == 0
        ]

        if escape_cards:
            card = min(escape_cards, key=lambda c: c.rank_order)
            return EscapeRoute(
                card=card,
                quality="CLEAN",
                damage=0,
                description=f"escape cez {card}",
            )

        # Escape cez nízku kartu v leaf/acorn
        for suit in ("leaf", "acorn"):
            suit_cards = [
                c for c in hand
                if c.suit == suit
                   and not c.is_special
                   and c.rank in ("seven", "eight", "nine")
            ]
            if suit_cards:
                card = min(suit_cards, key=lambda c: c.rank_order)
                quality = ("CONTAINED"
                           if self.memory.is_special_gone(suit)
                           else "MESSY")
                damage = 4 if suit == "acorn" else 8
                return EscapeRoute(
                    card=card,
                    quality=quality,
                    damage=damage if quality == "MESSY" else 0,
                    description=f"escape cez {card} ({quality})",
                )

        # Žiadny escape → DISASTER
        return EscapeRoute(
            card=candidate.first_card,
            quality="DISASTER",
            damage=20,
            description="žiadny escape",
        )

    @staticmethod
    def _determine_commit_type(p_sweep: float,
                               escape_quality: str) -> str:
        """
        Určí commit type podľa P(sweep) a escape kvality.

        NOT_NEEDED — plnú kontrolu, žiadny escape netreba.
                     Stačí mierna pravdepodobnosť pre commit.
        CLEAN — bezpečný únik, môžem si dovoliť committovať pri vyššej P.
        CONTAINED — únik s istým damage, ale obmedzený.
        MESSY — riskantný únik, vyžaduje vyššiu P.
        DISASTER — žiadny únik, len pri matematicky garantovanom sweepe.
        """
        if escape_quality == "NOT_NEEDED":
            if p_sweep > 0.5:
                return "COMMITTED_FULL"
            if p_sweep > 0.3:
                return "WATCHING"
            return "NIE"

        if escape_quality == "DISASTER":
            if p_sweep > 0.9:
                return "COMMITTED_FULL"
            return "NIE"

        if escape_quality == "CLEAN":
            if p_sweep > 0.7:
                return "COMMITTED_SAFE"
            return "WATCHING"

        if escape_quality == "CONTAINED":
            if p_sweep > 0.8:
                return "COMMITTED_SAFE"
            if p_sweep > 0.6:
                return "WATCHING"
            return "NIE"

        if escape_quality == "MESSY":
            if p_sweep > 0.85:
                return "COMMITTED_SAFE"
            return "NIE"

        return "NIE"
    # ------------------------------------------------------------------
    # VRSTVA 7: Decision
    # ------------------------------------------------------------------
    def _layer7(self, l1: Layer1Result,
                l2: Layer2Result,
                l5: Layer5Result,
                l6: Layer6Result) -> tuple[SweepDecision, SweepState, Card | None]:
        """
        Finálne rozhodnutie.
        """
        if not l6.best_candidate:
            return SweepDecision.NO, SweepState.IDLE, None

        best = l6.best_candidate

        # Krok 1: 100% override — pri matematicky garantovanom sweepe
        # ignorujeme všetky constraints. Bez ohľadu na trick number či
        # MEDIUM strength — ak P=1.0, sweep je istý a má zmysel
        # commitnúť okamžite (užitočné aj pre declaration "all").
        if best.sweep_probability >= 1.0:
            return (SweepDecision.YES,
                    SweepState.COMMITTED_FULL,
                    best.first_card)

        # Krok 2: Aplikuj WATCHING constraint z dvoch zdrojov:
        # 1. Phase (Gate 4 z Layer 1) — trick 1 max WATCHING
        # 2. Layer 2 strength=MEDIUM — slabšia ruka, len observačný stav
        commit_type = best.commit_type
        force_watching = (
            l1.max_state == "WATCHING"
            or l2.recommended_state == "WATCHING"
        )
        if force_watching and commit_type in ("COMMITTED_SAFE", "COMMITTED_FULL"):
            commit_type = "WATCHING"

        # Krok 3: Map na výstup
        if commit_type == "COMMITTED_FULL":
            return (SweepDecision.YES,
                    SweepState.COMMITTED_FULL,
                    best.first_card)

        if commit_type == "COMMITTED_SAFE":
            return (SweepDecision.YES,
                    SweepState.COMMITTED_SAFE,
                    best.first_card)

        if commit_type == "WATCHING":
            return (SweepDecision.WATCHING,
                    SweepState.WATCHING,
                    None)

        return SweepDecision.NO, SweepState.IDLE, None

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _transition(self, new_state: SweepState):
        """Prechod medzi stavmi."""
        if self.state != new_state:
            self._log(
                "SWEEP_STATE",
                f"{self.state.value} → {new_state.value}"
            )
            self.state = new_state