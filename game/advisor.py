# game/advisor.py
#
# Tipy pre ľudského hráča ("čo by zahrala AI a prečo").
#
# Advisor je tenká obálka nad existujúcou AI — kladie jej presne tie isté
# otázky ako pri rozhodovaní súperov (AI.decide_card), ale namiesto
# zahrania karty vráti Tip. AI.decide_card() herný stav nemení (pamäť sa
# plní oddelene cez record_*), takže vypýtať si tip je bezpečné a lacné
# (namerané: medián 0,1 ms, max 1,3 ms na ťah).
#
# Advisor NEPODVÁDZA — má vlastnú AIMemory, ktorú kŕmi to isté, čo vidí
# hráč: vlastnú ruku (init_with_hand) a verejné informácie (record_trick,
# record_illumination, record_declaration). Nevie, čo majú súperi v ruke.
#
# Táto vrstva je bez pygame — dá sa testovať headless a používajú ju
# rovnako ostrá hra aj tutoriál (vykreslenie rieši gui/tip_panel.py).

import random
from contextlib import contextmanager
from dataclasses import dataclass, field

from game.ai import AI
from game.card import Card
from game.player import Player
from game.tip_texts import illumination_reason, tip_text_for
from game.trick import Trick


@dataclass
class Tip:
    """
    Jedna rada pre hráča. `kind` je pripravený aj na budúce typy tipov
    ("illumination", "declaration", "sweep") — v prvej verzii sa tvorí
    len "card".
    """
    kind: str                              # "card" | "illumination" | ...
    recommended_card: Card | None = None
    # Karty, ktorých sa tip týka — pri karte je to tá jedna odporúčaná,
    # pri vysvietení to môžu byť oba horníky naraz. Panel kreslí toto.
    cards: list[Card] = field(default_factory=list)
    headline: str = ""                     # krátka veta do panela
    detail: str = ""                       # dlhší rozbor (tutoriál)
    # [(karta, váha, "Strategy.VARIANT"), ...] zostupne podľa váhy.
    # Napĺňa sa už teraz, hoci sa zatiaľ nevykresľuje — rozšírenie
    # panela o alternatívy tak bude zmena výlučne v kreslení.
    alternatives: list[tuple[Card, float, str]] = field(default_factory=list)
    source: str = ""                       # "AI_V2:AvoidTrick.UNDERPLAY" — debug/log

    def __post_init__(self):
        # Tip na kartu nemusí "cards" vypĺňať zvlášť — je to tá odporúčaná.
        if not self.cards and self.recommended_card is not None:
            self.cards = [self.recommended_card]

    @property
    def is_empty(self) -> bool:
        return not self.cards and not self.headline


class Advisor:
    """
    Radca pre jedného (ľudského) hráča. Drží vlastnú AI inštanciu, ktorá
    hrá VŽDY na "hard" — obtiažnosť súperov z nastavení sa sem zámerne
    neprenáša, rada má byť najlepšia, akú vieme dať.

    Kŕmenie pamäte je úmyselne rovnaké API ako u AI (record_trick,
    record_illumination, record_declaration, reset_memory), aby sa dal
    advisor v Screen-e obsluhovať v tých istých miestach ako súperi.
    """

    def __init__(self, player: Player, logger=None):
        self.player = player
        self.ai = AI(player, difficulty="hard", logger=logger)

    @staticmethod
    @contextmanager
    def _isolated_rng():
        """
        Odizoluje radcu od globálneho generátora náhody.

        AI rozhodovanie siaha na globálny random (RiskSpecial si hádže
        kocku, či zariskuje — game/ai_v2/strategies/risk_special.py).
        Keby sme sa AI pýtali na tip bez tejto izolácie, každý tip by
        odčerpal číslo z postupnosti a súperi by odvtedy hrali inak, než
        keby mal hráč tipy vypnuté. Overené: v 4 zo 40 hier sa priebeh
        naozaj rozišiel. Stav generátora preto uložíme a po rozhodnutí
        vrátime späť — tip je tak pre zvyšok hry úplne neviditeľný.
        """
        state = random.getstate()
        try:
            yield
        finally:
            random.setstate(state)

    # ------------------------------------------------------------------
    # Pamäť — presne to isté API ako AI (volá sa z gui/screen.py)
    # ------------------------------------------------------------------

    def reset_memory(self):
        self.ai.reset_memory()

    def init_with_hand(self, cards: list[Card]):
        self.ai.memory.init_with_hand(cards)

    def record_trick(self, played_cards, winner_index, trick_number):
        self.ai.record_trick(played_cards, winner_index, trick_number)

    def record_illumination(self, player_index: int, leaf: bool, acorn: bool):
        self.ai.record_illumination(player_index, leaf, acorn)

    def record_declaration(self, player_index: int, declaration: str | None):
        self.ai.record_declaration(player_index, declaration)

    # ------------------------------------------------------------------
    # Tipy
    # ------------------------------------------------------------------

    def tip_card(self, playable: list[Card], current_trick: Trick,
                 trick_number: int, all_scores: list[int]) -> Tip:
        """
        Akú kartu by na mieste hráča zahrala AI a prečo.

        Nemení herný stav ani pamäť — AI.decide_card() je čítacia
        operácia (overené testom test_advisor.py).
        """
        if not playable:
            return Tip(kind="card")

        with self._isolated_rng():
            card = self.ai.decide_card(
                playable, current_trick, trick_number, all_scores
            )

        trace = self.ai.engine_v2.last_trace
        strategy = trace.strategy if trace else ""
        variant = self.ai.last_strategy or (trace.variant if trace else "")
        detail = trace.detail if trace else ""

        # Sweep commit ide mimo selectora (AI.decide_card vracia kartu
        # priamo z pipeline) — vtedy trace patrí ešte minulému ťahu.
        if variant == "SWEEP_COMMIT":
            strategy, detail = "", ""
            alternatives = []
        else:
            alternatives = list(trace.alternatives) if trace else []

        headline, explanation = tip_text_for(strategy, variant, card)
        return Tip(
            kind="card",
            recommended_card=card,
            headline=headline,
            detail=explanation or detail,
            alternatives=alternatives,
            source=f"AI_V2:{strategy}.{variant}" if strategy else f"AI_V2:{variant}",
        )

    # Pomenovanie horníkov pre texty tipov.
    _SPECIAL_NAMES = {
        "leaf": ("zeleného horníka", "zelený horník (Q♠)"),
        "acorn": ("žaluďového horníka", "žaluďový horník (Q♣)"),
    }

    def tip_illumination(self, first_player_index: int,
                         all_scores: list[int]) -> Tip:
        """
        Vysvietiť horníka/horníkov, alebo nie?

        Radí len k tým horníkom, ktoré hráč naozaj drží — ak nemá ani
        jedného, vráti prázdny Tip (niet čo radiť). Rovnako ako
        tip_card() nemení herný stav.
        """
        hand = self.player.hand.cards
        held = [
            suit for suit in ("leaf", "acorn")
            if any(c.is_special and c.suit == suit for c in hand)
        ]
        if not held:
            return Tip(kind="illumination")

        # Rovnaká izolácia ako pri tipe na kartu — dnes síce rozhodovanie
        # o vysvietení náhodu nepoužíva, ale keby ju niekedy začalo, tip
        # by opäť ticho menil hru súperom.
        with self._isolated_rng():
            leaf_yes, acorn_yes = self.ai.decide_illumination(
                first_player_index, all_scores
            )
        debug = self.ai.declaration_advisor.last_illumination_debug or {}
        decisions = {"leaf": leaf_yes, "acorn": acorn_yes}

        cards = [
            c for c in hand
            if c.is_special and c.suit in held
        ]
        # Stabilné poradie: zelený (drahší) prvý.
        cards.sort(key=lambda c: 0 if c.suit == "leaf" else 1)

        codes, entries, sources = {}, {}, []
        for suit in held:
            entry = debug.get(suit) or ()
            entries[suit] = entry
            codes[suit] = entry[5] if len(entry) > 5 else ""
            sources.append(
                f"{suit}:{'yes' if decisions[suit] else 'no'}:{codes[suit]}"
            )

        if len(held) == 1:
            suit = held[0]
            verb = "Sviet" if decisions[suit] else "Nesviet"
            headline = f"{verb} {self._SPECIAL_NAMES[suit][0]}."
        else:
            yes_suits = [s for s in held if decisions[s]]
            if len(yes_suits) == 2:
                headline = "Sviet oboch horníkov."
            elif not yes_suits:
                headline = "Nesviet ani jedného horníka."
            else:
                headline = f"Sviet len {self._SPECIAL_NAMES[yes_suits[0]][0]}."

        # Pri jednom drženom horníkovi je v paneli dosť miesta na plné,
        # poskladané znenie (krytie + riziko + poistka, ak nejaká je).
        # Pri dvoch horníkoch (karty nad textom miesto vedľa neho, pozri
        # gui/tip_panel.py) je miesta podstatne menej — aj samotný
        # existujúci dlhý text sa tam vedel nezmestiť (overené meraním
        # cez skutočnú wrap logiku panela), takže tam ide vždy skrátená
        # verzia, bez ohľadu na to, či majú oba horníky rovnaký dôvod.
        if len(held) == 1:
            suit = held[0]
            entry = entries[suit]
            reserve_quality = entry[0] if len(entry) > 0 else None
            risk_level = entry[1] if len(entry) > 1 else None
            comp_breakdown = entry[4] if len(entry) > 4 else None
            reasons = [illumination_reason(
                codes[suit], reserve_quality=reserve_quality,
                risk_level=risk_level, comp_breakdown=comp_breakdown,
            )]
        else:
            symbols = {"leaf": "Q♠", "acorn": "Q♣"}
            reasons = [
                f"{symbols[s]} — "
                f"{illumination_reason(codes[s], short=True, reserve_quality=entries[s][0] if entries[s] else None)}."
                for s in ("leaf", "acorn") if s in held
            ]
        return Tip(
            kind="illumination",
            cards=cards,
            headline=headline,
            detail=" ".join(reasons),
            source="AI_ILLUM:" + "|".join(sources),
        )
