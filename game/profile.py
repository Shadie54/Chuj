# game/profile.py
#
# Profil hráča a jeho štatistiky.
#
# Kľúčové rozhodnutie: na disk sa ukladajú ZÁZNAMY O HRÁCH, nie hotové
# súčty. Vďaka tomu sa dá kedykoľvek pridať nová štatistika a dopočíta sa
# aj spätne z už odohratých hier. Jeden záznam má ~250 bajtov, takže aj
# tisíc hier je štvrť megabajtu.
#
# Súbor: Documents/Chuj/profile.json (vedľa settings.json, rovnaký vzor
# ako game_setup.py). Formát je od začiatku viacprofilový, aj keď hra
# zatiaľ pracuje len s jedným aktívnym profilom — pridať výber profilu
# neskôr teda nebude znamenať migráciu dát.
#
# Táto vrstva je bez pygame a bez závislosti na hernom stave — dá sa
# testovať headless.

import json
import os
from dataclasses import asdict, dataclass, field, fields

DEFAULT_NAME = "Hráč"

PROFILE_PATH = os.path.join(
    os.path.expanduser("~"), "Documents", "Chuj", "profile.json"
)


@dataclass
class GameRecord:
    """Jedna dohratá hra očami ľudského hráča."""

    # --- kontext ---
    # Obtiažnosti súperov tak, ako boli na konci hry. Ukladajú sa všetky
    # tri, lebo v Nastaveniach sa dajú nastaviť rôzne pre každé AI —
    # difficulty_label() z nich odvodí "hard" / "zmiešané".
    difficulties: list[str] = field(default_factory=list)
    # Hráč smie obtiažnosť prepnúť aj počas rozohratej hry (main.py to
    # aplikuje na bežiace AI), takže samotný zoznam vyššie by inak ticho
    # klamal — tento príznak hovorí, že sa v priebehu hry menila.
    difficulty_changed: bool = False

    # --- výsledok ---
    rounds: int = 0
    final_scores: list[int] = field(default_factory=list)
    my_index: int = 0
    loser_index: int = -1          # kto sa stal Chujom

    # --- priebeh (len ľudský hráč) ---
    clean_rounds: int = 0          # kolá s 0 trestnými bodmi
    worst_round: int = 0           # najviac bodov v jednom kole
    longest_clean_streak: int = 0
    leaf_over_caught: int = 0      # koľkokrát schytal zeleného horníka
    acorn_over_caught: int = 0
    hearts_caught: int = 0
    illuminated: int = 0           # koľkokrát vysvietil (spolu za hru)
    illuminated_caught_own: int = 0  # ...a vysvieteného si sám schytal
    declared_none: int = 0
    declared_none_ok: int = 0
    declared_all: int = 0
    declared_all_ok: int = 0
    sweeps: int = 0
    streak_bonus: int = 0          # koľkokrát padol bonus za 5 čistých kôl
    reset_100: int = 0             # koľkokrát skóre resetlo zo 100 na 90
    bullets: int = 0               # guličky v chujograme na konci hry

    @property
    def my_score(self) -> int:
        if 0 <= self.my_index < len(self.final_scores):
            return self.final_scores[self.my_index]
        return 0

    @property
    def is_loss(self) -> bool:
        """Prehra = hráč sa stal Chujom."""
        return self.loser_index == self.my_index

    @property
    def placement(self) -> int:
        """1 = najnižšie skóre (najlepší). Pri rovnosti delené miesto."""
        if not self.final_scores:
            return 0
        return 1 + sum(1 for s in self.final_scores if s < self.my_score)

    def difficulty_label(self) -> str:
        if not self.difficulties:
            return "?"
        unique = set(self.difficulties)
        return unique.pop() if len(unique) == 1 else "zmiešané"

    @classmethod
    def from_dict(cls, data: dict) -> "GameRecord":
        """Tolerantné načítanie — neznáme kľúče ignoruje, chýbajúce
        doplní predvolenými. Vďaka tomu staršie profily prežijú pridanie
        novej štatistiky."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Stats:
    """Agregované čísla pre obrazovku. Všetko sa počíta zo zoznamu
    GameRecord-ov, nič sa neukladá zvlášť."""
    games: int = 0
    wins: int = 0
    losses: int = 0
    abandoned: int = 0
    win_rate: float = 0.0
    avg_placement: float = 0.0
    avg_score: float = 0.0
    best_game: int | None = None        # najnižšie konečné skóre
    worst_game: int | None = None
    current_streak: int = 0             # hier bez prehry v rade (od konca)
    best_streak: int = 0

    rounds: int = 0
    clean_rounds: int = 0
    clean_rate: float = 0.0
    avg_round_points: float = 0.0
    worst_round: int = 0
    longest_clean_streak: int = 0

    leaf_over_caught: int = 0
    acorn_over_caught: int = 0
    hearts_caught: int = 0
    avg_hearts_per_round: float = 0.0
    illuminated: int = 0
    illuminated_caught_own: int = 0
    illumination_success: float = 0.0   # % vysvietení, kde si horníka NEschytal

    declared_none: int = 0
    declared_none_ok: int = 0
    declared_none_rate: float = 0.0
    declared_all: int = 0
    declared_all_ok: int = 0
    declared_all_rate: float = 0.0
    sweeps: int = 0
    streak_bonus: int = 0
    reset_100: int = 0
    bullets: int = 0


@dataclass
class Profile:
    name: str = DEFAULT_NAME
    games: list[GameRecord] = field(default_factory=list)
    # Nedohraté hry (odchod do menu) sa evidujú len ako počítadlo a do
    # bilancie sa nerátajú — inak by sa dalo pred istou prehrou odísť a
    # držať si čistý štít.
    abandoned: int = 0

    def add_game(self, record: GameRecord):
        self.games.append(record)

    def add_abandoned(self):
        self.abandoned += 1

    def stats(self) -> Stats:
        return compute_stats(self.games, self.abandoned)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "abandoned": self.abandoned,
            "games": [asdict(g) for g in self.games],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return cls(
            name=data.get("name", DEFAULT_NAME),
            abandoned=int(data.get("abandoned", 0)),
            games=[GameRecord.from_dict(g) for g in data.get("games", [])],
        )


def compute_stats(games: list[GameRecord], abandoned: int = 0) -> Stats:
    """Spočíta všetky štatistiky zo zoznamu hier."""
    s = Stats(games=len(games), abandoned=abandoned)
    if not games:
        return s

    s.losses = sum(1 for g in games if g.is_loss)
    s.wins = s.games - s.losses
    s.win_rate = s.wins / s.games * 100
    s.avg_placement = sum(g.placement for g in games) / s.games
    s.avg_score = sum(g.my_score for g in games) / s.games
    s.best_game = min(g.my_score for g in games)
    s.worst_game = max(g.my_score for g in games)

    # Séria hier bez prehry: aktuálna sa počíta od konca zoznamu.
    streak = best = 0
    for g in games:
        if g.is_loss:
            streak = 0
        else:
            streak += 1
            best = max(best, streak)
    s.current_streak, s.best_streak = streak, best

    s.rounds = sum(g.rounds for g in games)
    s.clean_rounds = sum(g.clean_rounds for g in games)
    s.clean_rate = (s.clean_rounds / s.rounds * 100) if s.rounds else 0.0
    s.worst_round = max(g.worst_round for g in games)
    s.longest_clean_streak = max(g.longest_clean_streak for g in games)

    s.leaf_over_caught = sum(g.leaf_over_caught for g in games)
    s.acorn_over_caught = sum(g.acorn_over_caught for g in games)
    s.hearts_caught = sum(g.hearts_caught for g in games)
    s.avg_hearts_per_round = (s.hearts_caught / s.rounds) if s.rounds else 0.0

    s.illuminated = sum(g.illuminated for g in games)
    s.illuminated_caught_own = sum(g.illuminated_caught_own for g in games)
    if s.illuminated:
        s.illumination_success = (
            (s.illuminated - s.illuminated_caught_own) / s.illuminated * 100
        )

    s.declared_none = sum(g.declared_none for g in games)
    s.declared_none_ok = sum(g.declared_none_ok for g in games)
    if s.declared_none:
        s.declared_none_rate = s.declared_none_ok / s.declared_none * 100
    s.declared_all = sum(g.declared_all for g in games)
    s.declared_all_ok = sum(g.declared_all_ok for g in games)
    if s.declared_all:
        s.declared_all_rate = s.declared_all_ok / s.declared_all * 100

    s.sweeps = sum(g.sweeps for g in games)
    s.streak_bonus = sum(g.streak_bonus for g in games)
    s.reset_100 = sum(g.reset_100 for g in games)
    s.bullets = sum(g.bullets for g in games)

    # Priemer trestných bodov na kolo — z konečných skóre sa to spočítať
    # nedá (bonusy a záväzky ho skresľujú), preto berieme súčet skóre
    # delený počtom kôl ako hrubý odhad "koľko ma stojí jedno kolo".
    total_points = sum(g.my_score for g in games)
    s.avg_round_points = (total_points / s.rounds) if s.rounds else 0.0
    return s


# ----------------------------------------------------------------------
# Načítanie / uloženie
# ----------------------------------------------------------------------

def load_profiles() -> tuple[dict[str, Profile], str]:
    """Vráti (profily, meno_aktívneho). Pri chýbajúcom alebo poškodenom
    súbore vráti čerstvý predvolený profil — štatistiky nikdy nesmú
    zhodiť hru."""
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("profiles", {})
        profiles = {name: Profile.from_dict(p) for name, p in raw.items()}
        active = data.get("active", DEFAULT_NAME)
        if not profiles:
            profiles = {DEFAULT_NAME: Profile()}
            active = DEFAULT_NAME
        if active not in profiles:
            active = next(iter(profiles))
        return profiles, active
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError,
            ValueError, AttributeError):
        return {DEFAULT_NAME: Profile()}, DEFAULT_NAME


def save_profiles(profiles: dict[str, Profile], active: str) -> bool:
    """Uloží profily. Vracia True pri úspechu — zlyhanie zápisu (plný
    disk, práva) nesmie zhodiť hru, len sa štatistika nezapíše."""
    try:
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        payload = {
            "version": 1,
            "active": active,
            "profiles": {n: p.to_dict() for n, p in profiles.items()},
        }
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def load_active_profile() -> Profile:
    profiles, active = load_profiles()
    return profiles[active]


def record_abandoned() -> bool:
    """Pripíše aktívnemu profilu jednu nedohratú hru. Volá sa až vtedy,
    keď hráč rozohratú hru naozaj zahodí (začne novú) — samotný odchod
    do menu sa dá vrátiť cez "Pokračovať", takže ešte nič nevzdáva."""
    try:
        profile = load_active_profile()
        profile.add_abandoned()
        return save_active_profile(profile)
    except Exception:
        return False


def save_active_profile(profile: Profile) -> bool:
    """Uloží zmeny v aktívnom profile a nechá ostatné nedotknuté."""
    profiles, active = load_profiles()
    old_name = active
    profiles[profile.name] = profile
    if profile.name != old_name and old_name in profiles:
        # Premenovanie profilu — starý kľúč zahodíme, nech nevzniknú
        # dva záznamy o tom istom hráčovi.
        del profiles[old_name]
    return save_profiles(profiles, profile.name)
