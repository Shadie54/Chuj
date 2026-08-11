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