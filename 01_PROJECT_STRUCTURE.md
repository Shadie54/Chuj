# Štruktúra projektu CHUJ

## Umiestnenie
C:\Chuj\

## Spustenie
python main.py                          ← spustí hru
python tester_main.py                   ← spustí tester (default scenár)
python tester_main.py --random          ← random scenár (časový seed)
python tester_main.py --seed 12345      ← random scenár s konkrétnym seedom

## Adresárová štruktúra
C:\Chuj
├── assets/
│   ├── cards-large/       ← 363×585 px
│   ├── cards-medium/      ← 181×293 px
│   ├── cards-small/       ← 91×146 px
│   │   Formát: {suit}-{rank}.png  napr. heart-ace.png, leaf-over.png
│   │   Suits: heart, bell, leaf, acorn
│   │   Ranks: ace, king, over, under, ten, nine, eight, seven
│   ├── graphics/
│   │   ├── table.jpg
│   │   └── 1000.ico
│   └── suit-icons/
│       Formát: {suit}-icon@{size}.png  (small=41×50 / medium=81×99 / large=162×200)
│
├── game/
│   ├── card.py            ← Card class (suit, rank, rank_order, is_special, points)
│   ├── deck.py            ← Deck class (shuffle so seedom, deal 4+4)
│   ├── hand.py            ← Hand class (karty, get_playable_cards, sort)
│   ├── player.py          ← Player class (skóre, záväzky, finalize_round)
│   ├── trick.py           ← Trick class (zahrané karty, get_winner_index)
│   ├── round.py           ← Round class (fázy: dealing→preparation→tricks→scoring)
│   ├── game_state.py      ← GameState class (hráči, kolá, chujogram, game_over)
│   ├── game_logger.py     ← GameLogger (logovanie do súboru + log_strategy pre AI)
│   ├── ai.py              ← AI class (decide_card, decide_declaration, decide_illumination)
│   ├── ai_memory.py       ← AIMemory + SuitProfile (pamäť, tracking, inferencia)
│   ├── ai_hand_eval.py    ← HandEval dataclass + evaluate_hand()
│   ├── ai_situation.py    ← SituationDetector (LEADER/FOLLOWER situácie)
│   ├── ai_card_select.py  ← CardSelector (SAFE/TAKE/OPEN mód logika)
│   ├── ai_sweep.py        ← SweepPipeline (L1-L7)
│   ├── ai_declaration.py  ← DeclarationAdvisor (záväzky a vysvietenie)
│   └── ai_strategies_const.py ← konštanty: Situation, Mode, Strategy
│
├── gui/
│   ├── screen.py          ← hlavná herná obrazovka, event loop, fázy hry
│   ├── card_renderer.py   ← kreslenie kariet
│   ├── deal_animation.py  ← animácia rozdávania
│   ├── trick_animation.py ← animácia letu kariet k víťazovi
│   ├── chujogram_panel.py ← panel s históriou skóre
│   ├── round_status.py    ← panel vpravo dole (kolo, seed, body, záväzok)
│   ├── info_overlay.py    ← overlay s pravidlami a bodovaním (2 záložky)
│   ├── speech_bubble.py   ← bubliny nad hráčmi
│   ├── menu.py            ← hlavné menu
│   ├── game_over_screen.py ← obrazovka konca hry
│   ├── settings_screen.py ← nastavenia (obtiažnosť AI per hráč)
│   ├── scoreboard.py      ← tabuľka skóre
│   ├── phase_renderer.py  ← kreslenie overlayov, tlačidiel, správ, menoviek
│   └── preparation_handler.py ← logika prípravnej fázy (záväzky, vysvietenie, AI príprava)
│
└── tester/
├── scenarios/
│   └── easy_sweep.py  ← hardcoded scenár
├── scenario.py        ← Scenario dataclass + DSL + validácia
├── tester_engine.py   ← bezhlavá logika (load scenario, next_step, snapshot/back)
├── tester_logger.py   ← TesterLogger (reasoning chain per ťah)
├── tester_screen.py   ← pygame GUI (1600×980, biele pozadie)
└── random_scenario.py ← generátor náhodných scenárov so seedom

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
SWEEP_BONUS = -10
DECLARATION_ALL_BONUS = -20
DECLARATION_ALL_PENALTY = 20
DECLARATION_NONE_BONUS = -10
DECLARATION_FAIL_PENALTY = 10
NO_PENALTY_STREAK = 5
NO_PENALTY_BONUS = -10
```

## GUI rozlíšenie
- Hra: štandardné rozlíšenie (prispôsobené obrazovke)
- Tester: 1600×980, biele pozadie
- DPI awareness: nastavená pre Windows scaling

## Seed systém
- Každé kolo má vlastný seed rozdania
- Seed sa zobrazuje v round_status paneli: "KOLO 3 (487123)"
- Seed sa loguje do `Documents/Chuj/logs/current_game.txt`
- Tester: `python tester_main.py --seed 487123` reprodukuje identické rozdanie

## Logy
- `Documents/Chuj/logs/current_game.txt` — priebežný log
- `Documents/Chuj/logs/game_YYYYMMDD_HHMMSS.txt` — finálny log
- `DEBUG_MODE = False` v config.py — ak True, karty AI sú viditeľné

## Tester — funkcie
- **Next** (Space/→): odohrá ďalší ťah AI
- **Back** (←): vráti sa o ťah späť
- **Override** (O): zahrá kartu manuálne
- **Štich** (T): autoplay celého štichu
- **Kolo**: autoplay celého kola
- **Random** (G): nový náhodný scenár
- **Export** (E): uloží stav do `tester_export.txt`
- **Reset** (R): reštart aktuálneho scenára
- **Setup bar**: override first playera a vysvietenia (klik na tlačidlá)