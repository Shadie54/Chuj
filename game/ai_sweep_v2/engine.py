# game/ai_sweep_v2/engine.py
"""
SweepEngineV2 — tenký orchestrátor nad dvoma vrstvami:

  1) pipeline.py — 1:1 kópia starého, osvedčeného ai_sweep.py (7-vrstvová
     AND-gate kaskáda), ktorú postupne reworkujeme priamo (rekalibrácia
     prahov cez simulátor, doplnenie chýbajúcich nuáns). Pozri
     pipeline.py docstring a claude/03_SWEEP_V2_HANDOFF.md pre kontext,
     prečo sme sem prešli namiesto pokračovania v pôvodnom "od nuly"
     Sweep v2 (risk.py/feasibility.py/strategies/ — zmazané 2026-08-20,
     dosahovali len ~17-18% úspešnosť oproti starému systému 85.3%).
     Beží VŽDY prvý — je lacný (žiadne exponenciálne prehľadávanie).

  2) Tier B (solver.py) — presné AND-OR vyhľadávanie pre koncovku
     (posledných pár štichov, pozri solver.MAX_SEARCH_TRICKS). Toto je
     SKUTOČNÝ dôkaz, nie odhad — niečo, čo starý ai_sweep.py nikdy
     nemal (aj jeho L7 pri P=1.0 je len "heuristicky isté", nie
     matematicky dokázané). Skúša sa LEN ako doplnok, keď pipeline.py
     vráti NO/WATCHING — môže dokázať niečo, čo konzervatívne prahy
     heuristiky prehliadli. Pôvodné poradie (Tier B vždy prvý v
     posledných 5 štichoch) bolo príliš drahé — spomalilo simuláciu
     ~25× bez merateľného prínosu, keďže heuristika aj tak väčšinou
     už povie COMMIT skôr, než sa Tier B vôbec dostane k slovu.

Staré Tier A/C moduly (security.py, risk.py, feasibility.py,
strategies/) boli odstránené — ich funkciu teraz plní priamo pipeline.py
(má vlastný Gate1 ekvivalent security.check_already_lost()).
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.trick import Trick
from game.ai_hand_eval import HandEval
from game.ai_sweep_v2 import solver
from game.ai_sweep_v2.pipeline import (
    SweepPipeline,
    SweepResult,
    SweepDecision,
    SweepState,
)

# Tier B (solver.py) je DOČASNE VYPNUTÝ (2026-08-20) — meranie na 200
# hrách (seed 777) ukázalo, že pipeline.py sám dáva 81.7% úspešnosť
# (zodpovedá starému ai_sweep.py, 85.3%), ale so zapnutým Tier B
# kolabuje na 3.8% pri 6615 pokusoch (vs. 180 bez neho) — Tier B evidentne
# často nesprávne "dokazuje" COMMIT. solver.py pochádza zo zahodenej
# pôvodnej Sweep v2 architektúry a nebol nikdy stress-testovaný na
# veľkom počte reálnych hier, len na pár ručne zostavených scenárov.
# Treba samostatne odladiť predtým, než sa znova zapne — pozri
# claude/03_SWEEP_V2_HANDOFF.md.
_TIER_B_ENABLED = False


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
