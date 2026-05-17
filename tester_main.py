import argparse
from tester.tester_screen import TesterScreen
from tester.random_scenario import random_scenario, save_last_seed, load_last_seed

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
            # Prvé spustenie — generuj random seed
            scenario = random_scenario()
            save_last_seed(int(scenario.name.split("_")[-1]))

    screen = TesterScreen(scenario)
    screen.run()

if __name__ == "__main__":
    main()