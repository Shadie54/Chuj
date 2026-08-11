# tester/findings_playlist.py
"""
Playlist nálezov zo sim_findings.jsonl pre prehrávanie v testeri.

Použitie:
    python tester_main.py --findings
"""

import json
import os
from tester.random_scenario import random_scenario
from tester.scenario import Scenario
from config import HIGH_SCORE_THRESHOLD

FINDINGS_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "sim_output",
    "sim_findings.jsonl"
)


def load_findings(path: str = FINDINGS_PATH) -> list[dict]:
    findings = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                findings.append(json.loads(line))
    return findings


class FindingsPlaylist:
    def __init__(self, findings: list[dict], start_index: int = 0):
        self.findings = findings
        self.index = max(0, min(start_index, len(findings) - 1))

    @property
    def current(self) -> dict:
        return self.findings[self.index]

    @property
    def label(self) -> str:
        f = self.current
        return (f"Nález {self.index + 1}/{len(self.findings)} | "
                f"{f['type']} | {f.get('player', '?')} | "
                f"kolo {f.get('round_number', '?')} "
                f"štich {f.get('trick_number', '?')}")

    def next(self) -> dict:
        self.index = (self.index + 1) % len(self.findings)
        return self.current

    def prev(self) -> dict:
        self.index = (self.index - 1) % len(self.findings)
        return self.current


def build_scenario(finding: dict) -> Scenario:
    """
    Scenár z finding záznamu:
    - deal_seed → identické rozdanie kariet
    - first_player_index z dát (prepíše náhodne vylosovaný)
    - scores → 90+ binárne (rovnaký mechanizmus ako tlačidlo 90+ v testeri)
    """
    scenario = random_scenario(seed=finding["deal_seed"])
    scenario.first_player_index = finding["first_player_index"]

    raw_scores = finding.get("scores_at_round_start", [0, 0, 0, 0])
    scenario.scores = {
        i: (90 if s >= HIGH_SCORE_THRESHOLD else 0)
        for i, s in enumerate(raw_scores)
    }
    return scenario
