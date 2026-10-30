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
from game.round_points import actual_round_points


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
        # Trestné body podľa zdroja — len body, ktoré hráč naozaj dostal
        # za karty (bežné kolo bez záväzku a bez "tichého"), s vysvietením
        # (×2) a pravidlom 90+ (horníci 0 b). Profil 2026-10-29.
        self.hearts_points = 0
        self.leaf_points = 0
        self.acorn_points = 0
        # Vysvietenie zvlášť podľa horníka
        self.illuminated_leaf = 0
        self.illuminated_leaf_caught = 0
        self.illuminated_acorn = 0
        self.illuminated_acorn_caught = 0
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

        # Skutočné body kola (nie len súčet kariet v štichoch) — rovnako
        # ako ich hra posiela do série bez trestných bodov. Čisté kolo =
        # kolo, ktoré sa hre ráta do bonusu za 5 čistých kôl.
        points = self._actual_round_points(game_state, player)
        self.worst_round = max(self.worst_round, points)
        if points <= 0:
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
        for suit, illuminated, is_that_hornik in (
            ("leaf", player.illuminated_leaf, lambda c: c.is_leaf_over),
            ("acorn", player.illuminated_acorn, lambda c: c.is_acorn_over),
        ):
            if not illuminated:
                continue
            caught = any(is_that_hornik(c) for c in player.penalty_cards)
            self.illuminated += 1
            setattr(self, f"illuminated_{suit}",
                    getattr(self, f"illuminated_{suit}") + 1)
            if caught:
                self.illuminated_caught_own += 1
                setattr(self, f"illuminated_{suit}_caught",
                        getattr(self, f"illuminated_{suit}_caught") + 1)

        self._record_card_points(game_state, player)

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

    def _actual_round_points(self, game_state, player) -> int:
        """Skutočné body kola — spoločná funkcia s panelom KOLO
        (game/round_points.py). Volá sa až po finish_round()."""
        hist = game_state.round_scores_history
        before = hist[-2][self.human_index] if len(hist) >= 2 else 0
        return actual_round_points(game_state.current_round, player,
                                   self.human_index, before)

    def _record_card_points(self, game_state, player):
        """Body za karty, ktoré hráč v kole naozaj dostal (rovnaká logika
        ako Player.finalize_round v bežnom kole). V kole so záväzkom a pri
        "tichom" sa karty nebodujú — vtedy nič."""
        from config import HIGH_SCORE_THRESHOLD
        rnd = game_state.current_round
        if rnd is None or rnd.declaration_type is not None:
            return
        if (player.round_flags or {}).get("sweep"):
            return
        leaf_ill = rnd.illuminated_by.get("leaf") is not None
        acorn_ill = rnd.illuminated_by.get("acorn") is not None
        # Skóre PRED týmto kolom (pravidlo 90+ sa posudzuje podľa neho):
        # predposledný riadok histórie skóre, v 1. kole 0.
        hist = game_state.round_scores_history
        before = hist[-2][self.human_index] if len(hist) >= 2 else 0
        for card in player.penalty_cards:
            pts = card.get_points(leaf_ill, acorn_ill)
            if card.is_leaf_over:
                if before < HIGH_SCORE_THRESHOLD:
                    self.leaf_points += pts
            elif card.is_acorn_over:
                if before < HIGH_SCORE_THRESHOLD:
                    self.acorn_points += pts
            elif card.suit == "heart":
                self.hearts_points += pts

    # ------------------------------------------------------------------

    def to_record(self, game_state, difficulties: list[str]) -> GameRecord:
        """Uzavrie hru do jedného záznamu pre profil."""
        loser_indices = [p.index for p in game_state.losers]
        self.note_difficulties(difficulties)
        return GameRecord(
            difficulties=list(difficulties),
            difficulty_changed=len(self._difficulties_seen) > 1,
            rounds=self.rounds,
            final_scores=[p.total_score for p in game_state.players],
            my_index=self.human_index,
            loser_index=loser_indices[0] if loser_indices else -1,
            loser_indices=loser_indices,
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
            hearts_points=self.hearts_points,
            leaf_points=self.leaf_points,
            acorn_points=self.acorn_points,
            illuminated_leaf=self.illuminated_leaf,
            illuminated_leaf_caught=self.illuminated_leaf_caught,
            illuminated_acorn=self.illuminated_acorn,
            illuminated_acorn_caught=self.illuminated_acorn_caught,
            bullets=game_state.players[self.human_index].bullets,
        )
