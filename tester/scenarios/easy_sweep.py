# tester/scenarios/easy_sweep.py

from tester.scenario import Scenario, hand, trick


scenario = Scenario(
    name="easy_sweep",
    description=(
        "AI hráč 0 má perfektnú ruku na sweep — top 3 hearts, oba horníci "
        "s coverage, kontrola vo všetkých suitoch. Po triku 1 (AI vyhral "
        "s A●) začína trick 2 a sweep pipeline by mala vrátiť YES."
    ),

    # Pôvodné rozdanie — 8 kariet pre každého hráča
    hands={
        0: hand("A♥ K♥ Q♥ A♠ Q♠ A♣ Q♣ A●"),
        1: hand("J♥ K♠ J♠ K♣ J♣ K● Q● J●"),
        2: hand("10♥ 9♥ 10♠ 9♠ 10♣ 9♣ 10● 9●"),
        3: hand("8♥ 7♥ 8♠ 7♠ 8♣ 7♣ 8● 7●"),
    },

    # Kto začínal kolo — AI hráč 0 (vedie trick 1 s A●)
    first_player_index=0,

    # Žiadne iluminácie ani záväzky
    illuminations={"leaf": None, "acorn": None},
    declarations={0: None, 1: None, 2: None, 3: None},

    # História — len trick 1
    history=[
        # Trick 1: AI 0 vedie A●, ostatní followujú bellom
        # Poradie: 0 → 1 → 2 → 3 (proti smeru hodín)
        # Plays sú v poradí ako sa hralo, počnúc leaderom
        trick(leader=0, plays="A● J● 9● 7●"),
        # Winner sa vypočíta automaticky → 0 (najvyššia karta v lead suit)
    ],

    # Zastavíme po celej histórii (= pred trickom 2)
    start_after_trick=None,
)