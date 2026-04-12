# game/ai_strategies_const.py

class Strategy:
    # Leader stratégie (L)
    SAFE_LEAD = "L1-SAFE_LEAD"
    FORCE_SPECIAL = "L2-FORCE_SPECIAL"

    # Follower stratégie (F)
    AVOID_PENALTY = "F1-AVOID_PENALTY"
    DUMP_SPECIAL = "F2-DUMP_SPECIAL"
    AGAINST_DECLARATION = "F3-AGAINST_DECLARATION"

    # Záväzok (D)
    DECLARATION_ALL = "D1-DECLARATION_ALL"
    DECLARATION_NONE = "D2-DECLARATION_NONE"