# CHUJ — kartová hra (Python 3.11+, pygame)

4 hráči (1 človek + 3 AI), 32 kariet, hrá sa proti smeru hodinových ručičiek.
Detaily: `docs/00_GAME_RULES.md` (pravidlá), `docs/01_PROJECT_STRUCTURE.md` (štruktúra),
`docs/02_AI_REFERENCE.md` (AI pipeline — čítaj LEN pri práci na AI logike).

## Spustenie
```
python main.py                      # hra
python tester_main.py               # tester, posledný seed
python tester_main.py --seed 12345  # reprodukcia konkrétneho rozdania
python tester_main.py --random      # náhodný scenár
```

## Mapa súborov (game/)
- `card.py`, `deck.py`, `hand.py`, `trick.py` — základné entity
- `player.py` — skóre, záväzky, finalize_round, update_streak
- `round.py` — fázy kola: dealing → preparation → tricks → scoring
- `game_state.py` — hráči, kolá, chujogram
- `ai.py` — vstupný bod AI (decide_card → router → sweep → situation → selector)
- `ai_memory.py` — pamäť + SuitProfile (trap/escape/safe karty)
- `ai_hand_eval.py` — HandEval, GameContext, DecisionContext
- `ai_situation.py` — SituationDetector (L-*/F-* situácie)
- `ai_card_select.py` — CardSelector (SAFE/TAKE/OPEN/RISK mode)
- `ai_sweep.py` — SweepPipeline L1–L7
- `ai_declaration.py` — záväzok "none" + vysvietenie
- `ai_play_none.py`, `ai_play_all.py` — vyhlásené hry
- `ai_strategies_const.py` — Situation/Mode/Strategy konštanty

`gui/` — GUI (neupravuj pri práci na AI logike). `tester/` — headless tester + pygame screen.

## Rozdelenie zodpovedností (dodržuj striktne)
- `ai_memory.py` — LEN pamäť a inferencia
- `ai_situation.py` — LEN detekcia situácie
- `ai_card_select.py` — LEN selekcia karty
- `ai.py` — LEN rozhodovacia logika
- `round.py` — herná logika a fázy; `player.py` — stav hráča, bodovanie

## Konvencie
- Type hints všade (`Card | None`, nie `Union`)
- Dataclasses pre štruktúrované výstupy
- Komentáre: slovenčina. Názvy tried/funkcií/premenných: angličtina
- GUI fonty: vždy `get_font()` z config.py (Unicode ♥ ● ♠ ♣)
- Pri odpovedi posielaj snippety metód, nie celé súbory
- Nespúšťaj hru/tester bez vyžiadania — pygame otvára okno

## Diagnostika AI bugov
AI loguje stratégie vo formáte `[AI meno] SITUÁCIA | MODE | STRATÉGIA: detail`
(napr. `L-SAFE | SAFE | L1-SAFE_LEAD: escape bell: 9●`).
Kódy stratégií: `ai_strategies_const.py`. Seed rozdania reprodukuje identické kolo.
Logy hry: `Documents/Chuj/logs/`.

## Po zmene AI logiky
Ak zmena mení správanie popísané v `docs/02_AI_REFERENCE.md`, aktualizuj
príslušnú sekciu dokumentu (kompaktne, bez duplikácie).
