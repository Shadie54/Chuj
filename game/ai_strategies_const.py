# game/ai_strategies_const.py


class Situation:
    # Leader situácie
    LEADER_SAFE         = "L-SAFE"
    LEADER_FORCED       = "L-FORCED"
    LEADER_AGGRESSIVE   = "L-AGGRESSIVE"
    LEADER_HIGH_SCORE   = "L-HIGH_SCORE"
    LEADER_RISK         = "L-RISK"

    # Follower situácie
    FOLLOWER_SAFE          = "F-SAFE"
    FOLLOWER_VOID          = "F-VOID"
    FOLLOWER_FORCED_CLEAN  = "F-FORCED_CLEAN"   # posledný, čistý štich
    FOLLOWER_FORCED_POINTS = "F-FORCED_POINTS"  # donútený, bodový štich
    FOLLOWER_FREE_TAKE     = "F-FREE_TAKE"
    FOLLOWER_WAIT          = "F-WAIT"
    FOLLOWER_RISK          = "F-RISK"


class Mode:
    SAFE  = "SAFE"
    TAKE  = "TAKE"
    OPEN  = "OPEN"
    RISK  = "RISK"   # ← placeholder pre budúce riskové stratégie


class Strategy:
    # Leader
    SAFE_LEAD       = "L1-SAFE_LEAD"
    FORCE_SPECIAL   = "L2-FORCE_SPECIAL"
    DUMP_SETUP      = "L3-DUMP_SETUP"
    HIGH_SCORE_LEAD = "L4-HIGH_SCORE_LEAD"  # ← nové
    RISK_SPECIAL    = "L5-RISK_SPECIAL"

    # Follower
    UNDERPLAY       = "F1-UNDERPLAY"  # podliezam
    FORCED_TAKE     = "F2-FORCED_TAKE"  # musím brať (penalty štich, trap)
    LAST_TAKE       = "F3-LAST_TAKE"  # posledný, čistý štich, beriem vedome
    DUMP_FREE       = "F4-DUMP_FREE"  # dump A/K cez FREE_TAKE príležitosť
    WAIT            = "F5-WAIT"  # niekto iný berie
    DUMP_SPECIAL    = "F6-DUMP_SPECIAL"
    DUMP_HEART      = "F7-DUMP_HEART"
    DUMP_DANGEROUS  = "F8-DUMP_DANGEROUS"
    RISK_TRAP       = "F9-RISK_TRAP"

    # Proti záväzku
    BREAK_ALL       = "A1-BREAK_ALL"
    BREAK_NONE      = "A2-BREAK_NONE"

    # Záväzok
    DECLARATION_ALL  = "D1-DECLARATION_ALL"
    DECLARATION_NONE = "D2-DECLARATION_NONE"