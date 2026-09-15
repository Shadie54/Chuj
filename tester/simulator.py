# tester/simulator.py
"""
Headless simulátor — hromadné odohranie hier (4x AIv2) a zber nálezov.

Spustenie:
    python -m tester.simulator --games 100
    python -m tester.simulator --games 500 --seed 42
    python -m tester.simulator --games 50 --no-sweep-failed-watch

Výstup (Documents/Chuj/sim_output/):
    sim_summary.txt    — agregátny prehľad
    sim_findings.jsonl — jednotlivé nálezy (1 JSON objekt na riadok)
                         so seedom na reprodukciu v testeri
"""

import os
import sys

# PYTHONHASHSEED musí byť nastavený PRED štartom interpretera — inak sa
# medzi behmi náhodne mení poradie iterácie cez set/dict s reťazcovými
# kľúčmi (napr. AIMemory.void_suits), čo robí --seed nereprodukovateľným
# aj keď je samotné rozdanie kariet už deterministické (pozri
# game/round.py). Reštartuje sa raz s fixovaným PYTHONHASHSEED=0, ak ešte
# nebol nastavený. Platí len pri samostatnom spustení (python -m
# tester.simulator) — pri importe (napr. z tester/sim_screen.py) sa guard
# rieši na úrovni toho vstupného bodu.
#
# Reštart ide cez subprocess.run vo forme "-m tester.simulator" (presne
# ako v hlavičkovom docstringu), nie cez os.execv so sys.orig_argv —
# sys.orig_argv pri spustení cez IDE (napr. PyCharm run/debug) obsahuje
# IDE/debug launcher namiesto tohto skriptu, takže reštart cezeň potichu
# zlyhá bez pripojeného debug serveru a proces skončí s "exit code 0"
# bez výstupu. Nájdené 2026-09-04 pri prvom nasadení pôvodného guardu.
if __name__ == "__main__" and os.environ.get("PYTHONHASHSEED") != "0":
    import subprocess
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, "-m", "tester.simulator"] + sys.argv[1:],
        env=env,
    )
    sys.exit(result.returncode)

import argparse
import json
import random
import time
from dataclasses import dataclass, field

from game.game_state import GameState
from game.ai_v2.ai import AIv2
from game.ai import AI
from config import NUM_PLAYERS, HIGH_SCORE_THRESHOLD


OUTPUT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "sim_output"
)

# Súboj v1 vs v2 (duel_mode) — rotácia dvojíc sedadiel, ktoré hrajú v2.
# 3 rozdelenia 4 sedadiel na dvojice x 2 orientácie = 6 kombinácií, cyklicky
# podľa game_index. Cieľ: pri dostatočnom počte hier sa vyruší pozičný
# efekt (kto sedí na ktorom mieste pri stole naprieč celými hrami — nie
# first_player v rámci hry, to už rotuje samo).
_DUEL_SEAT_PATTERNS = [
    {0, 1}, {2, 3},
    {0, 2}, {1, 3},
    {0, 3}, {1, 2},
]


def _duel_v2_seats(game_index: int) -> set:
    """Vráti množinu indexov sedadiel, ktoré v danej hre hrajú v2."""
    return _DUEL_SEAT_PATTERNS[game_index % len(_DUEL_SEAT_PATTERNS)]


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
    watch_forced_lead_trap: bool = True
    # Sweep aktivovaný → zobral/nezobral všetko. Samostatné flagy, aby sa
    # dalo sledovať len úspešné, len neúspešné, alebo oboje naraz.
    watch_sweep_success: bool = True
    watch_sweep_failed: bool = True
    # Výskum §14 (90+ pravidlo vs. sweep pipeline) — čisto pozorovací watcher,
    # zaznamená KAŽDÉ vyhodnotenie sweep pipeline pri hráčovi s 90+ bodmi.
    watch_sweep_90_eval: bool = True
    # Schytávanie horníkov — pre KAŽDÉ kolo (mimo all/none záväzkov)
    # zaznamená, kto schytal ktorého horníka a či bol vysvietený (a teda či
    # išlo o "vlastný" schytaný vysvietený horník). Všeobecný watcher,
    # nezávislý od konkrétnej stratégie — pôvodne vznikol pri VoidBait
    # výskume (2026-09-10, zamietnuté — viď handoff doc), ponechaný ako
    # trvalá regresná infraštruktúra.
    watch_hornik_capture: bool = True
    # EV znamienkový audit (§8 TODO) — zaznamená KAŽDÚ L6 súťaž medzi 2+
    # sweep kandidátmi, aby sa dalo overiť, či súčasný vzorec
    # `ev = P*(-10) - (1-P)*damage` niekedy vyberie iného kandidáta než
    # opravený `ev = P*(-10) + (1-P)*damage`.
    watch_sweep_ev_audit: bool = True
    # Gate2 audit (§16 TODO A3) — keď Gate2 (_gate2_min_hand_strength)
    # zablokuje sweep (žiadny z 3 scenárov: hearts-driven/control-driven/
    # hornik-bait), napriek tomu dopočíta L2 (capacity/to_capture model),
    # aby bolo vidno, či by L2 hodnotil ruku ako STRONG/MEDIUM.
    watch_gate2_audit: bool = True

    # Súboj v1 vs v2 — namiesto 4x AIv2 hrajú 2 sedadlá starým systémom
    # (AI, use_new_system=False) a 2 nový (use_new_system=True), rotujúc
    # naprieč hrami (_duel_v2_seats). Difficulty "hard" pre oba tímy.
    duel_mode: bool = False

    # Decision-divergence watcher (test-plan krok 4) — v2 skutočne hrá
    # ("pravda"), v1 beží paralelne ako "shadow" pozorovateľ s vlastnou,
    # synchronizovanou pamäťou (dostáva rovnaké record_trick/illumination/
    # declaration ako primary, ale jeho voľba karty sa nehrá). Pri každom
    # ťahu sa porovná, akú kartu by zahral v1 vs čo skutočne zahral v2 —
    # rozdiel sa zaloguje ako nález "decision_divergence".
    divergence_mode: bool = False


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
        if self.config.watch_forced_lead_trap and strategy == "FORCED_LEAD_TRAP":
            self._record("forced_lead_trap", player_name, strategy, details)
        if self.config.watch_sweep_90_eval and strategy == "SWEEP_90_EVAL":
            self._record("sweep_90_eval", player_name, strategy, details)
        if self.config.watch_sweep_ev_audit and strategy == "SWEEP_EV_AUDIT":
            self._record("sweep_ev_audit", player_name, strategy, details)
        if self.config.watch_gate2_audit and strategy == "GATE2_AUDIT":
            self._record("gate2_audit", player_name, strategy, details)
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

    shadow_players = None
    if config.duel_mode:
        v2_seats = _duel_v2_seats(game_index)
        ai_players = [
            AI(p, difficulty="hard", logger=sim_logger,
               use_new_system=(p.index in v2_seats))
            for p in game_state.players
        ]
    else:
        ai_players = [
            AIv2(p, difficulty="hard", logger=sim_logger)
            for p in game_state.players
        ]
        if config.divergence_mode:
            shadow_players = [
                AI(p, difficulty="hard", logger=_NoOpGameLogger(),
                   use_new_system=False)
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
        if shadow_players is not None:
            for shadow in shadow_players:
                shadow.reset_memory()
                shadow.memory.init_with_hand(
                    game_state.players[shadow.player.index].hand.cards
                )

        _run_preparation(game_state, ai_players, shadow_players)
        # first_player_index môže byť zmenený vyhlásením záväzku
        # ("nechytím nič"/"beriem všetko" preberá leadera) — aktualizuj
        # round_context AŽ TERAZ, po _run_preparation, nie pred ním
        sim_logger.round_context["first_player_index"] = rnd.current_leader_index
        rnd.finish_preparation()
        _run_tricks(game_state, ai_players, sim_logger, shadow_players)

        _round_end_watchers(config, findings, sim_logger, game_state,
                            scores_at_start)

        # Duel: body získané v tomto kole, per systém (musí byť PRED
        # finish_round(), lebo ten round_points resetuje na 0)
        if config.duel_mode:
            v2_seats = _duel_v2_seats(game_index)
            for i, p in enumerate(game_state.players):
                system = "v2" if i in v2_seats else "v1"
                stats.setdefault(f"duel_round_points_{system}", []).append(
                    p.round_points
                )

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

    if config.duel_mode:
        v2_seats = _duel_v2_seats(game_index)
        for i, p in enumerate(game_state.players):
            system = "v2" if i in v2_seats else "v1"
            stats.setdefault(f"duel_final_scores_{system}", []).append(
                p.total_score
            )
            if game_state.loser is not None and game_state.loser.index == i:
                stats[f"duel_loser_{system}"] = (
                    stats.get(f"duel_loser_{system}", 0) + 1
                )


def _run_preparation(game_state: GameState, ai_players: list,
                     shadow_players: list | None = None):
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
            if shadow_players is not None:
                for shadow in shadow_players:
                    shadow.record_illumination(ai.player.index, leaf, acorn)

    # Záväzok — v poradí od first_player, prvý vyhlásený platí
    order = [(rnd.first_player_index + i) % NUM_PLAYERS
             for i in range(NUM_PLAYERS)]
    for idx in order:
        decl = ai_players[idx].decide_declaration()
        if decl:
            rnd.process_declaration(idx, decl)
            for ai in ai_players:
                ai.record_declaration(idx, decl)
            if shadow_players is not None:
                for shadow in shadow_players:
                    shadow.record_declaration(idx, decl)
            break


def _run_tricks(game_state: GameState, ai_players: list,
                sim_logger: SimLogger, shadow_players: list | None = None):
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

            # Decision-divergence watcher: shadow (v1) dostane ZHODNÝ
            # kontext (rovnaká ruka aj história), jeho voľba sa len
            # porovná s tým, čo SKUTOČNE zahral v2 — nehrá sa (v2 je
            # "pravda", určuje priebeh hry).
            if shadow_players is not None:
                shadow = shadow_players[player_idx]
                shadow_card = shadow.decide_card(
                    playable, rnd.current_trick, rnd.trick_number, all_scores
                )
                if shadow_card != card:
                    sim_logger.findings.add({
                        "type": "decision_divergence",
                        **sim_logger.round_context,
                        "trick_number": rnd.trick_number + 1,
                        "player": player.name,
                        "playable": [str(c) for c in playable],
                        "v2_card": str(card),
                        "v1_card": str(shadow_card),
                    })

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
        if shadow_players is not None:
            for shadow in shadow_players:
                shadow.record_trick(played, winner, rnd.trick_number)
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

    # 1b) Kto schytal ktorého horníka (nezávisle od toho, či ho aj vysvietil)
    if config.watch_hornik_capture:
        declaration_active = rnd.declaration_type in ("none", "all")
        if not declaration_active:
            sweep_winner = rnd._check_sweep()
            for suit in ("leaf", "acorn"):
                catcher = None
                for player in game_state.players:
                    if any(c.is_special and c.suit == suit
                           for c in player.penalty_cards):
                        catcher = player
                        break
                if catcher is None:
                    continue
                illum_pidx = rnd.illuminated_by[suit]
                findings.add({
                    "type": "hornik_capture",
                    **sim_logger.round_context,
                    "player": catcher.name,
                    "suit": suit,
                    "illuminated": illum_pidx is not None,
                    "own_illuminated_catch": (
                        illum_pidx is not None
                        and game_state.players[illum_pidx].name == catcher.name
                    ),
                    "was_sweep": sweep_winner is not None,
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
    #    (watch_sweep_success/watch_sweep_failed sú samostatné flagy —
    #    dá sa sledovať len úspešné, len neúspešné, alebo oboje naraz)
    if (config.watch_sweep_success or config.watch_sweep_failed) \
            and sim_logger.sweep_committers:
        sweep_winner_idx = rnd._check_sweep()
        for name in sim_logger.sweep_committers:
            pidx = int(name.split("_")[-1])
            success = (sweep_winner_idx == pidx)
            if success and not config.watch_sweep_success:
                continue
            if not success and not config.watch_sweep_failed:
                continue
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

        if config.duel_mode:
            games_total = stats.get("games_total", 0)
            f.write("\nSÚBOJ v1 vs v2\n" + "-" * 50 + "\n")
            for system in ("v1", "v2"):
                losers = stats.get(f"duel_loser_{system}", 0)
                scores = stats.get(f"duel_final_scores_{system}", [])
                round_pts = stats.get(f"duel_round_points_{system}", [])
                avg_score = sum(scores) / len(scores) if scores else 0.0
                avg_round_pts = (
                    sum(round_pts) / len(round_pts) if round_pts else 0.0
                )
                win_rate = (
                    100.0 * (games_total - losers) / games_total
                    if games_total else 0.0
                )
                f.write(
                    f"{system}: prehry {losers}/{games_total} "
                    f"(výhier {win_rate:.1f}%), "
                    f"priem. finálne skóre {avg_score:.1f}, "
                    f"priem. body/kolo {avg_round_pts:.2f}\n"
                )
        # Okrem surového počtu výskytov aj počet KÔL, kde sa daný nález
        # objavil aspoň raz — jedno kolo môže vyprodukovať viac výskytov
        # toho istého typu (napr. viac fallbackov za kolo), čo vie
        # nafúknuť dojem z počtu výskytov oproti tomu, ako často sa to
        # v hre reálne stane. Kľúč kola = (game_index, round_number),
        # aby sa nezliali kolá z rôznych hier s rovnakým číslom.
        rounds_with_finding: dict[str, set] = {}
        for rec in findings.records:
            key = (rec.get("game_index"), rec.get("round_number"))
            rounds_with_finding.setdefault(rec["type"], set()).add(key)

        f.write("\nNÁLEZY (výskytov spolu | kôl s aspoň 1 výskytom)\n"
                + "-" * 50 + "\n")
        for ftype, count in sorted(findings.counts.items()):
            rounds_affected = len(rounds_with_finding.get(ftype, set()))
            f.write(f"{ftype}: {count} | {rounds_affected}\n")
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
    parser.add_argument("--no-forced-lead-trap-watch", action="store_true")
    parser.add_argument("--no-sweep-success-watch", action="store_true")
    parser.add_argument("--no-sweep-failed-watch", action="store_true")
    parser.add_argument("--no-sweep-90-eval-watch", action="store_true")
    parser.add_argument("--no-hornik-capture-watch", action="store_true")
    parser.add_argument("--no-sweep-ev-audit-watch", action="store_true")
    parser.add_argument("--no-gate2-audit-watch", action="store_true")
    parser.add_argument("--duel", action="store_true",
                        help="súboj v1 vs v2: 2 sedadlá starý systém, "
                             "2 nový, rotujúc naprieč hrami")
    parser.add_argument("--divergence", action="store_true",
                        help="v2 hrá naostro, v1 beží ako shadow "
                             "pozorovateľ — loguje každé rozdielne "
                             "rozhodnutie na tom istom ťahu")
    args = parser.parse_args()

    config = SimConfig(
        num_games=args.games,
        seed=args.seed,
        duel_mode=args.duel,
        divergence_mode=args.divergence,
        watch_illuminated_and_caught=not args.no_illuminated_watch,
        illuminated_exclude_high_score=not args.include_high_score_illuminated,
        watch_none_declaration_failed=not args.no_none_watch,
        watch_global_fallback=not args.no_fallback_watch,
        watch_forced_lead_trap=not args.no_forced_lead_trap_watch,
        watch_sweep_success=not args.no_sweep_success_watch,
        watch_sweep_failed=not args.no_sweep_failed_watch,
        watch_sweep_90_eval=not args.no_sweep_90_eval_watch,
        watch_hornik_capture=not args.no_hornik_capture_watch,
        watch_sweep_ev_audit=not args.no_sweep_ev_audit_watch,
        watch_gate2_audit=not args.no_gate2_audit_watch,
    )
    print(f"Spúšťam simuláciu: {config.num_games} hier (seed={config.seed})")
    run(config)


if __name__ == "__main__":
    main()