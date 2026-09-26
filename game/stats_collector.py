# game/stats_collector.py
#
# Zbiera údaje pre štatistiky profilu počas jednej hry.
#
# Princíp: record_round(game_state) sa volá hneď po
# GameState.finish_round(). V tej chvíli je v dosahu ešte úplne všetko —
# trestné karty aj s horníkmi, vysvietenie, záväzok aj to, či bol
# splnený, guličky a príznaky kola (player.round_flags). Stav sa čistí až
# pri ďalšom start_new_round(), takže neskôr už by tieto údaje neboli.
#
# Zberač NIČ nemení — len číta. Na konci hry z neho vypadne jeden
# GameRecord (pozri game/profile.py).

from game.profile import GameRecord


class StatsCollector:
    def __init__(self, human_index: int = 0):
        self.human_index = human_index
        self.rounds = 0
        self.clean_rounds = 0
        self.worst_round = 0
        self.longest_clean_streak = 0
        self._clean_streak = 0
        self.leaf_over_caught = 0
        self.acorn_over_caught = 0
        self.hearts_caught = 0
        self.illuminated = 0
        self.illuminated_caught_own = 0
        self.declared_none = 0
        self.declared_none_ok = 0
        self.declared_all = 0
        self.declared_all_ok = 0
        self.sweeps = 0
        self.streak_bonus = 0
        self.reset_100 = 0
        # Obtiažnosti sa berú až pri uzavretí hry; tu sledujeme len to,
        # či sa medzitým menili (main.py ich vie prepnúť aj za behu).
        self._difficulties_seen: set[tuple] = set()

    # ------------------------------------------------------------------

    def note_difficulties(self, difficulties: list[str]):
        """Zavolá sa pri štarte hry a po každej zmene v Nastaveniach."""
        self._difficulties_seen.add(tuple(difficulties))

    def record_round(self, game_state):
        """Prečíta práve uzavreté kolo. Musí sa volať hneď po
        GameState.finish_round(), kým sa stav hráča nevynuluje."""
        player = game_state.players[self.human_index]
        self.rounds += 1

        points = player.round_points
        self.worst_round = max(self.worst_round, points)
        if points == 0:
            self.clean_rounds += 1
            self._clean_streak += 1
            self.longest_clean_streak = max(
                self.longest_clean_streak, self._clean_streak
            )
        else:
            self._clean_streak = 0

        for card in player.penalty_cards:
            if card.is_leaf_over:
                self.leaf_over_caught += 1
            elif card.is_acorn_over:
                self.acorn_over_caught += 1
            elif card.suit == "heart":
                self.hearts_caught += 1

        # Vysvietenie: zaujíma nás nielen koľkokrát hráč vysvietil, ale
        # hlavne ako často mu vysvietený horník napokon spadol do
        # vlastného štichu (= dvojnásobná daň za vlastné rozhodnutie).
        for illuminated, is_that_hornik in (
            (player.illuminated_leaf, lambda c: c.is_leaf_over),
            (player.illuminated_acorn, lambda c: c.is_acorn_over),
        ):
            if not illuminated:
                continue
            self.illuminated += 1
            if any(is_that_hornik(c) for c in player.penalty_cards):
                self.illuminated_caught_own += 1

        if player.declaration == "none":
            self.declared_none += 1
            if player.declaration_fulfilled:
                self.declared_none_ok += 1
        elif player.declaration == "all":
            self.declared_all += 1
            if player.declaration_fulfilled:
                self.declared_all_ok += 1

        flags = player.round_flags or {}
        # Pozor na rozdiel oproti GameState.last_sweep_player: ten hovorí
        # len "pozbieral všetky trestné karty". Ak v kole beží záväzok,
        # Round.score_round() pre hráča finalize_round() vôbec nezavolá a
        # bonus −10 nedostane. Do štatistiky rátame len sweepy, ktoré sa
        # naozaj vyplatili — inak by číslo sľubovalo body, ktoré nikdy
        # neprišli.
        if flags.get("sweep"):
            self.sweeps += 1
        if flags.get("streak_bonus"):
            self.streak_bonus += 1
        if flags.get("reset_100"):
            self.reset_100 += 1

    # ------------------------------------------------------------------

    def to_record(self, game_state, difficulties: list[str]) -> GameRecord:
        """Uzavrie hru do jedného záznamu pre profil."""
        loser = game_state.loser
        self.note_difficulties(difficulties)
        return GameRecord(
            difficulties=list(difficulties),
            difficulty_changed=len(self._difficulties_seen) > 1,
            rounds=self.rounds,
            final_scores=[p.total_score for p in game_state.players],
            my_index=self.human_index,
            loser_index=loser.index if loser is not None else -1,
            clean_rounds=self.clean_rounds,
            worst_round=self.worst_round,
            longest_clean_streak=self.longest_clean_streak,
            leaf_over_caught=self.leaf_over_caught,
            acorn_over_caught=self.acorn_over_caught,
            hearts_caught=self.hearts_caught,
            illuminated=self.illuminated,
            illuminated_caught_own=self.illuminated_caught_own,
            declared_none=self.declared_none,
            declared_none_ok=self.declared_none_ok,
            declared_all=self.declared_all,
            declared_all_ok=self.declared_all_ok,
            sweeps=self.sweeps,
            streak_bonus=self.streak_bonus,
            reset_100=self.reset_100,
            bullets=game_state.players[self.human_index].bullets,
        )
