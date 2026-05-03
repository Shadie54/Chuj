# tester/scenario.py

from dataclasses import dataclass, field
from game.card import Card
from config import NUM_PLAYERS, CARDS_PER_PLAYER, SUITS, RANKS


# ------------------------------------------------------------------
# DSL — parser kariet zo symbolových kódov
# ------------------------------------------------------------------

# Mapovanie symbolov → interné názvy
_SUIT_FROM_SYMBOL = {
    "♥": "heart",
    "●": "bell",
    "♠": "leaf",
    "♣": "acorn",
}

_RANK_FROM_SYMBOL = {
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "J": "under",
    "Q": "over",
    "K": "king",
    "A": "ace",
}


def C(code: str) -> Card:
    """
    Vyrobí Card zo symbolového kódu.

    Príklady:
        C("A♥")  → Card("heart", "ace")
        C("Q♠")  → Card("leaf", "over")    # zelený horník
        C("10●") → Card("bell", "ten")
        C("7♣")  → Card("acorn", "seven")

    Algoritmus: posledný znak = suit, zvyšok = rank.
    """
    if not code or len(code) < 2:
        raise ValueError(f"Neplatný kód karty: {code!r} (príliš krátky)")

    suit_char = code[-1]
    rank_str = code[:-1]

    if suit_char not in _SUIT_FROM_SYMBOL:
        raise ValueError(
            f"Neznámy symbol farby v {code!r}: {suit_char!r}. "
            f"Povolené: {list(_SUIT_FROM_SYMBOL.keys())}"
        )
    if rank_str not in _RANK_FROM_SYMBOL:
        raise ValueError(
            f"Neznámy rank v {code!r}: {rank_str!r}. "
            f"Povolené: {list(_RANK_FROM_SYMBOL.keys())}"
        )

    return Card(_SUIT_FROM_SYMBOL[suit_char], _RANK_FROM_SYMBOL[rank_str])


def hand(*codes: str) -> list[Card]:
    """
    Vyrobí list[Card] z kódov. Podporuje dva formáty:

        hand("A♥", "K♥", "Q♥")           # varargs
        hand("A♥ K♥ Q♥")                 # jeden string s medzerami

    Užitočné pri písaní rúk hráčov v scenári.
    """
    if len(codes) == 1 and " " in codes[0]:
        # Jeden string s medzerami — splitneme
        tokens = codes[0].split()
    else:
        tokens = list(codes)

    return [C(token) for token in tokens]


def cards(*codes: str) -> list[Card]:
    """Alias pre hand() — pre prípad keď meno 'hand' nesedí kontextu."""
    return hand(*codes)


# ------------------------------------------------------------------
# TrickHistory — jeden štych z histórie scenára
# ------------------------------------------------------------------

@dataclass
class TrickHistory:
    """
    Jeden štych z histórie scenára.

    leader: index hráča ktorý začal štich (0-3)
    cards: zoznam (player_index, Card) v poradí ako sa hralo
           Prvá entry MUSÍ byť leader, ďalšie proti smeru hodín (+1, +2, +3)
    winner: index hráča ktorý štich vyhral
    """
    leader: int
    cards: list[tuple[int, Card]]
    winner: int


def trick(leader: int, plays: str, winner: int | None = None) -> TrickHistory:
    """
    Helper pre vytvorenie TrickHistory s automatickým výpočtom víťaza.

    Príklad:
        trick(leader=1, plays="7● 9● 10● 8●")
        # plays je v poradí leader → +1 → +2 → +3 (proti smeru hodín)
        # winner sa vypočíta automaticky podľa pravidiel štichu

    Ak winner=None → automaticky vypočítaný (najvyššia karta v lead suit).
    Ak winner je zadaný → kontrola sa robí vo validate_scenario().
    """
    tokens = plays.split()
    if len(tokens) != NUM_PLAYERS:
        raise ValueError(
            f"trick(): očakávame {NUM_PLAYERS} kariet v plays, "
            f"dostali sme {len(tokens)}: {plays!r}"
        )

    # Karty v poradí ako sa hralo
    parsed_cards = [C(t) for t in tokens]

    # Player indices — leader, leader+1, leader+2, leader+3 (mod 4)
    player_indices = [(leader + i) % NUM_PLAYERS for i in range(NUM_PLAYERS)]

    cards_with_players = list(zip(player_indices, parsed_cards))

    # Auto-výpočet víťaza ak nie je zadaný
    if winner is None:
        winner = _compute_winner(cards_with_players)

    return TrickHistory(
        leader=leader,
        cards=cards_with_players,
        winner=winner,
    )


def _compute_winner(cards_with_players: list[tuple[int, Card]]) -> int:
    """
    Vypočíta víťaza štichu podľa pravidiel:
    - Najvyššia karta v lead suit vyhráva
    - Karty inej farby nemôžu vyhrať
    - Žiadne tromfy
    """
    lead_suit = cards_with_players[0][1].suit
    best_idx, best_card = cards_with_players[0]

    for player_idx, card in cards_with_players[1:]:
        if card.suit != lead_suit:
            continue
        if best_card.suit != lead_suit:
            best_idx, best_card = player_idx, card
        elif card.rank_order > best_card.rank_order:
            best_idx, best_card = player_idx, card

    return best_idx


# ------------------------------------------------------------------
# Scenario — plný scenár
# ------------------------------------------------------------------

@dataclass
class Scenario:
    """
    Plný scenár pre tester (Full play).

    name: identifikátor pre dropdown
    description: krátky popis čo scenár testuje
    hands: pôvodné rozdanie — 8 kariet pre každého hráča (index 0-3)
           POZN: musí obsahovať aj karty ktoré sú v history (zahrané),
           lebo AIMemory.init_with_hand() potrebuje plnú pôvodnú ruku
    first_player_index: kto začínal kolo (pred prvým štichom)
    illuminations: kto vysvietil ktorého horníka
                   {"leaf": player_index | None, "acorn": player_index | None}
    declarations: záväzky hráčov {player_index: "all"|"none"|None}
    history: zoznam štichov ktoré sa už odohrali (môže byť prázdny)
    start_after_trick: po koľkých štichoch z history zastaviť
                       None = po celej histórii (default)
    """
    name: str
    description: str
    hands: dict[int, list[Card]]
    first_player_index: int
    illuminations: dict[str, int | None] = field(
        default_factory=lambda: {"leaf": None, "acorn": None}
    )
    declarations: dict[int, str | None] = field(
        default_factory=lambda: {i: None for i in range(NUM_PLAYERS)}
    )
    history: list[TrickHistory] = field(default_factory=list)
    start_after_trick: int | None = None


# ------------------------------------------------------------------
# Validácia
# ------------------------------------------------------------------

def validate_scenario(scenario: Scenario) -> list[str]:
    """
    Skontroluje konzistenciu scenára.
    Vracia zoznam chybových správ — prázdny zoznam = OK.
    """
    errors = []

    # 1. Počet hráčov v hands
    if set(scenario.hands.keys()) != set(range(NUM_PLAYERS)):
        errors.append(
            f"hands musí mať keys {list(range(NUM_PLAYERS))}, "
            f"má {sorted(scenario.hands.keys())}"
        )
        return errors  # ďalšie kontroly nemajú zmysel

    # 2. Počet kariet v každej ruke
    for idx, cards_in_hand in scenario.hands.items():
        if len(cards_in_hand) != CARDS_PER_PLAYER:
            errors.append(
                f"hráč {idx} má {len(cards_in_hand)} kariet, "
                f"očakávame {CARDS_PER_PLAYER}"
            )

    # 3. Unikátnosť kariet — žiadna nesmie byť u dvoch hráčov
    all_cards = []
    for cards_in_hand in scenario.hands.values():
        all_cards.extend(cards_in_hand)
    if len(all_cards) != len(set(all_cards)):
        seen = set()
        dups = []
        for c in all_cards:
            if c in seen and str(c) not in dups:
                dups.append(str(c))
            seen.add(c)
        errors.append(f"duplicitné karty v rukách: {dups}")

    # 4. Validné suit/rank
    for idx, cards_in_hand in scenario.hands.items():
        for c in cards_in_hand:
            if c.suit not in SUITS:
                errors.append(f"hráč {idx}: neznáma farba '{c.suit}'")
            if c.rank not in RANKS:
                errors.append(f"hráč {idx}: neznámy rank '{c.rank}'")

    # 5. Spolu 32 kariet
    expected_total = NUM_PLAYERS * CARDS_PER_PLAYER
    if len(all_cards) != expected_total:
        errors.append(
            f"spolu {len(all_cards)} kariet, očakávame {expected_total}"
        )

    # 6. Illuminations — vysvietený horník musí byť u vysvietujúceho
    for suit_short in ("leaf", "acorn"):
        illuminator = scenario.illuminations.get(suit_short)
        if illuminator is None:
            continue
        if illuminator not in scenario.hands:
            errors.append(
                f"illuminator pre {suit_short} je hráč {illuminator}, "
                f"ten v hands neexistuje"
            )
            continue
        has_special = any(
            c.suit == suit_short and c.rank == "over"
            for c in scenario.hands[illuminator]
        )
        if not has_special:
            errors.append(
                f"hráč {illuminator} vysvietil {suit_short}-over, "
                f"ale nemá ho v ruke"
            )

    # 7. first_player_index validný
    if scenario.first_player_index not in range(NUM_PLAYERS):
        errors.append(
            f"first_player_index={scenario.first_player_index} "
            f"musí byť v rozsahu 0-{NUM_PLAYERS-1}"
        )

    # 8. Declarations — povolené hodnoty
    for idx, decl in scenario.declarations.items():
        if decl not in (None, "all", "none"):
            errors.append(
                f"hráč {idx}: declaration '{decl}' nie je povolené "
                f"(očakávame None, 'all' alebo 'none')"
            )

    # 9. History — kontrola každého štichu
    for i, th in enumerate(scenario.history):
        trick_label = f"history štych {i+1}"

        # 9a. Počet kariet
        if len(th.cards) != NUM_PLAYERS:
            errors.append(
                f"{trick_label}: {len(th.cards)} kariet, "
                f"očakávame {NUM_PLAYERS}"
            )
            continue

        # 9b. Prvá karta = leader
        if th.cards[0][0] != th.leader:
            errors.append(
                f"{trick_label}: prvá karta je od hráča "
                f"{th.cards[0][0]}, ale leader je {th.leader}"
            )

        # 9c. Poradie hráčov — leader, +1, +2, +3 (mod 4)
        expected_order = [(th.leader + j) % NUM_PLAYERS for j in range(NUM_PLAYERS)]
        actual_order = [pi for pi, _ in th.cards]
        if actual_order != expected_order:
            errors.append(
                f"{trick_label}: poradie hráčov {actual_order}, "
                f"očakávame {expected_order} (proti smeru hodín)"
            )

        # 9d. Winner musí byť v štyche
        player_indices = [pi for pi, _ in th.cards]
        if th.winner not in player_indices:
            errors.append(
                f"{trick_label}: winner {th.winner} nehral v štyche"
            )
            continue

        # 9e. Winner matchuje pravidlá štichu
        computed = _compute_winner(th.cards)
        if computed != th.winner:
            errors.append(
                f"{trick_label}: winner zadaný {th.winner}, "
                f"podľa pravidiel mal byť {computed}"
            )

        # 9f. Karty z history musia byť v pôvodných rukách
        for player_idx, card in th.cards:
            if player_idx not in scenario.hands:
                errors.append(
                    f"{trick_label}: hráč {player_idx} v hands neexistuje"
                )
                continue
            if card not in scenario.hands[player_idx]:
                errors.append(
                    f"{trick_label}: hráč {player_idx} hral {card}, "
                    f"ale tá nie je v jeho pôvodnej ruke"
                )

    # 10. start_after_trick rozumný
    if scenario.start_after_trick is not None:
        if scenario.start_after_trick < 0:
            errors.append("start_after_trick nesmie byť záporné")
        elif scenario.start_after_trick > len(scenario.history):
            errors.append(
                f"start_after_trick={scenario.start_after_trick} "
                f"> dĺžka history={len(scenario.history)}"
            )

    # 11. Žiadna karta nesmie byť zahraná dvakrát v histórii
    played_in_history = []
    for th in scenario.history:
        for _, card in th.cards:
            played_in_history.append(card)
    if len(played_in_history) != len(set(played_in_history)):
        seen = set()
        dups = []
        for c in played_in_history:
            if c in seen and str(c) not in dups:
                dups.append(str(c))
            seen.add(c)
        errors.append(f"v histórii sú duplicitne zahrané karty: {dups}")

    return errors