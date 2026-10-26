# CHUJ — kartová hra (Python 3.11+, pygame)

4 hráči (1 človek + 3 AI), 32 kariet, hrá sa proti smeru hodinových ručičiek.
Detaily: `00_GAME_RULES.md` (pravidlá), `01_PROJECT_STRUCTURE.md` (štruktúra),
`02_AI_REFERENCE.md` + `AI_V2_HANDOFF.md` (AI pipeline — čítaj LEN pri práci na AI logike).

## Spustenie
```
python main.py                      # hra
python tester_main.py               # tester, posledný seed
python tester_main.py --seed 12345  # reprodukcia konkrétneho rozdania
python tester_main.py --random      # náhodný scenár
python main.py --resolution 1366x768 --windowed   # hra v inom rozlíšení (vývoj)
python main.py --safe               # núdzový štart v okne 1280×720
```
GUI kreslí v logickom priestore 1920×(1080…1200) cez `display.canvas()`;
rozloženie hernej obrazovky je v `gui/layout.py`. Rozlíšenia: doc 11.

## Mapa súborov (game/)
- `card.py`, `deck.py`, `hand.py`, `trick.py` — základné entity
- `player.py` — skóre, záväzky, finalize_round, update_streak
- `round.py` — fázy kola: dealing → preparation → tricks → scoring
- `game_state.py` — hráči, kolá, chujogram
- `ai.py` — vstupný bod AI (decide_card → router → sweep → ai_v2.AIEngine), **jediný AI systém od 2026-09-15**
- `ai_memory.py` — pamäť + SuitProfile (trap/escape/safe karty)
- `ai_hand_eval.py` — HandEval, GameContext, DecisionContext
- `ai_declaration.py` — záväzok "none" + vysvietenie
- `ai_play_none.py`, `ai_play_all.py` — vyhlásené hry
- `ai_v2/engine.py` — AIEngine, vstupný bod card-play enginu
- `ai_v2/context.py` — AIContext, TrickOutcome, card_outcome()
- `ai_v2/selector.py` — StrategySelector — agregácia návrhov, výber karty
- `ai_v2/strategies/*.py` — 11 stratégií (DumpSpecial, DumpHeart, DumpDangerous,
  DumpHigh, AvoidTrick, ForceSpecial, SetupVoid, AcceptTrick, RiskSpecial, Wait,
  LeadSafe), každá `is_active()`/`propose()`/`weight()` — pozri `AI_V2_HANDOFF.md`
- `ai_sweep/pipeline.py` — SweepPipeline L1–L7 (pozri `claude/03_SWEEP_V2_HANDOFF.md`)

`gui/` — GUI (neupravuj pri práci na AI logike). `tester/` — headless tester + pygame screen.

## Rozdelenie zodpovedností (dodržuj striktne)
- `ai_memory.py` — LEN pamäť a inferencia
- `ai_v2/strategies/*.py` — LEN návrh kariet pre svoju situáciu (is_active/propose)
- `ai_v2/selector.py` — LEN agregácia návrhov a výber karty
- `ai.py` — LEN routovanie (easy/sweep/declaration/ai_v2)
- `round.py` — herná logika a fázy; `player.py` — stav hráča, bodovanie

## Konvencie
- Type hints všade (`Card | None`, nie `Union`)
- Dataclasses pre štruktúrované výstupy
- Komentáre: slovenčina. Názvy tried/funkcií/premenných: angličtina
- GUI fonty: vždy `get_font()` z config.py (Unicode ♥ ● ♠ ♣)
- Pri odpovedi posielaj snippety metód, nie celé súbory
- Nespúšťaj hru/tester bez vyžiadania — pygame otvára okno

## Diagnostika AI bugov
AI loguje stratégie vo formáte `[AI meno] VARIANT: detail`
(napr. `[AI Počítač 1] RISK_TRAP: risk trap: Q♣ (P=0.7)`). Variant = label,
ktorý daná stratégia vráti z `propose()` (napr. `UNDERPLAY`, `FORCE`, `VOID`,
`RISK_TRAP`) — pozri `ai_v2/strategies/*.py` a `AI_V2_HANDOFF.md`.
Seed rozdania reprodukuje identické kolo (`python tester_main.py --seed X`).
Logy hry: `Documents/Chuj/logs/`.

## Po zmene AI logiky
Ak zmena mení správanie popísané v `02_AI_REFERENCE.md`, aktualizuj
príslušnú sekciu dokumentu (kompaktne, bez duplikácie).
