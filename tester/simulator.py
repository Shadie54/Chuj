# tester/simulator.py
"""
Headless simulátor — hromadné odohranie hier (4x AIv2) a zber nálezov.

Spustenie:
    python -m tester.simulator --games 100
    python -m tester.simulator --games 500 --seed 42
    python -m tester.simulator --games 50 --no-sweep-watch

Výstup (Documents/Chuj/sim_output/):
    sim_summary.txt    — agregátny prehľad
    sim_findings.jsonl — jednotlivé nálezy (1 JSON objekt na riadok)
                         so seedom na reprodukciu v testeri
"""

import argparse
import json
import os
import random
import time
from dataclasses import dataclass, field

from game.game_state import GameState
from game.ai_v2.ai import AIv2
from config import NUM_PLAYERS, HIGH_SCORE_THRESHOLD


OUTPUT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "sim_output"
)


# ------------------------------------------------------------------
# Konfigurácia
# ------------------------------------------------------------------

@dataclass
class SimConfig:
    num_games: int = 100
    seed: int | None = None

    watch_illuminated_and_caught: bool = True
    illuminated_exclude_high_score: bool = True  # vylúč 90+ prípady (zámerne OK)
    watch_none_declaration_failed: bool = True
    watch_global_fallback: bool = True
    watch_sweep_result: bool = True  # sweep aktivovaný → zobral/nezobral všetko


# ------------------------------------------------------------------
# Zber nálezov
# ------------------------------------------------------------------

@dataclass
class Findings:
    records: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def add(self, record: dict):
        self.records.append(record)
        self.counts[record["type"]] = self.counts.get(record["type"], 0) + 1


# ------------------------------------------------------------------
# No-op logger pre GameState (aby sa nezapisovali herné logy na disk)
# ------------------------------------------------------------------

class _NoOpGameLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


# ------------------------------------------------------------------
# SimLogger — ľahký logger pre AI (per-ťah watchery)
# ------------------------------------------------------------------

class SimLogger:
    """
    Implementuje rozhranie, ktoré AIv2/AIEngine očakáva (log_strategy,
    log_sweep_pipeline, ...), ale nič neukladá — len preposiela
    zaujímavé udalosti do Findings.
    """

    def __init__(self, config: SimConfig, findings: Findings):
        self.config = config
        self.findings = findings
        # Kontext aktuálneho kola/ťahu — nastavuje runner
        self.round_context: dict = {}
        self.trick_number: int = 0
        # Hráči, ktorí v aktuálnom kole spustili SWEEP_COMMIT
        self.sweep_committers: set[str] = set()

    def log_strategy(self, player_name: str, strategy: str, details: str = ""):
        if self.config.watch_global_fallback and strategy == "GLOBAL_FALLBACK":
            self._record("global_fallback", player_name, strategy, details)
        if strategy == "SWEEP_COMMIT":
            self.sweep_committers.add(player_name)

    def _record(self, finding_type: str, player_name: str,
                strategy: str, details: str):
        self.findings.add({
            "type": finding_type,
            **self.round_context,
            "trick_number": self.trick_number + 1,
            "player": player_name,
            "strategy": strategy,
            "details": details,
        })

    def __getattr__(self, name):
        # Všetky ostatné logovacie volania (log_sweep_pipeline, ...) → no-op
        return lambda *args, **kwargs: None


# ------------------------------------------------------------------
# Jedna hra
# ------------------------------------------------------------------

def _run_single_game(game_index: int, config: SimConfig,
                     findings: Findings, stats: dict):
    player_names = [f"AI_{i}" for i in range(NUM_PLAYERS)]
    game_state = GameState(player_names, human_index=-1)
    game_state.logger = _NoOpGameLogger()
    game_state.setup_first_player()

    sim_logger = SimLogger(config, findings)

    ai_players = [
        AIv2(p, difficulty="hard", logger=sim_logger)
        for p in game_state.players
    ]

    while True:
        scores_at_start = [p.total_score for p in game_state.players]
        first_player = game_state.first_player_index

        game_state.start_new_round()
        rnd = game_state.current_round

        sim_logger.round_context = {
            "game_index": game_index,
            "round_number": game_state.round_number,
            "deal_seed": rnd.deal_seed,
            "first_player_index": first_player,
            "scores_at_round_start": scores_at_start,
        }
        sim_logger.sweep_committers = set()

        for ai in ai_players:
            ai.reset_memory()
            ai.memory.init_with_hand(
                game_state.players[ai.player.index].hand.cards
            )

        _run_preparation(game_state, ai_players)
        # first_player_index môže byť zmenený vyhlásením záväzku
        # ("nechytím nič"/"beriem všetko" preberá leadera) — aktualizuj
        # round_context AŽ TERAZ, po _run_preparation, nie pred ním
        sim_logger.round_context["first_player_index"] = rnd.current_leader_index
        rnd.finish_preparation()
        _run_tricks(game_state, ai_players, sim_logger)

        _round_end_watchers(config, findings, sim_logger, game_state,
                            scores_at_start)

        game_state.finish_round()
        stats["rounds_total"] = stats.get("rounds_total", 0) + 1

        if game_state.phase == "game_over":
            break

    stats["games_total"] = stats.get("games_total", 0) + 1
    for i, p in enumerate(game_state.players):
        stats.setdefault("final_scores", []).append(p.total_score)
        if game_state.loser is not None and game_state.loser.index == i:
            key = f"loser_AI_{i}"
            stats[key] = stats.get(key, 0) + 1


def _run_preparation(game_state: GameState, ai_players: list):
    """Vysvietenie + záväzok — rovnaký vzor ako tester_engine."""
    rnd = game_state.current_round
    scores = [p.total_score for p in game_state.players]

    # Vysvietenie — každý AI rozhodne
    for ai in ai_players:
        leaf, acorn = ai.decide_illumination(rnd.first_player_index, scores)
        if leaf or acorn:
            rnd.process_revealing(ai.player.index, leaf, acorn)
            for other in ai_players:
                other.record_illumination(ai.player.index, leaf, acorn)

    # Záväzok — v poradí od first_player, prvý vyhlásený platí
    order = [(rnd.first_player_index + i) % NUM_PLAYERS
             for i in range(NUM_PLAYERS)]
    for idx in order:
        decl = ai_players[idx].decide_declaration()
        if decl:
            rnd.process_declaration(idx, decl)
            for ai in ai_players:
                ai.record_declaration(idx, decl)
            break


def _run_tricks(game_state: GameState, ai_players: list,
                sim_logger: SimLogger):
    """Odohrá štichy kola (s prerušením pri zlyhanom zväzku)."""
    rnd = game_state.current_round

    while rnd.phase == "tricks":
        sim_logger.trick_number = rnd.trick_number

        while not rnd.current_trick.is_complete:
            player_idx = rnd.get_current_player_index()
            player = game_state.players[player_idx]
            ai = ai_players[player_idx]

            playable = player.hand.get_playable_cards(
                rnd.current_trick.lead_suit,
                rnd.trick_number,
                declaration_active=rnd.declaration_type is not None,
            )
            all_scores = [p.total_score for p in game_state.players]
            card = ai.decide_card(
                playable, rnd.current_trick, rnd.trick_number, all_scores
            )
            ok = rnd.play_card(player_idx, card)
            if not ok:
                raise RuntimeError(
                    f"Simulátor: AI_{player_idx} zahral nelegálnu kartu "
                    f"{card} (seed={rnd.deal_seed}, trick={rnd.trick_number + 1})"
                )

        played = list(rnd.current_trick.played_cards)
        winner = rnd.current_trick.get_winner_index()
        for ai in ai_players:
            ai.record_trick(played, winner, rnd.trick_number)
        rnd.finish_trick()

        # Zlyhaný záväzok → kolo končí okamžite
        if rnd.check_declaration_failed():
            rnd.phase = "scoring"
            break

        if rnd.phase == "tricks":
            rnd.start_trick()


def _round_end_watchers(config: SimConfig, findings: Findings,
                        sim_logger: SimLogger, game_state: GameState,
                        scores_at_start: list[int]):
    rnd = game_state.current_round

    # 1) Vysvietil + schytal vlastného horníka
    if config.watch_illuminated_and_caught:
        declaration_active = rnd.declaration_type in ("none", "all")
        if not declaration_active:
            sweep_winner = rnd._check_sweep()
            for suit in ("leaf", "acorn"):
                pidx = rnd.illuminated_by[suit]
                if pidx is None:
                    continue
                if (config.illuminated_exclude_high_score
                        and scores_at_start[pidx] >= HIGH_SCORE_THRESHOLD):
                    continue
                # Vylúč ak hráč spravil sweep (zámerné schytanie všetkého)
                if sweep_winner == pidx:
                    continue
                player = game_state.players[pidx]
                caught = any(
                    c.is_special and c.suit == suit
                    for c in player.penalty_cards
                )
                if caught:
                    findings.add({
                        "type": "illuminated_and_caught",
                        **sim_logger.round_context,
                        "player": player.name,
                        "suit": suit,
                    })

    # 2) "Nechytím nič" zlyhalo
    if config.watch_none_declaration_failed:
        if (rnd.declaration_type == "none"
                and rnd.declaration_player is not None
                and game_state.players[rnd.declaration_player].tricks_won > 0):
            findings.add({
                "type": "none_declaration_failed",
                **sim_logger.round_context,
                "player": game_state.players[rnd.declaration_player].name,
                "tricks_won": game_state.players[rnd.declaration_player].tricks_won,
            })

    # 3) Sweep aktivovaný → zobral/nezobral všetky bodované karty
    if config.watch_sweep_result and sim_logger.sweep_committers:
        sweep_winner_idx = rnd._check_sweep()
        for name in sim_logger.sweep_committers:
            pidx = int(name.split("_")[-1])
            success = (sweep_winner_idx == pidx)
            findings.add({
                "type": "sweep_success" if success else "sweep_failed",
                **sim_logger.round_context,
                "player": name,
                "penalty_points_taken": game_state.players[pidx].round_points,
            })


# ------------------------------------------------------------------
# Hlavný beh + výstup
# ------------------------------------------------------------------

def run(config: SimConfig):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    findings = Findings()
    stats: dict = {}
    rng = random.Random(config.seed)

    start = time.time()
    for game_idx in range(config.num_games):
        # Seed pre random modul (ovplyvní deal aj RiskSpecial rolls)
        random.seed(rng.randint(0, 2 ** 31))
        _run_single_game(game_idx, config, findings, stats)
        if (game_idx + 1) % 10 == 0 or game_idx + 1 == config.num_games:
            elapsed = time.time() - start
            print(f"  hra {game_idx + 1}/{config.num_games} "
                  f"({elapsed:.1f}s, nálezov: {len(findings.records)})")

    _write_output(config, findings, stats, time.time() - start)


def _write_output(config: SimConfig, findings: Findings,
                  stats: dict, elapsed: float):
    findings_path = os.path.join(OUTPUT_DIR, "sim_findings.jsonl")
    with open(findings_path, "w", encoding="utf-8") as f:
        for rec in findings.records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    summary_path = os.path.join(OUTPUT_DIR, "sim_summary.txt")
    final_scores = stats.get("final_scores", [])
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("SIMULÁCIA — SÚHRN\n")
        f.write("=" * 50 + "\n")
        f.write(f"Hier: {stats.get('games_total', 0)}\n")
        f.write(f"Kôl spolu: {stats.get('rounds_total', 0)}\n")
        f.write(f"Čas: {elapsed:.1f}s\n\n")
        if final_scores:
            f.write(f"Priemerné finálne skóre: "
                    f"{sum(final_scores) / len(final_scores):.1f}\n")
        for i in range(NUM_PLAYERS):
            f.write(f"Prehry AI_{i}: {stats.get(f'loser_AI_{i}', 0)}\n")
        f.write("\nNÁLEZY\n" + "-" * 50 + "\n")
        for ftype, count in sorted(findings.counts.items()):
            f.write(f"{ftype}: {count}\n")
        f.write(f"\nDetaily: {findings_path}\n")

    print(f"\nHotovo. Súhrn: {summary_path}")
    print(f"Nálezy: {findings_path} ({len(findings.records)} záznamov)")


def main():
    parser = argparse.ArgumentParser(description="CHUJ headless simulátor")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--no-illuminated-watch", action="store_true")
    parser.add_argument("--include-high-score-illuminated", action="store_true",
                        help="zahrň aj 90+ prípady schytania vlastného horníka")
    parser.add_argument("--no-none-watch", action="store_true")
    parser.add_argument("--no-fallback-watch", action="store_true")
    parser.add_argument("--no-sweep-result-watch", action="store_true")
    args = parser.parse_args()

    config = SimConfig(
        num_games=args.games,
        seed=args.seed,
        watch_illuminated_and_caught=not args.no_illuminated_watch,
        illuminated_exclude_high_score=not args.include_high_score_illuminated,
        watch_none_declaration_failed=not args.no_none_watch,
        watch_global_fallback=not args.no_fallback_watch,
        watch_sweep_result=not args.no_sweep_result_watch,
    )
    print(f"Spúšťam simuláciu: {config.num_games} hier "
          f"(seed={config.seed})")
    run(config)


if __name__ == "__main__":
    main()