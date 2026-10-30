# game/round_points.py
#
# Skutočné body hráča v kole — to, čo mu hra naozaj pripíše (pred bonusom
# za sériu a resetom zo 100 na 90). Zrkadlí Round.score_round() a
# Player.finalize_round(); hernú logiku tu len ČÍTAME. Používa ju panel KOLO
# (gui/round_status.py) aj zberač štatistík (game/stats_collector.py), aby
# obe ukazovali presne to isté číslo.

from config import (
    DECLARATION_ALL_BONUS, DECLARATION_ALL_PENALTY, DECLARATION_FAIL_PENALTY,
    DECLARATION_NONE_BONUS, HIGH_SCORE_THRESHOLD, SHOOT_MOON_BONUS,
)


def actual_round_points(rnd, player, index: int, score_before: int,
                        finished: bool = True) -> int | None:
    """Skutočné body hráča `index` v kole `rnd`.

    score_before — skóre hráča PRED týmto kolom (pravidlo 90+).
    finished     — kolo je už uzavreté (Round.phase == "done"). V kole so
                   záväzkom je výsledok známy až vtedy; do tej chvíle
                   vracia None ("nič nezobrazovať")."""
    if rnd is not None and rnd.declaration_type is not None:
        if not finished:
            return None
        if rnd.declaration_player != index:
            return 0                        # záväzok súpera → nič
        if rnd.declaration_type == "none":
            return (DECLARATION_NONE_BONUS if player.tricks_won == 0
                    else DECLARATION_FAIL_PENALTY)
        return (DECLARATION_ALL_BONUS if player.tricks_won == 8
                else DECLARATION_ALL_PENALTY)

    if finished and (player.round_flags or {}).get("sweep"):
        return SHOOT_MOON_BONUS

    points = player.round_points
    if score_before >= HIGH_SCORE_THRESHOLD and rnd is not None:
        leaf_ill = rnd.illuminated_by.get("leaf") is not None
        acorn_ill = rnd.illuminated_by.get("acorn") is not None
        points -= sum(c.get_points(leaf_ill, acorn_ill)
                      for c in player.penalty_cards if c.is_special)
    return points
