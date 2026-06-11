# Štruktúra projektu CHUJ

## Umiestnenie a spustenie
```
C:\Chuj\
python main.py                          ← spustí hru
python tester_main.py                   ← načíta posledný seed
python tester_main.py --random          ← random scenár (časový seed)
python tester_main.py --seed 12345      ← konkrétny seed
```

## Adresárová štruktúra
```
C:\Chuj
├── assets/
│   ├── cards-large/   (363×585 px)
│   ├── cards-medium/  (181×293 px)
│   ├── cards-small/   (91×146 px)
│   │   Formát: {suit}-{rank}.png  napr. heart-ace.png, leaf-over.png
│   ├── graphics/      table.jpg, 1000.ico
│   └── suit-icons/    {suit}-icon@{size}.png
│
├── game/
│   ├── card.py            Card class (suit, rank, rank_order, is_special, points)
│   ├── deck.py            Deck class (shuffle so seedom, deal 4+4)
│   ├── hand.py            Hand class (get_playable_cards, sort)
│   ├── player.py          Player class (skóre, záväzky, finalize_round, update_streak)
│   ├── trick.py           Trick class (played_cards, get_winner_index, total_base_points)
│   ├── round.py           Round class (fázy: dealing→preparation→tricks→scoring)
│   ├── game_state.py      GameState class (hráči, kolá, chujogram, logger)
│   ├── game_logger.py     GameLogger (logovanie do súboru)
│   ├── ai.py              AI class — hlavný vstupný bod (decide_card, decide_declaration, decide_illumination)
│   ├── ai_memory.py       AIMemory + SuitProfile
│   ├── ai_hand_eval.py    HandEval, GameContext, DecisionContext, HandEvaluator
│   ├── ai_situation.py    SituationDetector
│   ├── ai_card_select.py  CardSelector
│   ├── ai_sweep.py        SweepPipeline (L1-L7)
│   ├── ai_declaration.py  DeclarationAdvisor
│   ├── ai_play_none.py    NonePlayer
│   ├── ai_play_all.py     AllPlayer
│   └── ai_strategies_const.py  Situation, Mode, Strategy konštanty
│
├── gui/                   (GUI — nie je predmetom tohto chatu)
│
└── tester/
    ├── scenarios/easy_sweep.py
    ├── scenario.py        Scenario dataclass + DSL (C(), hand(), trick())
    ├── tester_engine.py   bezhlavá logika (load, next_step, snapshot/back)
    ├── tester_logger.py   TesterLogger (LogEntry, capture API)
    ├── tester_screen.py   pygame GUI 1600×980
    └── random_scenario.py generátor náhodných scenárov
```

## Kľúčové konštanty (config.py)
```python
NUM_PLAYERS = 4
CARDS_PER_PLAYER = 8
TRICKS_PER_ROUND = 8
WINNING_SCORE = 100
RESET_SCORE = 90
HIGH_SCORE_THRESHOLD = 90
SUITS = ["heart", "bell", "leaf", "acorn"]
RANKS = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]
SHOOT_MOON_BONUS = -10
DECLARATION_ALL_BONUS = -20
DECLARATION_ALL_PENALTY = 20
DECLARATION_NONE_BONUS = -10
DECLARATION_FAIL_PENALTY = 10
NO_PENALTY_STREAK = 5
NO_PENALTY_BONUS = -10
LEAF_OVER = ("leaf", "over")
ACORN_OVER = ("acorn", "over")
```

## Seed systém
- `Deck.deal()` vracia `(hands, seed)` — ukladá sa do `Round.deal_seed`
- Seed je per-kolo (nie per-hra), viditeľný v round_status paneli
- `random.Random(seed)` — lokálny RNG, nie globálny
- `python tester_main.py --seed 487123` reprodukuje identické rozdanie
- Posledný seed sa ukladá do `Documents/Chuj/last_seed.txt`

## Logy
- `Documents/Chuj/logs/current_game.txt` — priebežný log
- `Documents/Chuj/logs/game_YYYYMMDD_HHMMSS.txt` — finálny log
- `DEBUG_MODE = False` v config.py — ak True, karty AI sú viditeľné

## Tester — ovládanie
- **Space/→ (Next)**: odohrá ďalší ťah AI
- **← (Back)**: vráti sa o ťah späť
- **O (Override)**: zahrá kartu manuálne
- **T (Štich)**: autoplay celého štichu
- **Kolo**: autoplay celého kola
- **G (Random)**: nový náhodný scenár
- **E (Export)**: uloží stav do `tester_export.txt`
- **R (Reset)**: reštart aktuálneho scenára
- **Setup bar**: override first_player a vysvietenia

## Konvencie kódu
- Python 3.11+, type hints všade (`Card | None` nie `Union`)
- Dataclasses pre štruktúrované výstupy
- Komentáre v kóde: slovenčina. Názvy tried/funkcií/premenných: angličtina
- Fonty: vždy `get_font()` z config.py (Unicode podpora ♥ ● ♠ ♣)
- Snippety metód, nikdy celý súbor

## Rozdelenie zodpovedností
- `ai_memory.py` — LEN pamäť a inferencia
- `ai_situation.py` — LEN detekcia situácie
- `ai_card_select.py` — LEN selekcia karty
- `ai.py` — LEN rozhodovacia logika
- `round.py` — herná logika a fázy
- `player.py` — stav hráča, bodovanie
