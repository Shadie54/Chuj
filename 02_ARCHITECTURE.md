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
    ctx = GameContext.build(self.player.index, all_scores or [...])

    sweep_result = self.sweep_pipeline.evaluate(hand_eval, trick_number)
    if sweep_result.decision == YES:
        if sweep_result.recommended_card in playable:
            return sweep_result.recommended_card

    situation = self.situator.determine(hand_eval, playable, current_trick, ctx)
    mode = self.situator.to_mode(situation, current_trick)
    card = self.selector.select(mode, situation, hand_eval, playable, current_trick)
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

`GameContext.build(my_index, all_scores)` vracia:

| Pole | Popis |
|------|-------|
| `my_score` | moje celkové skóre |
| `all_scores` | skóre všetkých hráčov |
| `is_high_score` | my_score >= 90 |
| `score_rank` | 1=vediem, 4=posledný |
| `gap_to_leader` | rozdiel od lídra (0 ak vediem) |
| `gap_to_last` | rozdiel od posledného (0 ak som posledný) |

### 2. SITUATION (`ai_situation.py`)

**Leader situácie:**

| Situácia | Trigger | Mode |
|----------|---------|------|
| `LEADER_AGGRESSIVE` | súper má horníka, mám non-A/K v jeho farbe | TAKE |
| `LEADER_SAFE` | mám non-heart escape karty | SAFE |
| `LEADER_FORCED` | nemám escape | OPEN |

**Follower situácie:**

| Situácia | Trigger | Mode |
|----------|---------|------|
| `FOLLOWER_VOID` | nemám lead suit | OPEN |
| `FOLLOWER_SAFE` | viem podliezť | SAFE |
| `FOLLOWER_FREE_TAKE` | vysvietený horník u skoršieho hráča už zahral nehorníka + mám A/K | TAKE |
| `FOLLOWER_CONTROLLED` | nedá sa podliezť, štich bez bodov, posledný | dynamic |
| `FOLLOWER_WAIT` | niekto iný pravdepodobne berie | OPEN |
| `FOLLOWER_FORCED` | ja určite vyhrám štich (nedá sa podliezť) | TAKE |

### 3. CARD (`ai_card_select.py`)

**SAFE mode:**
- Leader: najnižšia non-heart escape (mimo protected suits)
  - `_protected_suits()` — chráni farbu kde som svietil horníka a mám málo rezerv; ignoruje farby kde horník už padol
- Follower: horník má prioritu ak je v underplay → inak najvyššia podliezka

**TAKE mode:**
- `LEADER_AGGRESSIVE`: najnižšia non-A/K v cudzej horník-farbe
- Follower: najvyššia non-special lead karta

**OPEN mode:**
- `FOLLOWER_VOID` → `_void_discard()`:

Horník (najviac bodov)
Trap A/K vo farbe živého horníka — len ak nemám escape pod každú remaining kartu (greedy párovanie 1:1)
Hearts (najvyššia)
Iné trap karty (najvyššia)
Bell (najvyššia) → inak najvyššia non-special non-heart

- `FOLLOWER_WAIT` bezbodový štich:
Trap karty → najnižšia trap
Bez trapu → najvyššia escape
- `FOLLOWER_WAIT` bodový štich: najnižšia karta

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
- `"all"` — beriem všetky štichy
- `"none"` — nechytím žiadny štich
- `None` — žiadny záväzok

### `decide_illumination(first_player_index, all_scores=None)`
- Hodnotí rezervu horníka (počet podporných kariet + kvalita)
- Hodnotí riziko červených: každý nekrytý vysoký červeň (A/K bez buffera) = +4b očakávaná penalizácia
- Hodnotí kompenzáciu: void farby (+1 každá), posledný hráč (+1)
- **90+ veto** — ak `my_score >= 90`:
  - `high_score_unprotected_hearts` — vysoký červeň bez buffera
  - `high_score_naked_high` — nahý vysoký bell bez buffera
- **is_leader veto** — ak vediem skóre (`max_score > 0`) a rezerva = borderline → nevysvietim
- Vypočíta `is_leader` z `all_scores` (True ak mám max skóre a `max_score > 0`)

## Logovanie stratégií

```python
self._log(Strategy.SAFE_LEAD, f"escape: {card}")
# → [AI Počítač 1] L1-SAFE_LEAD: escape: 7♣
```

### Konštanty stratégií (`ai_strategies_const.py`)

```python
class Situation:
    LEADER_SAFE, LEADER_FORCED, LEADER_AGGRESSIVE
    FOLLOWER_SAFE, FOLLOWER_VOID, FOLLOWER_FORCED
    FOLLOWER_CONTROLLED, FOLLOWER_WAIT, FOLLOWER_FREE_TAKE

class Mode:
    SAFE, TAKE, OPEN

class Strategy:
    # Leader
    SAFE_LEAD, FORCE_SPECIAL, DUMP_SETUP
    # Follower
    UNDERPLAY, FORCED_TAKE, LAST_TAKE, WAIT
    DUMP_SPECIAL, DUMP_HEART, DUMP_DANGEROUS
    # Záväzok
    BREAK_ALL, BREAK_NONE, DECLARATION_ALL, DECLARATION_NONE
```

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