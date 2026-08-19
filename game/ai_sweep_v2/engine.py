# game/ai_sweep_v2/engine.py
"""
SweepEngineV2 — nový sweep systém, budovaný from scratch.

Fáza 3 (aktuálny stav): Tier A (Security check, security.py) +
Tier B (presné vyhľadávanie pre koncovku, solver.py) + Tier C
(risk/EV odhad + pomenované forcing plays, risk.py + strategies/).

Tier A vracia PROVEN_CERTAIN / PROVEN_IMPOSSIBLE len keď to vie
skutočne dokázať lacno a deterministicky. Ak vráti UNRESOLVED,
skúsime Tier B — presné AND-OR prehľadávanie nad reprezentatívnymi
najhoršími hypotézami rozloženia kariet (obmedzené na koncovku,
pozri solver.MAX_SEARCH_TRICKS). Ak ani Tier B nič nedokáže, skúsime
Tier C — heuristický odhad pravdepodobnosti úspechu.

Tier C poradie kritických eventov: viacero nezaistených zdrojov sa
NIKDY neriešia v ľubovoľnom poradí — najprv sa skúša najlacnejší
AKTUÁLNE TESTOVATEĽNÝ zdroj (kaskáda cez risk.source_cost_points),
až keď ten už nejde otestovať (zdroj zaistený, alebo nemám vhodnú
kartu), postupuje sa na ďalší najlacnejší. Dôvod: predčasné odhalenie
drahej karty (napr. vysvieteného horníka) prezradí súperom, že ide o
sweep, a lacné zdroje potom môžu prekaziť oveľa lacnejšie, než keby
boli otestované ako prvé — pozri claude/03_SWEEP_V2_HANDOFF.md.

Tier C nikdy nevracia PROVEN_CERTAIN — aj pri COMMIT ostáva
certainty=UNRESOLVED, aby bolo z logu vždy jasné, že ide o odhad,
nie o dôkaz.
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.trick import Trick
from game.ai_sweep_v2.models import SweepPlan
from game.ai_sweep_v2 import security
from game.ai_sweep_v2 import solver
from game.ai_sweep_v2 import risk
from game.ai_sweep_v2.strategies import force_resolution
from game.ai_sweep_v2.strategies import hearts_probe

# Prahy pre Tier C COMMIT — per stratégia. Čím "drahšia"/odhaľujúcejšia
# stratégia, tým vyššia požadovaná istota (vedome konzervatívne, aby sa
# nezopakoval starý bug — hazardovanie pri nízkej reálnej šanci).
# Doladiť podľa testov na reálnych seedoch.
TIER_C_COMMIT_THRESHOLDS = {
    force_resolution.ACE_PROBE_NAME: 0.25,    # bezrizikové — takmer vždy sa oplatí
    hearts_probe.STRATEGY_NAME: 0.40,         # lacné — nízka požadovaná istota
    force_resolution.KING_PROBE_NAME: 0.50,   # nepriame riziko (void-discard) — stredná istota
    force_resolution.STRATEGY_NAME: 0.65,     # drahé/odhaľujúce — vysoká istota
}
TIER_C_DEFAULT_THRESHOLD = 0.65


class SweepEngineV2:
    def __init__(self, player: Player, memory: AIMemory, logger=None):
        self.player = player
        self.memory = memory
        self.logger = logger

    def _log(self, detail: str):
        if self.logger:
            self.logger.log_strategy(self.player.name, "SWEEP_V2", detail)

    def decide(self, playable: list[Card], current_trick: Trick,
               trick_number: int) -> SweepPlan:
        reasoning = []

        if security.check_already_lost(self.player, self.memory):
            reasoning.append("niektorý súper už drží trestnú kartu")
            plan = SweepPlan(
                certainty="PROVEN_IMPOSSIBLE",
                decision="ABANDON",
                reasoning=reasoning,
            )
            self._log(f"{plan.certainty} | {plan.decision} | {reasoning[-1]}")
            return plan

        sources = security.evaluate_sources(self.player, self.memory)
        for s in sources:
            reasoning.append(f"{s.kind}: secured={s.secured} ({s.reason})")

        if all(s.secured for s in sources):
            plan = SweepPlan(
                certainty="PROVEN_CERTAIN",
                decision="COMMIT",
                confidence=1.0,
                sources=sources,
                reasoning=reasoning,
            )
            self._log(f"{plan.certainty} | {plan.decision} | všetky zdroje zaistené")
            return plan

        # Tier A nerozhodlo — skús Tier B (presné vyhľadávanie pre koncovku)
        b_plan = solver.solve(self.player, self.memory, trick_number,
                               current_trick, playable)
        b_plan.sources = sources
        b_plan.reasoning = reasoning + b_plan.reasoning
        if b_plan.decision == "COMMIT":
            self._log(
                f"{b_plan.certainty} | {b_plan.decision} | "
                f"Tier B našiel istú kartu: {b_plan.card}"
            )
            return b_plan

        # Tier B nerozhodlo — skús Tier C (heuristický odhad + forcing plays)
        c_plan = self._decide_tier_c(playable, current_trick, trick_number,
                                      sources, b_plan.reasoning)
        return c_plan

    def _decide_tier_c(self, playable: list[Card], current_trick: Trick,
                        trick_number: int, sources: list,
                        reasoning: list[str]) -> SweepPlan:
        unresolved = [s for s in sources if not s.secured]
        current_trick_cards = [c for _, c in current_trick.played_cards]
        tricks_remaining = 8 - trick_number
        is_leader = len(current_trick.played_cards) == 0

        confidence = risk.estimate_confidence(
            self.player, self.memory, unresolved,
            current_trick_cards, tricks_remaining,
        )

        # Kaskáda podľa ceny: skús najlacnejší AKTUÁLNE TESTOVATEĽNÝ
        # zdroj prvý; ak sa nedá otestovať (zaistený medzičasom, alebo
        # nemám vhodnú kartu), posuň sa na ďalší najlacnejší.
        costed = sorted(unresolved, key=lambda s: risk.source_cost_points(s, self.memory))
        cost_summary = ", ".join(
            f"{s.kind}={risk.source_cost_points(s, self.memory)}b" for s in costed
        )
        reasoning = reasoning + [
            f"Tier C: heuristická confidence={confidence:.2f} (odhad, nie dôkaz; "
            f"poradie podľa ceny: {cost_summary})"
        ]

        candidate = None
        for source in costed:
            if source.kind == "hearts":
                candidate = hearts_probe.find_candidate(
                    self.player, self.memory, source, playable, is_leader
                )
            elif source.kind in ("leaf_hornik", "acorn_hornik"):
                candidate = force_resolution.find_candidate(
                    self.player, self.memory, source, playable, is_leader
                )
            if candidate is not None:
                break

        if candidate is not None:
            card, bonus, strategy_name = candidate
            threshold = TIER_C_COMMIT_THRESHOLDS.get(strategy_name, TIER_C_DEFAULT_THRESHOLD)
            final_confidence = min(risk.MAX_HEURISTIC_CONFIDENCE, confidence + bonus)
            if card in playable and final_confidence >= threshold:
                plan = SweepPlan(
                    certainty="UNRESOLVED",
                    decision="COMMIT",
                    card=card,
                    confidence=final_confidence,
                    strategy_used=strategy_name,
                    sources=sources,
                    reasoning=reasoning + [
                        f"Tier C: {strategy_name} kandidát {card} "
                        f"(confidence={final_confidence:.2f} >= {threshold})"
                    ],
                )
                self._log(
                    f"{plan.certainty} | {plan.decision} | "
                    f"{strategy_name}: {card} (confidence={final_confidence:.2f})"
                )
                return plan

            reasoning = reasoning + [
                f"Tier C: {strategy_name} kandidát {card} "
                f"zamietnutý (confidence={final_confidence:.2f} < {threshold})"
            ]

        plan = SweepPlan(
            certainty="UNRESOLVED",
            decision="WATCH",
            confidence=confidence,
            sources=sources,
            reasoning=reasoning,
        )
        self._log(
            f"{plan.certainty} | {plan.decision} | "
            f"Tier C nekomituje (confidence={confidence:.2f})"
        )
        return plan

    def reset(self):
        """Reset po skončení kola — Tier A/B/C sú všetky bezstavové."""
        pass
