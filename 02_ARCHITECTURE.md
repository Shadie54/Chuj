# AI architektúra — CHUJ

## Filozofia

AI rozhoduje cez **dvojúrovňový pipeline**. Každý ťah prechádza paralelne:

1. **Sweep pipeline** — vyhodnotí či má hráč šancu chytiť všetky trestné karty
2. **Default pipeline** — bežné rozhodovanie

Sweep pipeline má prednosť: ak vráti `YES`, jeho karta sa hrá. Inak rozhoduje default pipeline.

## Hlavný vstupný bod — `AI.decide_card()` (`game/ai.py`)

```python
def decide_card(self, playable, current_trick, trick_number,
                all_scores: list[int] | None = None) -> Card:
    if self.difficulty == "easy":
        return random.choice(playable)

    hand_eval = self.evaluator.evaluate(...)
    ctx = GameContext.build(self.player.index, all_scores, my_declaration)

    sweep_result = self.sweep_pipeline.evaluate(hand_eval, trick_number)
    if sweep_result.decision == YES:
        if sweep_result.recommended_card in playable:
            return sweep_result.recommended_card

    situation = self.situator.determine(hand_eval, playable, current_trick, ctx)
    mode = self.situator.to_mode(situation, current_trick)
    card = self.selector.select(mode, situation, hand_eval, playable, current_trick, ctx)
    return card
```

## Memory model — `AIMemory` (`game/ai_memory.py`)

Každý AI má vlastnú `AIMemory` inštanciu. Drží:

- `played_cards` — set všetkých zahraných kariet od začiatku kola
- `remaining[suit]` — karty ktoré ešte sú u súperov
- `void_suits[player_idx]` — farby kde hráč preukázal void
- `special_possible_holders[suit]` — hráči ktorí môžu mať horníka
- `special_gone[suit]` — či horník padol
- `illuminated_by[suit]` — kto vysvietil horníka
- `tricks_taken[player_idx]` — počet vyhraných štichov
- `discards[player_idx]` — karty zahodené cez void

### `SuitProfile` — situačný snapshot farby

`memory.build_suit_profile(suit, my_hand, current_trick_cards)` vracia:

| Pole | Popis |
|------|-------|
| `count` | počet mojich kariet farby |
| `is_void` | či som void |
| `my_cards` | moje karty farby |
| `trap_cards` | nikto vyšší vonku → zoberiem štich |
| `escape_cards` | niekto vyšší vonku → môžem podliezť (nie garantované) |
| `safe_cards` | všetci vonku sú vyšší → garantovane nevyhrám štich |
| `coverage` | vyššie karty vonku (remaining + trick karty) |
| `has_special` | mám horníka tejto farby |
| `special_reserves` | počet kariet okrem horníka |

## Default pipeline

### 1. HAND_EVAL (`ai_hand_eval.py`)

Vstup: ruka, počet zostávajúcich štichov, karty v aktuálnom štichu.
Výstup: `HandEval` dataclass — per-suit profiles, trap/escape/safe karty, agregáty.

### `GameContext` — herný kontext pre AI rozhodovanie

`GameContext.build(my_index, all_scores, my_declaration)` vracia:

| Pole | Popis |
|------|-------|
| `my_score` | moje celkové skóre |
| `all_scores` | skóre všetkých hráčov |
| `is_high_score` | my_score >= 90 |
| `score_rank` | 1=vediem, 4=posledný |
| `gap_to_leader` | rozdiel od lídra (0 ak vediem) |
| `gap_to_last` | rozdiel od posledného (0 ak som posledný) |
| `my_declaration` | môj aktívny záväzok ("all"/"none"/None) |

### 2. SITUATION (`ai_situation.py`)

**Leader situácie:**

| Situácia | Trigger | Mode |
|----------|---------|------|
| `LEADER_AGGRESSIVE` | súper má horníka, mám non-A/K v jeho farbe | TAKE |
| `LEADER_HIGH_SCORE` | 90+, mám prebytočné nízke červene | SAFE |
| `LEADER_SAFE` | mám non-heart escape (non-special) | SAFE |
| `LEADER_RISK` | horník + A/K bez escape, vonku vyššia karta | OPEN |
| `LEADER_FORCED` | nemám escape | OPEN |

**Follower situácie:**

| Situácia | Trigger | Mode |
|----------|---------|------|
| `FOLLOWER_VOID` | nemám lead suit | OPEN |
| `FOLLOWER_FREE_TAKE` | vysvietený horník u skoršieho hráča zahral nehorníka + mám A/K, horník živý | TAKE |
| `FOLLOWER_SAFE` | viem podliezť | SAFE |
| `FOLLOWER_CONTROLLED` | posledný + čistý štich + nemôžem podliezť | TAKE |
| `FOLLOWER_WAIT` | niekto po mne môže biť, nie som i_will_likely_win | OPEN |
| `FOLLOWER_FORCED` | nemôžem podliezť, som i_will_likely_win alebo penalty štich | TAKE |

### 3. CARD (`ai_card_select.py`)

**SAFE mode:**
- Leader `LEADER_HIGH_SCORE`: nízka prebytočná červeň → `L4-HIGH_SCORE_LEAD`
- Leader štandard: najnižšia non-heart escape (mimo protected suits) → `L1-SAFE_LEAD`
  - `_protected_suits()` — chráni farbu kde som svietil horníka a mám málo rezerv
- Follower: horník má prioritu ak je v underplay → inak najvyššia podliezka → `F1-UNDERPLAY`

**TAKE mode:**
- `LEADER_AGGRESSIVE`: najnižšia non-A/K v cudzej horník-farbe → `L2-FORCE_SPECIAL`
- `FOLLOWER_CONTROLLED`: dump horník → dump trap A/K → najvyššia lead → `F3-LAST_TAKE`
- `FOLLOWER_FREE_TAKE`: dump A/K v lead suit → `F4-DUMP_FREE`
- Follower štandard: najnižšia lead (nie posledný) / najvyššia lead (posledný) → `F2-FORCED_TAKE`

**OPEN mode:**
- `FOLLOWER_VOID` → `_void_discard()`:
  - 90+ → `_void_discard_high_score()`: trap červeň → horník → non-safe červeň → štandard
  - "none" záväzok → `_void_discard_none()`: najvyššia non-special
  - štandard → `_void_discard_standard()`: horník → trap A/K živý horník → hearts → trap → fallback
- `LEADER_RISK` → `_risk_play()`: horník namiesto A/K → `L5-RISK_SPECIAL`
- `LEADER_FORCED` / `FOLLOWER_WAIT` → `_open_play()`:
  - Leader: void setup → escape → exhaust → risk play check
  - Follower: dump horník/trap → dump high → wait najnižšia → `F8-DUMP_DANGEROUS` / `F5-WAIT`

## Sweep pipeline — `ai_sweep.py`

### Stavy
- `IDLE` — nepokúšam sa o sweep
- `WATCHING` — situácia sľubná, sledujem
- `COMMITTED_SAFE` — committed s escape
- `COMMITTED_FULL` — matematicky garantovaný sweep

### Vrstvy L1–L7
| Vrstva | Názov | Úloha |
|--------|-------|-------|
| L1 | Hard Gates | lacné deterministické filtre |
| L2 | Hand Evaluation | adaptívne hodnotenie sily ruky |
| L3 | Suit Control | per-suit timeline + kritické udalosti |
| L4 | Opponent Modeling | pravdepodobnosti umiestnenia kariet |
| L5 | Targeted Simulation | kandidátne karty + P(sweep) |
| L6 | Escape Evaluation | escape route + EV výpočet |
| L7 | Decision | finálne rozhodnutie |

## Declaration pipeline — `ai_declaration.py`

### `decide_declaration()`
- `"none"` — skórovací systém rizika:
  - Veto: horník, osamelý J/Q/K/A bez bufferov, A/K/Q bez ≥2 nízkych
  - Riziko: 10 osamelá=+4, 10 s 1 nízkou=+1, J s 1 nízkou=+2, Q/K/A s 2+ nízkymi=+1
  - Kompenzácia: void farba=-4
  - Threshold: ≤0 vždy, 1-4 hard, >4 nikdy
- `"all"` — TODO: nie je implementované
- `None` — žiadny záväzok
- Ochrana: len jeden záväzok per kolo (podľa poradia od first_player)

### `decide_illumination(first_player_index, all_scores=None)`
- Hodnotí rezervu horníka (počet podporných kariet + kvalita)
- Hodnotí riziko červených: každý nekrytý vysoký červeň = +4b očakávaná penalizácia
- Hodnotí kompenzáciu: void farby (+1 každá), posledný hráč (+1)
- **90+ veto** — ak `my_score >= 90`:
  - `high_score_unprotected_hearts` — vysoký červeň bez buffera
  - `high_score_naked_high` — nahý vysoký bell bez buffera
- **is_leader veto** — ak vediem skóre a rezerva = borderline → nevysvietim

## 90+ logika

Pri `my_score >= 90` sa mení správanie:
- **Vysvietenie**: veto ak nekryté vysoké červene
- **Leader**: `LEADER_HIGH_SCORE` — veď nízkou prebytočnou červeňou
- **Void discard**: `_void_discard_high_score()` — priorita trap červeňov, near loss threshold 95b
- **LEADER_AGGRESSIVE**: ostáva — horníci k súperom stále žiaduce

## Known issues / TODO
- Sweep WATCHING vs 90+ logika konflikt
- Útočnejší play ak som posledný (najmenej bodov)
- Horník dump heuristika (komu nasoliť pri voide)
- "Beriem všetko" declaration logika — nie je implementovaná
- Správanie ostatných hráčov proti "none" záväzku
- Výber escape karty — náhodnosť pri rovnocenných možnostiach
- Last resort leader ignoruje protected suits

## Diagram volaní
AI.decide_card()
├── HandEvaluator.evaluate()              [ai_hand_eval.py]
│   └── AIMemory.build_all_profiles()    [ai_memory.py]
├── GameContext.build()                   [ai_hand_eval.py]
├── SweepPipeline.evaluate()             [ai_sweep.py]
│   └── L1 → L2 → L3 → L4 → L5 → L6 → L7
├── SituationDetector.determine()        [ai_situation.py]
├── SituationDetector.to_mode()          [ai_situation.py]
└── CardSelector.select()                [ai_card_select.py]

Teraz 03_CONVENTIONS.md:
markdown# Konvencie projektu CHUJ

## Jazyk
- Komentáre v kóde: **slovenčina**
- Názvy premenných, funkcií, tried: **angličtina**
- Komunikácia s Claudom: **slovenčina**

## Kódovací štýl
- Python 3.11+, type hints všade
- Dataclasses pre štruktúrované výstupy (`HandEval`, `SuitProfile`)
- `|` namiesto `Union` pre type hints (`Card | None`)
- Indentácia: 4 medzery
- Max dĺžka riadku: ~100 znakov

## Pomenovanie kariet
```python
RANK_DISPLAY = {"ace": "A", "king": "K", "over": "Q", "under": "J", ...}
SUIT_DISPLAY = {"heart": "♥", "bell": "●", "leaf": "♠", "acorn": "♣"}
# card.__str__() → "A♥", "Q♠", "7♣"
```

## Logovanie AI stratégií
```python
self._log(Strategy.SAFE_LEAD, f"escape: {card}")
# → volá: self.logger.log_strategy(player_name, strategy, details)
# → výstup: [AI Počítač 1] L1-SAFE_LEAD: escape: 7♣
```

## Stratégie — aktuálny zoznam
```python
class Strategy:
    # Leader
    SAFE_LEAD       = "L1-SAFE_LEAD"
    FORCE_SPECIAL   = "L2-FORCE_SPECIAL"
    DUMP_SETUP      = "L3-DUMP_SETUP"
    HIGH_SCORE_LEAD = "L4-HIGH_SCORE_LEAD"
    RISK_SPECIAL    = "L5-RISK_SPECIAL"

    # Follower
    UNDERPLAY       = "F1-UNDERPLAY"
    FORCED_TAKE     = "F2-FORCED_TAKE"
    LAST_TAKE       = "F3-LAST_TAKE"
    DUMP_FREE       = "F4-DUMP_FREE"
    WAIT            = "F5-WAIT"
    DUMP_SPECIAL    = "F6-DUMP_SPECIAL"
    DUMP_HEART      = "F7-DUMP_HEART"
    DUMP_DANGEROUS  = "F8-DUMP_DANGEROUS"

    # Proti záväzku
    BREAK_ALL       = "A1-BREAK_ALL"
    BREAK_NONE      = "A2-BREAK_NONE"

    # Záväzok
    DECLARATION_ALL  = "D1-DECLARATION_ALL"
    DECLARATION_NONE = "D2-DECLARATION_NONE"
```

## Rozdelenie zodpovedností
- `ai_memory.py` — LEN pamäť a inferencia, nikdy "zahraj kartu X"
- `ai.py` — LEN rozhodovacia logika, nikdy low-level tracking
- `ai_card_select.py` — LEN selekcia karty, žiadna detekcia situácie
- `ai_situation.py` — LEN detekcia situácie, žiadna selekcia karty
- `screen.py` — GUI a event handling, volá AI metódy
- `round.py` — herná logika, fázy kola
- `player.py` — stav hráča, bodovanie

## Fonty
```python
# Vždy používať get_font() z config.py — podporuje Unicode znaky (♥ ● ♠ ♣)
from config import get_font
self.font_small = get_font(24)
# NIKDY: pygame.font.SysFont(None, 24)
# Emoji nie sú podporované — používaj text
```

## Pravidlá pre zmeny v chate
- Pri zmenách posielaj **snippet metódy**, nikdy nie celý súbor
- Pri bugoch: najprv popíš problém + kde sa nachádza, potom oprav
- Pri viacerých bugoch: informuj o všetkých, opravuj **po jednom** so schválením
- Odbočky označuj: "odbočka: ..." a "späť k hlavnej téme"

## Seed systém
- `Deck.deal()` vracia `(hands, seed)` — seed sa ukladá do `Round.deal_seed`
- Seed je per-kolo (nie per-hra)
- `random.Random(seed)` — lokálny RNG, nie globálny `random`
- Tester používa rovnaký algoritmus rozdávania (4+4) ako hra
- Posledný seed sa ukladá do `Documents/Chuj/last_seed.txt`

## Tester
- Spúšťa sa z koreňa projektu: `python tester_main.py`
- Bez argumentov: načíta posledný seed z `Documents/Chuj/last_seed.txt`
- Random scenár: `python tester_main.py --random`
- Konkrétny seed: `python tester_main.py --seed 487123`
- AI sami rozhodnú o vysvietení a záväzkoch
- Override vysvietenia a first playera cez setup bar

## Projekt je "vibe coding"
- Vysvetli nuansy ak si niečo neistý
- Pre triviálne zmeny (typo, jasný bug) urob priamo bez pýtania
- Pre architektúrne zmeny počkaj na potvrdenie
- Pri návrhu: najprv koncept so súhlasom, potom implementácia