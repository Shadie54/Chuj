# tutorial/scripted_ai.py
#
# Náhradník game/ai.py::AI pre naskriptovanú kapitolu tutoriálu.
#
# Myšlienka: Screen sa na ťah počítača pýta self.ai_players[i].decide_card().
# Ak na to miesto podstrčíme triedu, ktorá sa nerozhoduje, ale vracia
# kartu predpísanú scenárom, počítače odohrajú scenár BEZ jediného zásahu
# do Screen — a zadarmo zdedíme jeho pauzu pred ťahom, hod karty
# animáciou aj uzavretie štichu. Odpadá tým celý vlastný front ťahov,
# ktorý si tutoriál dovtedy viedol sám (pending_auto_plays).
#
# Trieda musí naplniť presne to rozhranie AI, ktoré Screen a
# PreparationHandler reálne používajú — nič viac.
#
# Pozri claude/08_TUTORIAL_REFACTOR_DESIGN.md §3.1.

from game.ai_memory import AIMemory


class ScriptedAI:
    """Počítač, ktorý hrá podľa scenára, nie podľa uváženia."""

    def __init__(self, player, director,
                 illumination: tuple[bool, bool] = (False, False),
                 declaration: str | None = None,
                 difficulty: str = "tutorial",
                 logger=None):
        self.player = player
        self.player_name = player.name
        self.difficulty = difficulty
        self.logger = logger
        self.director = director

        # Skutočná pamäť, nie atrapa — Screen._start_round() na nej volá
        # reset()/init_with_hand() a _process_waiting_trick() record_trick().
        self.memory = AIMemory(player.index)

        # Screen sa pozerá na last_strategy (bublina pri risku) a tipy na
        # last_sweep_result; musia existovať, aj keď sa tu nepoužívajú.
        self.last_strategy: str = ""
        self.last_sweep_result = None

        self.declaration_player: int | None = None
        self.declaration_type: str | None = None

        self._illumination = illumination
        self._declaration = declaration

    # ------------------------------------------------------------------
    # Rozhodovanie — celé podľa scenára
    # ------------------------------------------------------------------

    def decide_declaration(self) -> str | None:
        return self._declaration

    def decide_illumination(self, first_player_index: int,
                            all_scores=None) -> tuple[bool, bool]:
        # Vysvietenia, ktoré majú byť vidno od začiatku kola, nastavuje
        # režisér už pri rozdaní (scripted_round.apply_scripted_deal) —
        # tu sa preto štandardne nevysvecuje nič, nech sa to nerobí
        # dvakrát.
        return self._illumination

    def decide_card(self, playable, current_trick, trick_number,
                    all_scores=None):
        card = self.director.scripted_card(self.player.index, trick_number)
        if card is not None and card in playable:
            self.last_strategy = "SCRIPT"
            return card

        # Poistka. Nemala by nikdy zabrať — legálnosť celého scenára je
        # overená (pozri návrh §2) — ale keby sa scenár rozišiel s
        # pravidlami, Round.play_card() by kartu odmietol a
        # Screen._commit_ai_card() návratovú hodnotu nekontroluje, takže
        # by hra ticho zamrzla. Radšej zahráme prvú legálnu a nahlas o
        # tom povieme.
        self.last_strategy = "SCRIPT_FALLBACK"
        print(
            f"[tutoriál] VAROVANIE: scenár pre hráča {self.player.index} "
            f"({self.player_name}) v štichu {trick_number + 1} predpisuje "
            f"{card}, čo nie je medzi povolenými kartami "
            f"{[str(c) for c in playable]}. Hrám {playable[0]}."
        )
        return playable[0]

    # ------------------------------------------------------------------
    # Pamäť — rovnaké rozhranie ako AI
    # ------------------------------------------------------------------

    def record_trick(self, played_cards, winner_index, _trick_number):
        self.memory.record_trick(played_cards, winner_index)

    def record_illumination(self, player_index: int, leaf: bool, acorn: bool):
        self.memory.record_illumination(player_index, leaf, acorn)

    def record_declaration(self, player_index: int, declaration: str | None):
        if declaration:
            self.declaration_player = player_index
            self.declaration_type = declaration

    def reset_memory(self):
        self.memory.reset()
        self.declaration_player = None
        self.declaration_type = None

    def __repr__(self) -> str:
        return f"ScriptedAI({self.player_name})"
