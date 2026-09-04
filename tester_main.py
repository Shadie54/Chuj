# PYTHONHASHSEED musí byť nastavený PRED štartom interpretera (nedá sa
# zmeniť za behu) — inak Python defaultne randomizuje poradie iterácie
# cez set/dict s reťazcovými kľúčmi (napr. AIMemory.void_suits: dict[int,
# set[str]]) pri každom spustení procesu. Ak niečo v AI rozhodovaní také
# poradie číta, --seed X potom nereprodukuje vždy tú istú hru — nájdené
# 2026-09-04 pri overovaní regresného testu (dva behy s tým istým
# --seed 777 dávali rôzne výsledky, aj keď samotné rozdanie bolo už
# opravené na deterministické — pozri game/round.py). Tento guard sa
# reštartuje raz s fixovaným PYTHONHASHSEED=0, ak ešte nebol nastavený.
#
# Reštart ide cez subprocess.run (nie os.execv) a berie argumenty z
# sys.argv (logické argumenty skriptu), nie zo sys.orig_argv (surový
# príkazový riadok interpretera). Dôvod: pri spustení cez IDE (napr.
# PyCharm run/debug) sys.orig_argv obsahuje IDE/debug launcher, nie
# tento skript priamo — jeho opätovné spustenie cez os.execv potichu
# zlyhá bez pripojeného debug serveru a proces skončí s "exit code 0"
# bez akéhokoľvek výstupu. Nájdené 2026-09-04 pri prvom nasadení
# pôvodného os.execv guardu.
import os
import sys
if __name__ == "__main__" and os.environ.get("PYTHONHASHSEED") != "0":
    import subprocess
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)] + sys.argv[1:],
        env=env,
    )
    sys.exit(result.returncode)

import argparse
from tester.tester_screen import TesterScreen
from tester.random_scenario import random_scenario, save_last_seed, load_last_seed
from tester.findings_playlist import load_findings, FindingsPlaylist, build_scenario


def main():
    parser = argparse.ArgumentParser(description="Chuj tester")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--findings", action="store_true",
                        help="prehrávanie nálezov zo sim_findings.jsonl")
    parser.add_argument("--finding-index", type=int, default=0)
    args = parser.parse_args()

    playlist = None
    if args.findings:
        findings = load_findings()
        if not findings:
            print("sim_findings.jsonl je prázdny alebo neexistuje.")
            return
        playlist = FindingsPlaylist(findings, start_index=args.finding_index)
        scenario = build_scenario(playlist.current)
    elif args.seed is not None:
        scenario = random_scenario(seed=args.seed)
        save_last_seed(args.seed)
    elif args.random:
        scenario = random_scenario()
        save_last_seed(int(scenario.name.split("_")[-1]))
    else:
        last_seed = load_last_seed()
        if last_seed is not None:
            scenario = random_scenario(seed=last_seed)
        else:
            scenario = random_scenario()
            save_last_seed(int(scenario.name.split("_")[-1]))

    screen = TesterScreen(scenario, findings_playlist=playlist)
    screen.run()


if __name__ == "__main__":
    main()