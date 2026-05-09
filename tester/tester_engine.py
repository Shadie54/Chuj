# tester/tester_engine.py

from dataclasses import dataclass, field
from game.card import Card
from game.player import Player
from game.ai import AI
from game.round import Round
from tester.scenario import Scenario, validate_scenario, TrickHistory
from tester.tester_logger import TesterLogger, LogEntry
from config import NUM_PLAYERS


# ------------------------------------------------------------------
# StepResult — výstup jedného ťahu
# ------------------------------------------------------------------

@dataclass
class StepResult:
    """
    Výsledok jedného ťahu (AI zahrá jednu kartu).

    Ak sa ťahom dokončil štich:
        trick_completed=True, trick_winner+trick_points sú nastavené

    Ak sa ťahom dokončilo kolo:
        round_completed=True (po poslednom štiche)
    """
    player_index: int
    player_name: str
    card_played: Card
    log_entries: list[LogEntry]
    trick_completed: bool = False
    trick_winner: int | None = None
    trick_points: int = 0
    round_completed: bool = False


# ------------------------------------------------------------------
# EngineState — snapshot pre GUI
# ------------------------------------------------------------------

@dataclass
class EngineState:
    """Aktuálny stav scenára — všetko čo GUI potrebuje na vykreslenie."""
    hands: dict[int, list[Card]]
    current_trick_cards: list[tuple[int, Card]]
    current_player_index: int
    trick_number: int
    round_points: dict[int, int]
    total_scores: dict[int, int]
    illuminations: dict[str, int | None]
    declarations: dict[int, str | None]
    is_complete: bool
    completed_tricks: list[TrickHistory] = field(default_factory=list)


# ------------------------------------------------------------------
# TesterEngine — hlavný engine
# ------------------------------------------------------------------

class TesterEngine:
    """
    Bezhlavá logika testera.

    Načíta scenár, prehrá históriu, a poskytne API pre step-by-step
    odohranie zvyšku kola.

    Použitie:
        engine = TesterEngine(scenario)
        while not engine.is_complete():
            result = engine.next_step()
            # zobraz result v GUI
    """

    def __init__(self, scenario: Scenario):
        # Validácia scenára
        errors = validate_scenario(scenario)
        if errors:
            raise ValueError(
                "Scenár obsahuje chyby:\n  - "
                + "\n  - ".join(errors)
            )

        self.scenario = scenario
        self.logger = TesterLogger()

        # Tieto sa nastavia v _load_scenario()
        self.players: list[Player] = []
        self.ais: dict[int, AI] = {}
        self.round: Round | None = None
        self._is_complete: bool = False
        self._pending_new_trick: bool = False
        self._last_trick_cards: list[tuple[int, Card]] = []

        # História štichov ktoré sa odohrali — vrátane úvodnej z scenára
        # Engine ich tu zhromažďuje pre GUI ('completed_tricks')
        self.completed_tricks: list[TrickHistory] = []
        self.illumination_logs: list[LogEntry] = []
        # Snapshoty pre Back — uložené pred každým next_step()
        # Každá entry je tuple: (engine_state_dict, last_step)
        self._snapshots: list = []

        self._load_scenario()

    # ------------------------------------------------------------------
    # Scenár loader
    # ------------------------------------------------------------------

    def _load_scenario(self):
        """Načíta scenár a pripraví engine na štart."""
        sc = self.scenario

        # 1. Vytvor 4 hráčov (vo Fáze 1 všetci AI)
        self.players = [
            Player(name=f"AI_{i}", is_human=False, index=i)
            for i in range(NUM_PLAYERS)
        ]

        # 2. Vytvor 4 AI inštancie s TesterLogger
        self.ais = {}
        for i in range(NUM_PLAYERS):
            ai = AI(
                player=self.players[i],
                difficulty="hard",
                logger=self.logger,
            )
            self.ais[i] = ai

        # 3. Vytvor Round (bez deal() — karty rozdáme manuálne)
        self.round = Round(
            players=self.players,
            first_player_index=sc.first_player_index,
        )

        # 4. Rozdaj karty manuálne (obíď deal())
        for i in range(NUM_PLAYERS):
            self.players[i].receive_cards(list(sc.hands[i]))
        for i, score in sc.scores.items():
            self.players[i].total_score = score
        # 5. Manuálne nastav fázu (deal() to inak robí na konci)
        self.round.phase = "preparation"

        # 6. Inicializuj AIMemory pôvodnou rukou (pred prehratím histórie!)
        for i, ai in self.ais.items():
            ai.memory.init_with_hand(self.players[i].hand.cards)

        # 7. Aplikuj iluminácie
        self._apply_illuminations()

        # 8. Aplikuj záväzky
        self._apply_declarations()

        # 9. Ukončí prípravu, spustí prvý štich
        self.round.finish_preparation()

        # 10. Prehrať históriu štichov
        self._replay_history()

    def _apply_illuminations(self):
        sc = self.scenario

        # AI rozhodnutia
        decisions: dict[int, tuple[bool, bool]] = {}
        for player_idx in range(NUM_PLAYERS):
            self.logger.start_capture()
            scores = [self.players[i].total_score for i in range(NUM_PLAYERS)]
            leaf, acorn = self.ais[player_idx].decide_illumination(
                sc.first_player_index, scores
            )
            captured = self.logger.get_capture()
            hand = self.players[player_idx].hand.cards
            has_leaf = any(c.is_leaf_over for c in hand)
            has_acorn = any(c.is_acorn_over for c in hand)
            for entry in captured:
                if entry.kind != "illumination":
                    self.illumination_logs.append(entry)
                    continue
                if entry.suit == "leaf" and not has_leaf:
                    continue
                if entry.suit == "acorn" and not has_acorn:
                    continue
                self.illumination_logs.append(entry)
            decisions[player_idx] = (leaf, acorn)

        # Aplikuj override zo scenára
        for suit in ("leaf", "acorn"):
            if suit not in sc.illuminations:
                continue  # žiadny override → AI rozhodnutie sa zachová
            override_holder = sc.illuminations[suit]
            if override_holder is None:
                # Explicitne žiadne vysvietenie — vynuluj AI rozhodnutia
                for pidx in range(NUM_PLAYERS):
                    leaf, acorn = decisions[pidx]
                    decisions[pidx] = (
                        (False, acorn) if suit == "leaf" else (leaf, False)
                    )
                continue
            # Override konkrétneho hráča
            for pidx in range(NUM_PLAYERS):
                leaf, acorn = decisions[pidx]
                decisions[pidx] = (
                    (False, acorn) if suit == "leaf" else (leaf, False)
                )
            hand = self.players[override_holder].hand.cards
            has_special = any(
                c.is_leaf_over if suit == "leaf" else c.is_acorn_over
                for c in hand
            )
            if not has_special:
                continue
            leaf, acorn = decisions[override_holder]
            decisions[override_holder] = (
                (True, acorn) if suit == "leaf" else (leaf, True)
            )

        # Aplikuj všetky rozhodnutia
        for player_idx, (leaf, acorn) in decisions.items():
            if not (leaf or acorn):
                continue
            self.round.process_revealing(player_idx, leaf, acorn)
            for ai in self.ais.values():
                ai.record_illumination(player_idx, leaf, acorn)

    def _apply_declarations(self):
        """Aplikuje záväzky zo scenára."""
        sc = self.scenario

        for player_idx, decl in sc.declarations.items():
            self.round.process_declaration(player_idx, decl)
            for ai in self.ais.values():
                ai.record_declaration(player_idx, decl)

    def _replay_history(self):
        """
        Prehrá históriu zo scenára.

        Pre každý štich:
        1. Round už má aktívny current_trick (z finish_preparation alebo
           z predošlého finish_trick)
        2. Pre každú kartu zavolá round.play_card()
        3. Po 4. karte zavolá ai.record_trick() na všetkých AI
        4. Zavolá round.finish_trick() — to spustí start_trick() pre ďalší
           štich implicitne? NIE — finish_trick len uzatvorí, ďalší trick
           treba spustiť ručne cez start_trick() — POZOR

        Pozn: round.finish_trick() **nezavoláva** start_trick(),
        ale po phase != "scoring" engine musí spustiť ďalší trick ručne.
        """
        sc = self.scenario

        # Koľko štichov z histórie prehrať
        if sc.start_after_trick is None:
            replay_count = len(sc.history)
        else:
            replay_count = sc.start_after_trick

        for trick_idx in range(replay_count):
            th = sc.history[trick_idx]
            self._replay_one_trick(th)

    def _replay_one_trick(self, th: TrickHistory):
        """Prehrá jeden štich z histórie."""
        # Pre každú kartu v štiche v poradí ako sa hralo
        for player_idx, card in th.cards:
            success = self.round.play_card(player_idx, card)
            if not success:
                raise RuntimeError(
                    f"Nepodarilo sa zahrať {card} pre hráča {player_idx} "
                    f"v histórii (možno karta nie je playable?)"
                )

        # štich je kompletný — synchronizuj AI memory
        played_cards = list(self.round.current_trick.played_cards)
        winner_index = self.round.current_trick.get_winner_index()
        trick_number = self.round.trick_number

        for ai in self.ais.values():
            ai.record_trick(played_cards, winner_index, trick_number)

        # Uzatvor štich v Round (priradí karty víťazovi, inkrementuje counter)
        self.round.finish_trick()

        # Zaznamenaj do completed_tricks pre GUI
        self.completed_tricks.append(TrickHistory(
            leader=th.leader,
            cards=played_cards,
            winner=winner_index,
        ))

        # Spusti ďalší trick ak kolo neskončilo
        if self.round.phase != "scoring":
            self.round.start_trick()
        else:
            self._is_complete = True

    # ------------------------------------------------------------------
    # Hlavné API
    # ------------------------------------------------------------------

    def next_step(self) -> StepResult:
        """
        Odohrá ďalší ťah aktuálneho hráča (vždy AI vo Fáze 1).

        Vracia StepResult s informáciami o ťahu, prípadnom dokončení
        štichu a kola.
        """
        if self._is_complete:
            raise RuntimeError(
                "Engine: kolo už je dokončené, next_step() nemá čo robiť"
            )

        # Snapshot pre prípadný Back
        self._snapshot_state()

        # Ak predošlý ťah dokončil štich, teraz vyčistíme stôl a spustíme
        # nový trick. Toto je tu (a nie v _finalize_trick) preto, aby GUI
        # videlo kompletný 4-kartový štich medzi dvoma Next stlačeniami.
        if self._pending_new_trick:
            self.round.start_trick()
            self._pending_new_trick = False
            self._last_trick_cards = []

        if self.round.current_trick is None:
            raise RuntimeError(
                "Engine: current_trick je None — nečakaný stav"
            )

        # Aktuálny hráč
        player_idx = self.round.get_current_player_index()
        player = self.players[player_idx]
        ai = self.ais[player_idx]

        # Playable karty
        playable = player.hand.get_playable_cards(
            self.round.current_trick.lead_suit,
            self.round.trick_number,
        )

        if not playable:
            raise RuntimeError(
                f"Engine: hráč {player_idx} nemá playable karty — "
                f"{player.hand.cards}"
            )

        # Zachyt logy z tohto rozhodovania
        self.logger.start_capture()
        card = ai.decide_card(
            playable,
            self.round.current_trick,
            self.round.trick_number,
        )
        captured = self.logger.get_capture()

        # Zahraj kartu
        success = self.round.play_card(player_idx, card)
        if not success:
            raise RuntimeError(
                f"Engine: AI {player_idx} chcel zahrať {card}, "
                f"ale Round.play_card vrátil False"
            )

        # Postaveniame StepResult
        result = StepResult(
            player_index=player_idx,
            player_name=player.name,
            card_played=card,
            log_entries=captured,
        )

        # Dokončenie štichu?
        if self.round.current_trick.is_complete:
            self._finalize_trick(result)

        return result

    def next_step_override(self, override_card: Card) -> StepResult:
        """
        Override variant next_step() — namiesto AI rozhodnutia použije
        kartu zadanú užívateľom.

        AI stále vyhodnotí situáciu (zachytí reasoning), ale výsledok
        ignoruje. Použije sa override_card.

        override_card MUSÍ byť v playable kartách aktívneho hráča.
        """
        if self._is_complete:
            raise RuntimeError(
                "Engine: kolo už je dokončené, next_step_override() "
                "nemá čo robiť"
            )

        # Snapshot pre prípadný Back
        self._snapshot_state()

        # Ak predošlý ťah dokončil štich, vyčisti stôl
        if self._pending_new_trick:
            self.round.start_trick()
            self._pending_new_trick = False
            self._last_trick_cards = []

        if self.round.current_trick is None:
            raise RuntimeError(
                "Engine: current_trick je None — nečakaný stav"
            )

        # Aktuálny hráč
        player_idx = self.round.get_current_player_index()
        player = self.players[player_idx]
        ai = self.ais[player_idx]

        # Playable karty
        playable = player.hand.get_playable_cards(
            self.round.current_trick.lead_suit,
            self.round.trick_number,
        )

        # Override karta musí byť v playable
        if override_card not in playable:
            raise RuntimeError(
                f"Engine: override karta {override_card} nie je v "
                f"playable {playable}"
            )

        # Zachyť reasoning AI (vyhodnoť ale výsledok ignoruj)
        self.logger.start_capture()
        ai_card = ai.decide_card(
            playable,
            self.round.current_trick,
            self.round.trick_number,
        )
        captured = self.logger.get_capture()

        # Pridaj override info do log entries
        self.logger.log_strategy(
            player.name,
            "OVERRIDE",
            f"AI by zahrala {ai_card}, override → {override_card}",
        )
        # Re-capture aby sme dostali aj override entry
        captured = self.logger.get_capture()

        # Zahraj override kartu
        success = self.round.play_card(player_idx, override_card)
        if not success:
            raise RuntimeError(
                f"Engine: override {override_card} odmietnutý "
                f"Round.play_card-om"
            )

        # Postaveniame StepResult
        result = StepResult(
            player_index=player_idx,
            player_name=player.name,
            card_played=override_card,
            log_entries=captured,
        )

        # Dokončenie štichu?
        if self.round.current_trick.is_complete:
            self._finalize_trick(result)

        return result

    def prepare_for_override(self):
        """
        Pripraví engine na override — ak je čakajúci nový trick,
        spustí ho. Volá sa z GUI keď užívateľ vstúpi do override modu,
        aby `current_trick` existoval a GUI vedelo zistiť playable karty.

        Nenastáva snapshot — ten sa robí až pri samotnom override ťahu.
        """
        if self._is_complete:
            return
        if self._pending_new_trick:
            self.round.start_trick()
            self._pending_new_trick = False
            self._last_trick_cards = []

    def _finalize_trick(self, result: StepResult):
        """Pomocná metóda — dokončí štich a aktualizuje result."""
        played_cards = list(self.round.current_trick.played_cards)
        winner_index = self.round.current_trick.get_winner_index()
        trick_number = self.round.trick_number
        leader = self.round.current_trick.leader_index
        trick_points = self.round.current_trick.total_base_points

        # Ulož pre GUI — current_trick bude None po finish_trick()
        self._last_trick_cards = played_cards

        # Synchronizuj AIMemory pred finish_trick
        for ai in self.ais.values():
            ai.record_trick(played_cards, winner_index, trick_number)

        # Round uzatvorí štich — priradí karty víťazovi, inkrementuje counter
        self.round.finish_trick()

        # Zaznamenaj pre GUI
        self.completed_tricks.append(TrickHistory(
            leader=leader,
            cards=played_cards,
            winner=winner_index,
        ))

        # Aktualizuj result
        result.trick_completed = True
        result.trick_winner = winner_index
        result.trick_points = trick_points

        # Kolo skončilo?
        if self.round.phase == "scoring":
            self.round.score_round()
            self._is_complete = True
            result.round_completed = True
        else:
            # Nezačíname nový trick HNEĎ — flag pre next_step() aby GUI
            # mohlo zobraziť kompletný 4-kartový štich pred vyčistením.
            self._pending_new_trick = True

    def play_human_card(self, card: Card) -> StepResult:
        """
        Pre 3+1 mód v Fáze 3 — človek manuálne vybral kartu.
        Vo Fáze 1 sa nepoužíva.
        """
        raise NotImplementedError(
            "play_human_card() bude implementovaná v Fáze 3 (3+1 mód)"
        )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        """Vráti True ak kolo skončilo."""
        return self._is_complete

    def current_state(self) -> EngineState:
        """Vráti snapshot pre GUI."""
        if self.round is None:
            raise RuntimeError("Engine: round nie je inicializovaný")

        # Aktuálny štich — môže byť None ak práve skončil posledný
        # alebo ak je _pending_new_trick (4. karta zahraná, čaká sa na Next)
        if self._pending_new_trick:
            current_trick_cards = list(self._last_trick_cards)
        elif self.round.current_trick is not None:
            current_trick_cards = list(self.round.current_trick.played_cards)
        else:
            current_trick_cards = []

        # Current player — ak kolo skončilo, vráť 0 ako placeholder
        if self._is_complete:
            current_player = 0
        else:
            current_player = self.round.get_current_player_index()

        return EngineState(
            hands={
                i: list(self.players[i].hand.cards)
                for i in range(NUM_PLAYERS)
            },
            current_trick_cards=current_trick_cards,
            current_player_index=current_player,
            trick_number=self.round.trick_number,
            round_points={
                i: self.players[i].round_points
                for i in range(NUM_PLAYERS)
            },
            total_scores={
                i: self.players[i].total_score
                for i in range(NUM_PLAYERS)
            },
            illuminations={
                "leaf": self.round.illuminated_by["leaf"],
                "acorn": self.round.illuminated_by["acorn"],
            },
            declarations=dict(self.scenario.declarations),
            is_complete=self._is_complete,
            completed_tricks=list(self.completed_tricks),
        )

    # ------------------------------------------------------------------
    # Snapshot / Back (rollback)
    # ------------------------------------------------------------------

    def _snapshot_state(self):
        """
        Uloží snapshot aktuálneho stavu engine.
        Volané pred každým next_step() aby sa dalo vrátiť.

        DÔLEŽITÉ: deepcopy musí byť atomická pre players + round + ais,
        lebo round.players a ais[i].player sú referencie na rovnaké
        Player objekty. Deepcopy v jednom volaní zachová referenčnú
        štruktúru.
        """
        import copy

        # Deepcopy v jednom volaní — zachová zdieľané referencie
        # medzi players, round.players, ais[i].player
        bundle = copy.deepcopy({
            "players": self.players,
            "ais": self.ais,
            "round": self.round,
        })

        snapshot = {
            "players": bundle["players"],
            "ais": bundle["ais"],
            "round": bundle["round"],
            "is_complete": self._is_complete,
            "pending_new_trick": self._pending_new_trick,
            "last_trick_cards": list(self._last_trick_cards),
            "completed_tricks": list(self.completed_tricks),
            "logger_full_history": list(self.logger.full_history),
            "logger_current_capture": list(self.logger.current_capture),
        }
        self._snapshots.append(snapshot)

    def can_go_back(self) -> bool:
        """Vráti True ak sa dá ísť o ťah späť."""
        return len(self._snapshots) > 0

    def go_back(self):
        """
        Vráti engine o jeden ťah späť.
        Obnoví stav z posledného snapshotu.
        """
        if not self.can_go_back():
            raise RuntimeError("Engine: žiadny snapshot na vrátenie")

        snapshot = self._snapshots.pop()
        self.players = snapshot["players"]
        self.ais = snapshot["ais"]
        self.round = snapshot["round"]
        self._is_complete = snapshot["is_complete"]
        self._pending_new_trick = snapshot["pending_new_trick"]
        self._last_trick_cards = snapshot["last_trick_cards"]
        self.completed_tricks = snapshot["completed_tricks"]

        # Logger restore
        self.logger.full_history = snapshot["logger_full_history"]
        self.logger.current_capture = snapshot["logger_current_capture"]

        # Re-bind logger v AI inštanciách (deepcopy vytvoril vlastné
        # logger inštancie, my chceme aby všetky AI logovali do nášho).
        for ai in self.ais.values():
            ai.logger = self.logger
            ai.sweep_pipeline.logger = self.logger
            ai.declaration_advisor.logger = self.logger
            ai.selector.logger = self.logger

        # Sanity check — po restore musí byť round.players[i] is players[i]
        for i in range(NUM_PLAYERS):
            if self.round.players[i] is not self.players[i]:
                raise RuntimeError(
                    f"Engine: po go_back() round.players[{i}] != players[{i}] "
                    f"— deepcopy nezachoval referencie"
                )
            if self.ais[i].player is not self.players[i]:
                raise RuntimeError(
                    f"Engine: po go_back() ais[{i}].player != players[{i}] "
                    f"— deepcopy nezachoval referencie"
                )
    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self):
        """Reštartuje scenár od začiatku."""
        self.logger.reset()
        self.players = []
        self.ais = {}
        self.round = None
        self._is_complete = False
        self._pending_new_trick = False
        self._last_trick_cards = []
        self.completed_tricks = []
        self._snapshots = []
        self._load_scenario()