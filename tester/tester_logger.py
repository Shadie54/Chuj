# tester/tester_logger.py

from dataclasses import dataclass, field
from game.ai_sweep import SweepResult


# ------------------------------------------------------------------
# LogEntry — jeden záznam logu
# ------------------------------------------------------------------

@dataclass
class LogEntry:
    """
    Jeden záznam zachytený TesterLoggerom.

    kind = "strategy":  log_strategy() volanie
        player, strategy, details
    kind = "sweep":     log_sweep_pipeline() volanie
        player, sweep_result, trick_number
    """
    kind: str                              # "strategy" | "sweep"
    player: str

    # Pre kind="strategy"
    strategy: str = ""
    details: str = ""

    # Pre kind="sweep"
    sweep_result: SweepResult | None = None
    trick_number: int = 0


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

    def log_illumination_decision(self, *args, **kwargs):
        pass

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
                f"[SWEEP {entry.player}] štych {entry.trick_number}: "
                f"{r.decision.value} | stav={r.state.value} | "
                f"P(sweep)={r.sweep_probability:.2f} | EV={r.expected_value}"
            )
            if r.recommended_card:
                lines.append(f"  → odporúčaná karta: {r.recommended_card}")
            for step in r.reasoning_chain:
                lines.append(f"  → {step}")
            for plan in r.escape_plan:
                lines.append(f"  ↩ escape: {plan}")

        return lines