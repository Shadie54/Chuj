# game/ai_sweep_v2/strategies/hearts_probe.py
"""
HEARTS_PROBE — otestuj najlacnejší nezaistený zdroj (hearts) skôr, než
sa siahne po drahších pákach (napr. FORCE_RESOLUTION na horníka).

Srdcové karty majú nízku bodovú hodnotu (1-2b/kartu) — ak chce súper
sweep prekaziť, toto je jeho najlacnejšia príležitosť. Vedenie
najnižšej srdcovej karty v mojej ruke je lacný spôsob, ako to zistiť
skôr, než odhalím drahšiu kartu (horníka) a tým súperovi ukážem, že sa
oplatí sweep prekaziť aj lacnou obetou (pozri engine._decide_tier_c —
kaskáda podľa risk.source_cost_points).
"""

from game.card import Card
from game.player import Player
from game.ai_memory import AIMemory
from game.ai_sweep_v2.models import PenaltySource

STRATEGY_NAME = "HEARTS_PROBE"

_PROBE_BONUS = 0.2  # skromný bonus — toto je test, nie istota


def find_candidate(player: Player, memory: AIMemory,
                    source: PenaltySource,
                    playable: list[Card],
                    is_leader: bool) -> tuple[Card, float, str] | None:
    """
    source: nezaistený "hearts" zdroj. Vráti (najnižšia srdcová karta,
    confidence_bonus, meno_stratégie), alebo None ak sa nedá práve teraz
    otestovať (nie som leader / nemám žiadnu srdcovú kartu na zahranie).
    """
    if not is_leader or source.kind != "hearts":
        return None

    my_hearts = [c for c in player.hand.cards if c.suit == "heart" and c in playable]
    if not my_hearts:
        return None

    lowest = min(my_hearts, key=lambda c: c.rank_order)
    return lowest, _PROBE_BONUS, STRATEGY_NAME
