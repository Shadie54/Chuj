# PYTHONHASHSEED musí byť nastavený PRED štartom interpretera (nedá sa
# zmeniť za behu) — rovnaký guard ako v tester_main.py / tester/simulator.py
# (pozri komentár tam pre plné odôvodnenie). Bez neho by simulácia spustená
# cez toto GUI nebola so --seed reprodukovateľná.
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

from tester.sim_screen import SimScreen


def main():
    screen = SimScreen()
    screen.run()


if __name__ == "__main__":
    main()
