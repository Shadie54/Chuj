# game/ai_sweep/engine.py
"""
SweepEngineV2 — tenký orchestrátor nad dvoma vrstvami:

  1) pipeline.py (Tier A) — 7-vrstvová AND-gate kaskáda, jediný sweep
     systém v hre (starý game/ai_sweep.py bol po overení zhody zmazaný
     2026-09-06 — pozri pipeline.py docstring a
     claude/03_SWEEP_V2_HANDOFF.md pre históriu). Beží VŽDY prvý — je
     lacný (žiadne exponenciálne prehľadávanie).

  2) Tier B (solver.py) — presné AND-OR vyhľadávanie pre koncovku
     (posledných pár štichov, pozri solver.MAX_SEARCH_TRICKS). Toto je
     SKUTOČNÝ dôkaz, nie odhad (aj L7 pipeline.py pri P=1.0 je len
     "heuristicky isté", nie matematicky dokázané). Skúša sa LEN ako
     doplnok, keď pipeline.py vráti NO/WATCHING — môže dokázať niečo,
     čo konzervatívne prahy heuristiky prehliadli.
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.trick import Trick
from game.ai_hand_eval import HandEval
from game.ai_sweep import solver
from game.ai_sweep.pipeline import (
    SweepPipeline,
    SweepResult,
    SweepDecision,
    SweepState,
)

# Tier B (solver.py) — 2026-08-20 dočasne vypnutý: pôvodná verzia
# testovala len 2-3 ručne vybrané "najhoršie" hypotézy rozloženia
# namiesto skutočne VŠETKÝCH platných rozložení, takže PROVEN_CERTAIN
# nebol skutočný dôkaz — kolabovalo to na 3.8% (6615 pokusov) namiesto
# spoľahnutia sa na pipeline.py (81.7%, 180 pokusov). 2026-09-04:
# solver.py prepísaný tak, aby generoval ÚPLNE VŠETKY platné rozdelenia
# zvyšných kariet (nie len vzorku) — skutočný kompletný dôkaz, obmedzený
# na MAX_SEARCH_TRICKS=2, aby to zostalo výpočtovo lacné. Znovu zapnuté
# na test — pozri claude/03_SWEEP_V2_HANDOFF.md pre regresné čísla.
_TIER_B_ENABLED = True


class SweepEngineV2:
    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger
        self.pipeline = SweepPipeline(player, memory, logger)

    def _log(self, detail: str):
        if self.logger:
            self.logger.log_strategy(self.player.name, "SWEEP_V2_TIERB", detail)

    def evaluate(self, hand_eval: HandEval, trick_number: int,
                 current_trick: Trick, playable: list[Card]) -> SweepResult:
        # Najprv rýchla heuristika (pipeline.py, lacné L1-L7) — ak už
        # našla COMMIT, netreba drahé presné vyhľadávanie. Tier B sa
        # skúša len ako DOPLNOK, keď heuristika nenájde nič (NO/WATCHING)
        # a sme v koncovke — vtedy môže dokázať niečo, čo heuristika
        # (konzervatívne prahy) prehliadla. Pôvodné poradie (Tier B vždy
        # prvý v posledných 5 štichoch) bolo príliš drahé — spomalilo
        # simuláciu ~25× oproti starému systému bez merateľného prínosu
        # pre bežné prípady, kde heuristika aj tak povie COMMIT.
        result = self.pipeline.evaluate(hand_eval, trick_number)
        if result.decision == SweepDecision.YES or not _TIER_B_ENABLED:
            return result

        tricks_remaining = 8 - trick_number
        if tricks_remaining <= solver.MAX_SEARCH_TRICKS:
            b_plan = solver.solve(self.player, self.memory, trick_number,
                                   current_trick, playable)
            if b_plan.decision == "COMMIT" and b_plan.card is not None:
                self._log(f"presný dôkaz (Tier B): {b_plan.card}")
                return SweepResult(
                    decision=SweepDecision.YES,
                    state=SweepState.COMMITTED_FULL,
                    recommended_card=b_plan.card,
                    sweep_probability=1.0,
                    reasoning_chain=result.reasoning_chain
                    + ["Tier B: presné vyhľadávanie"] + b_plan.reasoning,
                )

        return result

    def reset(self):
        self.pipeline.reset()
