# tester/regression_rules_demo.py
#
# Overí, že príklady v animovanej ukážke pravidiel štichov
# (gui/rules_demo.py) zodpovedajú skutočnej logike hry — farba, povolené
# karty, víťaz štichu, poradie hráčov, prvý štich bez červene.
#
# Použitie:  python tester/regression_rules_demo.py

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("CHUJ_RESOLUTION", "1920x1080")


def main():
    from gui.rules_demo import verify_scenes
    errors = verify_scenes()
    for e in errors:
        print(f"  {e}")
    print("VÝSLEDOK: " + ("ukážka pravidiel zodpovedá logike hry" if not errors
                          else f"{len(errors)} chýb"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
