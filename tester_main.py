# tester_main.py
"""
Entry point pre Chuj tester.

Spustenie z koreňa projektu:
    python tester_main.py                       # hardcoded scenár
    python tester_main.py --seed 847362         # random scenár s daným seedom
    python tester_main.py --random              # random scenár s časovým seedom

Bez argumentov sa použije hardcoded easy_sweep scenár.
"""

import argparse
from tester.tester_screen import TesterScreen
from tester.scenarios.easy_sweep import scenario as default_scenario
from tester.random_scenario import random_scenario


def main():
    parser = argparse.ArgumentParser(description="Chuj tester")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed pre random scenár (reprodukovateľný)",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Spustí random scenár (s časovým seedom ak --seed nie je daný)",
    )
    args = parser.parse_args()

    if args.seed is not None:
        scenario = random_scenario(seed=args.seed)
    elif args.random:
        scenario = random_scenario()
    else:
        scenario = default_scenario

    screen = TesterScreen(scenario)
    screen.run()


if __name__ == "__main__":
    main()