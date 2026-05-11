# tester/tester_logger.py

from dataclasses import dataclass, field
from game.ai_sweep import SweepResult


# ------------------------------------------------------------------
# LogEntry — jeden záznam logu
# ------------------------------------------------------------------

@dataclass
class LogEntry:
    kind: str
    player: str

    # strategy
    strategy: str = ""
    details: str = ""

    # sweep
    sweep_result: SweepResult | None = None
    trick_number: int = 0

    # illumination
    suit: str = ""
    reserve_quality: str = ""
    risk_level: str = ""
    compensation: int = 0
    comp_breakdown: dict = field(default_factory=dict)
    reason: str = ""
    decision: bool = False

    # declaration
    declaration_result: bool = False
    declaration_risk: str = ""


# ------------------------------------------------------------------
# TesterLogger
# ------------------------------------------------------------------

class TesterLogger:
    """
    Logger pre tester — zachytáva log_strategy() a log_sweep_pipeline()
    volania z AI.

    Rozhranie kompatibilné s GameLogger, aby ho bolo možné injectnúť
    do AI bez zmeny AI kódu. Ostatné metódy sú no-op stuby (AI ich
    nevolá, ale niektoré herné triedy by mohli — bezpečné no-op).

    Použitie:
        logger = TesterLogger()
        ai = AI(player, logger=logger)

        # Pred každým ťahom:
        logger.start_capture()
        card = ai.decide_card(...)
        captured = logger.get_capture()
        # captured obsahuje všetky log entries z toho ťahu
    """

    def __init__(self):
        self.current_capture: list[LogEntry] = []
        self.full_history: list[LogEntry] = []

    # ------------------------------------------------------------------
    # Capture API
    # ------------------------------------------------------------------

    def start_capture(self):
        """Vyprázdni current_capture, začne nové zachytávanie."""
        self.current_capture = []

    def get_capture(self) -> list[LogEntry]:
        """Vráti čo sa zachytilo od posledného start_capture()."""
        return list(self.current_capture)

    def get_full_history(self) -> list[LogEntry]:
        """Vráti celú históriu od vzniku loggera."""
        return list(self.full_history)

    def reset(self):
        """Úplne vyčistí logger (pri reštarte scenára)."""
        self.current_capture = []
        self.full_history = []

    # ------------------------------------------------------------------
    # Rozhranie kompatibilné s GameLogger — implementované
    # ------------------------------------------------------------------

    def log_strategy(self, player: str, strategy: str, details: str = ""):
        """Zachytí strategy log od AI."""
        entry = LogEntry(
            kind="strategy",
            player=player,
            strategy=strategy,
            details=details,
        )
        self.current_capture.append(entry)
        self.full_history.append(entry)

    def log_sweep_pipeline(self, player: str, result: SweepResult,
                            trick_number: int):
        """
        Zachytí sweep pipeline výstup od AI.

        POZN: Na rozdiel od GameLogger, TesterLogger zachytí AJ stav IDLE
        — pre tester chceme úplný debug každého ťahu.
        """
        entry = LogEntry(
            kind="sweep",
            player=player,
            sweep_result=result,
            trick_number=trick_number,
        )
        self.current_capture.append(entry)
        self.full_history.append(entry)

    # ------------------------------------------------------------------
    # Rozhranie kompatibilné s GameLogger — no-op stuby
    # ------------------------------------------------------------------

    def new_round(self, *args, **kwargs):
        pass

    def log_declaration(self, *args, **kwargs):
        pass

    def log_illumination_decision(self, player: str, suit: str,
                                  reserve_quality: str, risk_level: str,
                                  compensation: int, comp_breakdown: dict,
                                  reason: str, decision: bool):
        entry = LogEntry(
            kind="illumination",
            player=player,
            suit=suit,
            reserve_quality=reserve_quality,
            risk_level=risk_level,
            compensation=compensation,
            comp_breakdown=comp_breakdown,
            reason=reason,
            decision=decision,
        )
        self.current_capture.append(entry)
        self.full_history.append(entry)

    def log_declaration_decision(self, player: str, declaration: str | None,
                                 reason: str):
        entry = LogEntry(
            kind="declaration",
            player=player,
            strategy=declaration or "žiadny",
            details=reason,
        )
        self.current_capture.append(entry)
        self.full_history.append(entry)

    def log_illumination(self, *args, **kwargs):
        pass

    def log_trick(self, *args, **kwargs):
        pass

    def log_shoot_moon(self, *args, **kwargs):
        pass

    def log_declaration_result(self, *args, **kwargs):
        pass

    def log_round_result(self, *args, **kwargs):
        pass

    def log_no_penalty_streak(self, *args, **kwargs):
        pass

    def save_round(self, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        return None

    # ------------------------------------------------------------------
    # Pomocné — formátovanie pre zobrazenie
    # ------------------------------------------------------------------

    @staticmethod
    def format_entry(entry: LogEntry) -> list[str]:
        """
        Naformátuje LogEntry do zoznamu riadkov pre zobrazenie.

        Sweep entries sa rozbalia na viac riadkov (decision/state/card +
        reasoning chain). Strategy entries sú vždy jeden riadok.
        """
        lines = []

        if entry.kind == "strategy":
            if entry.details:
                lines.append(
                    f"[{entry.player}] {entry.strategy}: {entry.details}"
                )
            else:
                lines.append(f"[{entry.player}] {entry.strategy}")

        elif entry.kind == "sweep":
            r = entry.sweep_result
            if r is None:
                lines.append(f"[SWEEP {entry.player}] — žiadny result")
                return lines

            lines.append(
                f"[SWEEP {entry.player}] štich {entry.trick_number}: "
                f"{r.decision.value} | stav={r.state.value} | "
                f"P(sweep)={r.sweep_probability:.2f} | EV={r.expected_value}"
            )
            if r.recommended_card:
                lines.append(f"  → odporúčaná karta: {r.recommended_card}")
            for step in r.reasoning_chain:
                lines.append(f"  → {step}")
            for plan in r.escape_plan:
                lines.append(f"  ↩ escape: {plan}")

        elif entry.kind == "illumination":
            suit_sym = "Q♠" if entry.suit == "leaf" else "Q♣"
            result = "ÁNO" if entry.decision else "NIE"
            lines.append(
                f"[{entry.player}] {suit_sym} svietiť? {result} "
                f"| rezerva={entry.reserve_quality} "
                f"| riziko={entry.risk_level} "
                f"| kompenz.={entry.compensation}"
            )
            # Dôvod
            reason_map = {
                "no_special": "nemám horníka",
                "no_reserves": "žiadne rezervy",
                "bad_reserves": "zlé rezervy",
                "leader_borderline": "líder — borderline rezerva",
                "high_score_veto": "90+ veto",
                "high_score_unprotected_hearts": "90+ nekrytý vysoký červeň",
                "high_score_naked_high": "90+ plonkový vysoký v inej farbe",
                "decision_yes": "rozhodnutie: svietiť",
                "decision_no": "rozhodnutie: nesvietiť",
            }
            reason_text = reason_map.get(entry.reason, entry.reason)
            lines.append(f"  → dôvod: {reason_text}")
            bd = entry.comp_breakdown
            if bd.get("void"):
                suits_str = ", ".join(bd["void"])
                lines.append(f"  → void farby: {suits_str} (+{len(bd['void'])})")
            if bd.get("position"):
                lines.append(f"  → posledný hráč (+1)")

        elif entry.kind == "declaration":
            declaration_map = {
                "all": "Beriem všetko",
                "none": "Nechytím nič",
                "žiadny": "žiadny záväzok",
            }
            declaration_text = declaration_map.get(entry.strategy, entry.strategy)
            lines.append(
                f"[{entry.player}] záväzok: {declaration_text} | {entry.details}"
            )
        return lines