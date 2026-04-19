# game/ai_strategies_const.py


class Situation:
    # Leader situácie
    LEADER_SAFE         = "L-SAFE"
    LEADER_FORCED       = "L-FORCED"
    LEADER_AGGRESSIVE   = "L-AGGRESSIVE"

    # Follower situácie
    FOLLOWER_SAFE       = "F-SAFE"
    FOLLOWER_VOID       = "F-VOID"
    FOLLOWER_FORCED     = "F-FORCED"
    FOLLOWER_CONTROLLED = "F-CONTROLLED"
    FOLLOWER_WAIT       = "F-WAIT"


class Mode:
    SAFE  = "SAFE"
    TAKE  = "TAKE"
    OPEN  = "OPEN"


class Strategy:
    # Leader
    SAFE_LEAD       = "L1-SAFE_LEAD"
    FORCE_SPECIAL   = "L2-FORCE_SPECIAL"
    DUMP_SETUP      = "L3-DUMP_SETUP"

    # Follower
    UNDERPLAY       = "F1-UNDERPLAY"
    FORCED_TAKE     = "F2-FORCED_TAKE"
    LAST_TAKE       = "F3-LAST_TAKE"
    WAIT            = "F4-WAIT"
    DUMP_SPECIAL    = "F5-DUMP_SPECIAL"
    DUMP_HEART      = "F6-DUMP_HEART"
    DUMP_DANGEROUS  = "F7-DUMP_DANGEROUS"

    # Proti záväzku
    BREAK_ALL       = "A1-BREAK_ALL"
    BREAK_NONE      = "A2-BREAK_NONE"

    # Záväzok
    DECLARATION_ALL  = "D1-DECLARATION_ALL"
    DECLARATION_NONE = "D2-DECLARATION_NONE"