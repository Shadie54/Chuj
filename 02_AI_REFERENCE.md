# AI Referencia — CHUJ

## Pipeline (každý ťah)
```
AI.decide_card()
  ├── easy difficulty → random.choice(playable)
  ├── GameContext.build()
  ├── HandEvaluator.evaluate() → HandEval
  ├── ROUTER: declaration_type == "none" → NonePlayer.decide()
  ├── ROUTER: my_declaration == "all"   → AllPlayer.decide()
  ├── DecisionContext.build()
  ├── SweepPipeline.evaluate() → SweepResult
  │     YES + card in playable → zahraj a koniec
  ├── SituationDetector.determine() → Situation
  ├── SituationDetector.to_mode() → Mode
  └── CardSelector.select() → Card
```

---

## Memory — AIMemory

Každý AI má vlastnú inštanciu. Volanie `init_with_hand()` po rozdaní odstráni moje karty z `remaining`.

Kľúčové polia:
- `played_cards: set[Card]` — všetky zahrané karty
- `remaining[suit]` — karty ešte u súperov
- `void_suits[player_idx]` — preukázané voidy
- `suits_led: set[str]` — farby ktoré boli vedené ako lead
- `special_possible_holders[suit]` — kto môže mať horníka
- `special_gone[suit]` — či horník padol
- `illuminated_by[suit]` — kto vysvietil (presne vieme)
- `tricks_taken[player_idx]`, `discards[player_idx]`

### SuitProfile (z `build_suit_profile()`)
- `trap_cards` — nikto vyšší vonku → zoberiem štich
- `escape_cards` — niekto vyšší vonku → môžem podliezť
- `safe_cards` — všetci vonku sú vyšší → garantovane nevyhrám
- `coverage` — remaining[suit] + karty farby v aktuálnom štichu
- `has_special`, `special_reserves` (počet kariet okrem horníka)

---

## Kontexty

### GameContext
- `my_score`, `is_high_score` (≥90), `score_rank` (1=vediem), `my_declaration`

### DecisionContext (vypočíta sa raz na ťah)
- `is_leader`, `is_last`, `lead_suit`, `lead_cards`
- `players_after` — hráči ktorí ešte nehrajú
- `someone_takes` — `"yes"` / `"maybe"` / `"no"`
- `can_be_beaten` — môže niekto prebiť moju najnižšiu lead kartu
- `trick_has_penalty` — štich má body ALEBO akýkoľvek horník v played_cards
- `protected_suits` — svietil som horníka + ≤3 rezervy + horník živý
- `exhaustable_suits` — svietil som + ≥4 rezervy + žiadny A/K v rezervách
- `special_holders[suit]` — set hráčov ktorí môžu mať horníka

---

## Situácie a mody

### Leader — poradie kontroly

| Situácia | Podmienka | Mode |
|----------|-----------|------|
| `L-AGGRESSIVE` | hard, cudzí horník živý, mám non-A/K v jeho farbe (veto: posledná taká karta) | TAKE |
| `L-HIGH_SCORE` | is_high_score + mám prebytočné nízke heart | SAFE |
| `L-SAFE` | existuje escape karta (vrátane heart) ALEBO bell ešte nebola vedená a mám bell | SAFE |
| `L-RISK` | mám horníka + v tej farbe len A/K + vonku vyššia non-special | OPEN |
| `L-FORCED` | fallback | OPEN |

**Poznámka k `L-SAFE`**: podmienka je `non_heart_escape OR bell_escape_possible`, kde `bell_escape_possible = "bell" not in suits_led AND mám bell kartu`.

### Follower — poradie kontroly

| Situácia | Podmienka | Mode |
|----------|-----------|------|
| `F-VOID` | nemám lead suit | OPEN |
| `F-FREE_TAKE` | lead=leaf/acorn, mám A/K, cudzí svietil a hral, žiadny horník v triku, bezpečné | TAKE |
| `F-RISK` | 3. v poradí, trap A/K + jedna escape, nevysvietený horník, náhodná šanca (0.2/0.5/0.7 podľa score_rank) | RISK |
| `F-FORCED_CLEAN` (early) | is_last + čistý štich + mám bell A/K | TAKE |
| `F-EARLY_TAKE` | 2./3. pozícia, lead=bell, čistý štich, ≥2 bell karty, bell ešte nebola vedená, remaining≥5 | TAKE |
| `F-SAFE` | viem podliezť (mám kartu nižšiu ako current_best) | SAFE |
| `F-FORCED_CLEAN` | is_last alebo nemôže byť prebytý, čistý štich | TAKE |
| `F-FORCED_POINTS` | is_last alebo nemôže byť prebytý, bodový štich | TAKE |
| `F-WAIT` | niekto po mne môže biť a pravdepodobne nevyhrám | OPEN |

---

## CardSelector — SAFE mode

### Leader SAFE
1. `L-HIGH_SCORE`: najvyššia prebytočná nízka heart → `L4-HIGH_SCORE_LEAD`
2. `_bell_escape()` (vždy pred escape_playable filtrom):
   - Guard: `"bell" in suits_led` → None
   - Trap+non-trap bell: ak remaining≥5 a my_count≤2 → dump trap bell
   - my_count==1: non-trap → zahraj; osamelý trap → zahraj ak bell nebola vedená
   - my_count≥2: non-trap cez `_risk_pick()`
3. `escape_playable` filter (vetá): is_special, protected_suits, `_is_last_escape_in_dangerous_suit()`, escape A/K v farbe živého cudzieho horníka, posledný buffer pre môjho horníka
4. Z escape_playable: leaf/acorn → `min`; ostatné → `min` → `L1-SAFE_LEAD`
5. `exhaust_cards` filter → `min` → `L1-SAFE_LEAD`
6. Last resort: protected escape → `min(non_special)` → `L1-SAFE_LEAD`

### Follower SAFE
Dump blok (ak lead=leaf/acorn, horník živý, žiadny horník v triku, `someone_takes != "no"`):
- Ak `not dangerous_after` (nikto po mne nemôže mať horníka):
  - Dump môjho horníka ak podlieza current_best → `F6-DUMP_SPECIAL`
  - Dump trap A/K (môj nevysvietený horník, 3. v poradí) → `F8-DUMP_DANGEROUS`
  - Dump trap A/K (všeobecné) → `F4-DUMP_FREE` (is_last) / `F8-DUMP_DANGEROUS`
- `max(underplay)` → `F1-UNDERPLAY`; ak horník v underplay → `F6-DUMP_SPECIAL`
- Fallback: `min(playable)`

---

## CardSelector — TAKE mode

| Situácia | Logika | Kód |
|----------|--------|-----|
| `L-AGGRESSIVE` | `_aggressive_card()` — vlastná void-riziko matica | `L2-FORCE_SPECIAL` |
| `F-FORCED_CLEAN` | `_controlled_take()`: dump trap A/K (is_last) → max non-special lead | `F3-LAST_TAKE` / `F2-FORCED_TAKE` |
| `F-FREE_TAKE` | `_free_take()`: max A/K non-special lead | `F4-DUMP_FREE` |
| `F-RISK` | `_risk_trap()`: max trap A/K | `F9-RISK_TRAP` |
| `F-EARLY_TAKE` | `_early_take()`: bell cez `_risk_pick()`, ak < current_best → max(underplay) | `F10-EARLY_TAKE` |
| štandard | is_last → max; inak → min non-special lead | `F2-FORCED_TAKE` |

### `_aggressive_card()` matica (LEADER_AGGRESSIVE forcing)
- remaining≥5: my_count 1-2 → max; 3 → mid; 4+ → min
- remaining<5: my_count 1-2 → mid; 3+ → min
- `mid = _mid_card_relative()` — najvyššia kde rank_order rozdiel od max v ruke ≥2

### `_risk_pick()` matica (bell escape + early_take)
- remaining≥5: my_count≤2 → max; ==3 → mid; ≥4 → safe/min
- remaining<5: my_count≤2 → mid; ≥3 → safe/min

---

## CardSelector — OPEN mode

### `F-VOID` → `_void_discard()`
**Štandard** (priorita):
1. Horník (max bodov) → `F6-DUMP_SPECIAL`
2. A/K vo farbe živého horníka (danger_trap cez all_covered check) → `F8-DUMP_DANGEROUS`
3. Max heart → `F7-DUMP_HEART`
4. Trap (non-heart, non-special) → `F8-DUMP_DANGEROUS`
5. Max bell → `F5-WAIT`
6. Fallback max → `F5-WAIT`

**90+ (`is_high_score`)** (priorita):
1. Near loss (score + expected_damage ≥ 95) + trap hearts → `F7-DUMP_HEART`
2. Horník → `F6-DUMP_SPECIAL`
3. Trap hearts → `F7-DUMP_HEART`
4. Non-safe hearts → `F7-DUMP_HEART`
5. Fallback → štandard

### `L-RISK` → `_risk_play()`
Horník kde vonku vyššia non-special → `L5-RISK_SPECIAL`

### `L-FORCED` / `F-WAIT` → `_open_play()`
**Leader**:
1. Void setup (1 karta farby, non-heart, non-protected, non-trap) → `L3-DUMP_SETUP`
2. Min escape → `F5-WAIT`
3. Min exhaust → `F5-WAIT`
4. Fallback min non-special

**Follower**:
1. Min escape → `F5-WAIT`
2. Čistý štich: dump horník → `F6-DUMP_SPECIAL`; dump trap → `F8-DUMP_DANGEROUS`; dump high → `F8-DUMP_DANGEROUS`
3. Bodový štich: min lead → `F5-WAIT`
4. Fallback min non-special

---

## Sweep Pipeline (ai_sweep.py)

Stavy: `IDLE` → `WATCHING` → `COMMITTED_SAFE` → `COMMITTED_FULL`

### Vrstvy
- **L1 Hard Gates**: Gate1 (žiadny súper nemá trestnú kartu), Gate4 (trick≤1 → max WATCHING), Gate2 (min sila ruky: hearts-driven/control-driven/hornik-bait), Gate3 (vypnuté — vždy False)
- **L2 Hand Evaluation**: sila ruky STRONG/MEDIUM/WEAK, profil HEARTS_DRIVEN/CONTROL_DRIVEN/MIXED/HORNIK_BAIT
- **L3 Suit Control**: per-suit timeline, cross-suit analýza, critical events, odporúčané poradie lead
- **L4 Opponent Modeling**: pravdepodobnosti umiestnenia kariet, distribúcia
- **L5 Targeted Simulation**: kandidátne karty + P(sweep)
- **L6 Escape Evaluation**: escape quality (NOT_NEEDED/CLEAN/CONTAINED/MESSY/DISASTER), EV výpočet, commit type
- **L7 Decision**: P=1.0 → YES okamžite; force_watching (L1 alebo L2) downgrade commit; COMMITTED_FULL/SAFE → YES; WATCHING → NO s state WATCHING

---

## Vyhlásené hry

### NonePlayer (ai_play_none.py) — platí pre VŠETKÝCH hráčov
- **Leader**: `min(playable)`, vyhni sa farbe kde je vyhlasovateľ void
- **Follower má lead suit**: posledný + nie som deklarant + nemôžem podliezť → `max`; deklarant prebytý → `max`; inak → `max(underplay)` alebo `min`
- **Follower void**: `max(playable)`

### AllPlayer (ai_play_all.py) — len deklarant
- Trap → `_best_trap()` (farba s najviac trapmi, najvyššia)
- Escape → `max(escape)`
- Fallback → `max(playable)`

---

## Declaration / Illumination (ai_declaration.py)

### `decide_declaration()` — záväzok "none"
Skórovací systém rizika:
- **Veto**: horník, osamelý J/Q/K/A bez bufferov, A/K/Q bez ≥2 nízkych
- Riziko: 10 osamelá=+4, 10 s 1 nízkou=+1, J s 1=+2, Q/K/A s 2+ nízkymi=+1
- Kompenzácia: void farba=−4
- Threshold: ≤0 vždy; 1–4 hard difficulty; >4 nikdy
- Záväzok "all": nie je implementovaný (vracia None)

### `decide_illumination()`
- Rezerva: `_reserve_quality()` → strong/good/borderline/bad/plonk
- Riziko: `_hand_risk_level()` — nekryté vysoké heart/bell/leaf/acorn = expected_penalty
- Kompenzácia: void farby (+1 každá), posledný hráč (+1)
- **90+ veto**: nekryté high heart → stop; nahý high bell bez low → stop
- **is_leader veto**: borderline rezerva → nesvietiť
- Rozhodovacia tabuľka (reserve_quality × risk_level × compensation)

---

## Situation Trace (tester-only)

`SituationDetector._trace()` → `TesterLogger.log_situation_trace()` ak logger má túto metódu.
Symboly: ✓=PASS, ✗=FAIL, ·=SKIP, ?=CHECK

```
[AI_3] SITUATION_TRACE:
  ✗ L-AGGRESSIVE: FAIL — žiadny vhodný cudzí horník v leaf/acorn
  · L-HIGH_SCORE: SKIP — not is_high_score
  ✓ L-SAFE: PASS — escape dostupný: 2 kariet
```

## Log formát
```
[AI Počítač 1] L-SAFE | SAFE | L1-SAFE_LEAD: escape bell: 9●
               ^^^^^^   ^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
               situácia  mode  stratégia + detail
```

---

## Known Issues / TODO

### Rozpracované
- `_bell_escape()` trap bell vetva (trap+non-trap podmienka na začiatku) — správanie pri my_count≤2 a remaining≥5 je nové, potrebuje otestovanie
- Follower leaf/acorn risk logika — obdoba `_early_take()` pre leaf/acorn
- `_is_trap()` pre leader kontext — vlastná vyššia karta nesprávne chráni pred trap statusom

### Dlhodobé
- AllPlayer ("Beriem všetko") — len stub logika
- Správanie ostatných hráčov proti "all" — nie je implementované
- 90+ follower logika
- Blízko hranice (85–89b → cielene na 90; blízko 100 → reset na 90)
- Sweep WATCHING vs 90+ konflikt
- Candidate scoring systém — namiesto hierarchického waterfall
