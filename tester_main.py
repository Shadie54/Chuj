import argparse
import os
from pathlib import Path
from tester.tester_screen import TesterScreen
from tester.scenarios.easy_sweep import scenario as default_scenario
from tester.random_scenario import random_scenario

LAST_SEED_FILE = Path.home() / "Documents" / "Chuj" / "last_seed.txt"

def save_last_seed(seed: int):
    LAST_SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEED_FILE.write_text(str(seed))

def load_last_seed() -> int | None:
    try:
        return int(LAST_SEED_FILE.read_text().strip())
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Chuj tester")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--random", action="store_true")
    args = parser.parse_args()

    if args.seed is not None:
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
            scenario = default_scenario

    screen = TesterScreen(scenario)
    screen.run()

if __name__ == "__main__":
    main()