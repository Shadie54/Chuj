# AI Pipeline — CHUJ

## Prehľad

Každý ťah AI prechádza týmto poradím:

```
decide_card()
  ├── GameContext.build()
  ├── HandEvaluator.evaluate() → HandEval
  ├── ROUTER: none/all záväzok
  ├── DecisionContext.build()
  ├── SweepPipeline.evaluate()
  ├── SituationDetector.determine() → Situation
  ├── SituationDetector.to_mode() → Mode
  └── CardSelector.select() → Card
```

---

## 1. GameContext

Vypočíta sa pred všetkým. Obsahuje skórový kontext.

| Pole | Výpočet | Použitie |
|------|---------|---------|
| `my_score` | `all_scores[my_index]` | Skóre tohto hráča |
| `is_high_score` | `my_score >= 90` | Aktivuje 90+ logiku |
| `score_rank` | Poradie v skóre (1=vediem, 4=posledný) | RISK faktor |
| `gap_to_leader` | `max(all_scores) - my_score` | Budúce použitie |
| `gap_to_last` | `my_score - min(all_scores)` | Budúce použitie |
| `my_declaration` | Z `AI.declaration_type` ak `declaration_player == my_index` | Router pre none/all |

---

## 2. HandEval

Snapshot stavu ruky. Vypočíta sa cez `AIMemory.build_all_profiles()`.

### SuitProfile (per farba)

| Pole | Podmienka | Vysvetlenie |
|------|-----------|-------------|
| `trap_cards` | Nikto vyšší vonku (remaining + trick) | Zoberiem štich |
| `escape_cards` | Niekto vyšší vonku | Môžem podliezť (nie garantované) |
| `safe_cards` | Všetci vonku sú vyšší | Garantovane nevyhrám |
| `coverage` | `remaining[suit] + trick_suit_cards` | Vyššie karty vonku |
| `has_special` | Mám horníka tejto farby | — |
| `special_reserves` | Počet kariet okrem horníka | — |

### HandEval agregáty

| Pole | Zdroj |
|------|-------|
| `trap_cards` | Všetky trap karty zo všetkých SuitProfile |
| `escape_cards` | Všetky escape karty zo všetkých SuitProfile |
| `void_suits` | Farby kde `count == 0` |

---

## 3. Router: Vyhlásené hry

```
if my_declaration == "none" → NonePlayer.decide()
if my_declaration == "all"  → AllPlayer.decide()
```

Ak nie je záväzok → pokračuje normálny pipeline.

**NonePlayer logika:**
- Leader: `max(playable)` — pustíme niekoho na štich
- Follower (má lead suit): `max(underplay)` — podliezaj; ak nie je možné → `min(lead_cards)`
- Follower (void): `min(playable)` — najnižšia

**AllPlayer logika:**
- Vždy leader (ak stratí lead, hra končí fail)
- Trap karta → `_best_trap()` (farba s najviac trapmi, najvyššia)
- Ak nie je trap → najvyššia escape
- Fallback → `max(playable)`

---

## 4. DecisionContext

Vypočíta sa raz, odovzdá sa všetkým handlerom.

| Pole | Výpočet | Podmienka/Poznámka |
|------|---------|-------------------|
| `is_leader` | `len(trick.played_cards) == 0` | — |
| `is_last` | `len(trick.played_cards) == NUM_PLAYERS - 1` | — |
| `lead_suit` | `trick.lead_suit` | None ak leader |
| `lead_cards` | `[c for c in playable if c.suit == lead_suit]` | Prázdny ak leader alebo void |
| `players_after` | Hráči v poradí po mne ktorí ešte nehrali | — |
| `someone_takes` | `memory.will_someone_else_take(...)` | `"yes"` / `"maybe"` |
| `can_be_beaten` | `memory.can_anyone_beat(my_lowest, players_after, trick_cards)` | Len ak mám lead_cards |
| `trick_has_penalty` | `trick.total_base_points > 0` alebo horník v played_cards | — |
| `protected_suits` | Farby kde som svietil horníka + `len(reserves) <= 3` + horník živý | Chráni lead z tejto farby |
| `exhaustable_suits` | Farby kde som svietil + `len(reserves) >= 4` + žiadny A/K v reserves | Môžem vyčerpať farbu |
| `special_holders` | `memory.who_has_special(suit)` pre leaf a acorn | Set hráčov ktorí môžu mať horníka |

---

## 5. Sweep Pipeline

Ak `SweepDecision.YES` a `recommended_card in playable` → zahraj túto kartu, koniec.
Inak → pokračuj normálnym pipeline.

---

## 6. SituationDetector — Leader

### Poradie kontroly situácií:

```
1. LEADER_AGGRESSIVE
2. LEADER_HIGH_SCORE (ak is_high_score)
3. LEADER_SAFE
4. LEADER_RISK
5. LEADER_FORCED (fallback)
```

### LEADER_AGGRESSIVE
**Podmienky (všetky musia platiť):**
- `difficulty == "hard"`
- Iterujem cez `("leaf", "acorn")`
- `not memory.is_special_gone(suit)` — horník živý
- `special_holders[suit]` nie je prázdny
- `my_index not in special_holders[suit]` — nemám horníka ja
- Existuje karta v playable: `suit == suit`, `not is_special`, `rank not in ("ace", "king")`
- **Veto:** ak je to posledná non-A/K karta v tej farbe a ostanú len A/K → `continue`

**Následok:** Mode=TAKE → `_play_take()` → `L2-FORCE_SPECIAL`

### LEADER_HIGH_SCORE
**Podmienky:**
- `game_ctx.is_high_score == True` (my_score >= 90)
- Mám prebytočné nízke červene: `len(low_hearts) - len(high_hearts) > 0`
- Existuje nízka červeň v playable (`rank in ("seven","eight","nine")`)

**Ak nie → fallback na LEADER_SAFE alebo LEADER_FORCED v rámci `_leader_high_score()`**

**Následok:** Mode=SAFE → `_play_safe()` → `L4-HIGH_SCORE_LEAD`

### LEADER_SAFE
**Podmienky:**
- Existuje escape karta: `suit != "heart"`, `not is_special`, `c in playable`

**Následok:** Mode=SAFE → `_play_safe()` → `L1-SAFE_LEAD`

### LEADER_RISK
**Podmienky (všetky musia platiť pre aspoň jeden suit z leaf/acorn):**
- `not memory.is_special_gone(suit)`
- Mám horníka v playable pre tento suit
- Mám non-special karty tohto suitu v playable
- Všetky non-special karty sú A alebo K (`all_high == True`)
- Existujú vyššie non-special karty v `remaining[suit]` ako môj horník

**Následok:** Mode=OPEN → `_play_open()` → `L5-RISK_SPECIAL`

### LEADER_FORCED
**Podmienky:** Žiadna z vyššie uvedených situácií nenastala

**Následok:** Mode=OPEN → `_play_open()` → rôzne stratégie

---

## 7. SituationDetector — Follower

### Poradie kontroly situácií:

```
1. FOLLOWER_VOID
2. FOLLOWER_FREE_TAKE
3. FOLLOWER_RISK
4. FOLLOWER_SAFE
5. FOLLOWER_FORCED_CLEAN / FOLLOWER_FORCED_POINTS / FOLLOWER_WAIT
```

### FOLLOWER_VOID
**Podmienka:** `lead_cards` je prázdny (nemám lead suit)

**Následok:** Mode=OPEN → `_play_open()` → `_void_discard()`

### FOLLOWER_FREE_TAKE
**Podmienky `_trick_is_free_to_take()` (všetky musia platiť):**
- `lead_suit != "heart"`
- `lead_suit in ("leaf", "acorn")`
- Mám A alebo K v `lead_cards`
- `not memory.is_special_gone(lead_suit)`
- `illuminated_by[lead_suit] is not None` — niekto vysvietil
- `illuminated_by[lead_suit] != my_index` — nie ja
- Illuminator už zahral v štichu
- **Veto:** akýkoľvek horník je v played_cards → `False`
- **Veto:** void hráč po mne môže mať druhého horníka → `False`

**Následok:** Mode=TAKE → `_play_take()` → `F4-DUMP_FREE`

### FOLLOWER_RISK
**Podmienky (všetky musia platiť):**
- `not is_last` a `len(players_after) == 1` — som tretí v poradí
- `not game_ctx.is_high_score`
- `not (80 <= my_score <= 89)`
- `_should_risk_trap()` vrátil True:
  - Nemám horníka v lead_cards
  - `lead_suit in ("leaf", "acorn")`
  - `not memory.is_special_gone(lead_suit)`
  - Žiadny horník v played_cards
  - `illuminated_by[lead_suit] is None` — nevysvietený
  - Mám trap A/K v lead_cards
  - Mám presne jednu escape (non-A/K) v lead_cards
  - Náhodnostný faktor: rank=1 → 20%, rank=4 → 70%, inak → 50%

**Následok:** Mode=RISK → `_play_take()` → `F9-RISK_TRAP`

### FOLLOWER_SAFE
**Podmienka:** `can_underplay == True`
- `any(c.rank_order < current_best.rank_order for c in lead_cards)`

**Následok:** Mode=SAFE → `_play_safe()` → `F1-UNDERPLAY` alebo `F6-DUMP_SPECIAL` alebo `F8-DUMP_DANGEROUS`

### FOLLOWER_FORCED_CLEAN / FOLLOWER_FORCED_POINTS / FOLLOWER_WAIT
**Pomocné výpočty:**
- `i_will_likely_win`: mám len 1 lead kartu + nikto vyšší v remaining + nikto vyšší v trick
- `can_be_beaten`: z DecisionContext

**Rozvetvenie:**
```
trick_has_penalty == False:
  is_last → FOLLOWER_FORCED_CLEAN
  can_be_beaten and not i_will_likely_win → FOLLOWER_WAIT
  inak → FOLLOWER_FORCED_CLEAN

trick_has_penalty == True:
  is_last → FOLLOWER_FORCED_POINTS
  can_be_beaten and not i_will_likely_win → FOLLOWER_WAIT
  inak → FOLLOWER_FORCED_POINTS
```

---

## 8. CardSelector — SAFE mode

### Leader SAFE

**escape_playable filter (všetky podmienky):**
- `c in hand_eval.escape_cards`
- `c in playable`
- `not c.is_special`
- `c.suit not in protected_suits`
- `not _is_last_escape_in_dangerous_suit(c)`:
  - `suit in ("leaf", "acorn")`
  - `not is_special_gone(suit)`
  - `special_holders[suit]` nie je prázdny
  - `not i_have_special` (nemám horníka tejto farby)
  - `remaining_escapes == []` (posledná escape)
  - `high_cards` obsahuje trap A/K → True (veto)
- **Veto escape A/K vo farbe živého cudzieho horníka:**
  - `c.rank in ("ace", "king")`
  - `c.suit in ("leaf", "acorn")`
  - `not is_special_gone(c.suit)`
  - `not i_have_special v tejto farbe`

**Ak escape_playable:** `min(rank_order)` → `L1-SAFE_LEAD`

**exhaust_cards filter:**
- `not c.is_special`
- `c.suit not in protected_suits` alebo `c.suit in exhaustable_suits`
- Nie je to karta vo farbe živého horníka kde ja nemám horníka

**Ak exhaust_cards:**
- Risk check: ak je to A/K vo farbe kde mám horníka + vonku vyššia karta → `L5-RISK_SPECIAL`
- Inak: `min(rank_order)` → `L1-SAFE_LEAD`

**Last resort:**
- Prednostne escape z protected suits
- Inak `min(non_special)` → `L1-SAFE_LEAD`

### Follower SAFE

**Dump blok (ak lead_suit in leaf/acorn + horník živý):**

```
Podmienky pre vstup do dump bloku:
1. not is_special_gone(lead_suit)
2. has_live_special: mám horníka alebo special_holders nie je prázdny
3. not special_in_trick: žiadny horník (akýkoľvek) v played_cards
4. effective_takes == "yes":
   - is_last and not winner_is_me → "yes"
   - inak: dctx.someone_takes
```

**Ak vstúpim do dump bloku:**
```
dangerous_after:
  - Ak mám horníka sám → False
  - Inak: any(p in special_holders[suit] for p in players_after)

Ak not dangerous_after:
  A) Dump horníka: mám horníka + je v lead_cards + rank < current_best → F6-DUMP_SPECIAL
  B) Dump trap A/K (mám horníka nevysvieteného, som 3.v poradí):
     - illuminated_by[suit] is None
     - len(players_after) == 1
     - Existuje trap A/K v lead_cards → F8-DUMP_DANGEROUS
  C) Dump trap A/K (všeobecné):
     - Existuje A/K (non-special) v lead_cards
     - F4-DUMP_FREE ak is_last, inak F8-DUMP_DANGEROUS
```

**Underplay:**
- `underplay = [c for c in lead_cards if c.rank_order < current_best.rank_order]`
- Ak horník v underplay → `F6-DUMP_SPECIAL`
- Inak `max(underplay)` → `F1-UNDERPLAY`

**Fallback:** `min(playable)`

---

## 9. CardSelector — TAKE mode

### LEADER_AGGRESSIVE → L2-FORCE_SPECIAL
- Iteruj cez leaf/acorn
- Nájdi najnižšiu non-A/K kartu v suit kde súper má horníka

### FOLLOWER_RISK → F9-RISK_TRAP
- `max(trap_high)` z lead_cards

### FOLLOWER_FORCED_CLEAN → `_controlled_take()`
```
Ak is_last:
  danger = trap A/K v lead_cards → max(danger) → F3-LAST_TAKE
Najvyššia non-special lead:
  is_last → F3-LAST_TAKE
  inak → F2-FORCED_TAKE
```

### FOLLOWER_FREE_TAKE → `_free_take()`
- A/K non-special v lead_cards → `max` → F4-DUMP_FREE
- Fallback: najvyššia non-special lead → F3-LAST_TAKE

### FOLLOWER_FORCED_POINTS / štandard
```
is_last → max(non_special_lead) → F2-FORCED_TAKE
inak → min(non_special_lead) → F2-FORCED_TAKE
```

---

## 10. CardSelector — OPEN mode

### FOLLOWER_VOID → `_void_discard()`

**Router:**
```
my_declaration == "none" → _void_discard_none(): max(non_special)
is_high_score → _void_discard_high_score()
inak → _void_discard_standard()
```

**`_void_discard_standard()` priorita:**
1. Horník (max bodov) → F6-DUMP_SPECIAL
2. Trap A/K vo farbe živého horníka kde nemám escape krytie → F8-DUMP_DANGEROUS
3. Hearts (najvyššia) → F7-DUMP_HEART
4. Iné trap karty (najvyššia) → F8-DUMP_DANGEROUS
5. Bell (najvyššia) → F5-WAIT
6. Fallback high → F5-WAIT

**`_void_discard_high_score()` priorita:**
1. Near loss (my_score + expected_damage >= 95) + trap hearts → F7-DUMP_HEART
2. Horník (max bodov) → F6-DUMP_SPECIAL
3. Trap hearts → F7-DUMP_HEART
4. Non-safe hearts → F7-DUMP_HEART
5. Fallback → `_void_discard_standard()`

### LEADER_RISK → `_risk_play()`
- Horník kde vonku vyššia non-special karta → F5-RISK_SPECIAL

### LEADER_FORCED / FOLLOWER_WAIT → `_open_play()`

**Leader:**
1. Void setup: farba kde mám 1 kartu (non-heart, non-protected, non-trap) → F3-DUMP_SETUP
2. Escape (min) → F5-WAIT
3. Exhaust (min z exhaustable_suits) → F5-WAIT
4. Fallback: min(non_special)

**Follower:**
1. Escape (min) → F5-WAIT
2. Ak `not trick_has_penalty`:
   - Dump horník → F6-DUMP_SPECIAL
   - Dump trap → F8-DUMP_DANGEROUS
   - Dump high → F8-DUMP_DANGEROUS
3. Ak `trick_has_penalty`: min(lead) → F5-WAIT
4. Fallback: min(non_special)

---

## 11. Pomocné metódy

| Metóda | Kde | Čo robí |
|--------|-----|---------|
| `_is_trap(card, trick)` | CardSelector | Nikto vyšší v remaining+trick+vlastná ruka |
| `_special_is_safe_lead(card)` | CardSelector | Všetci vonku sú vyšší ako horník |
| `_special_points(card)` | CardSelector | Body za horníka (s/bez vysvietenia) |
| `_is_safe_heart(card)` | CardSelector | Najnižšia červeň v hre |
| `_is_last_escape_in_dangerous_suit(card)` | CardSelector | Posledná escape + ostanú trap + cudzí horník živý |
| `can_anyone_beat(card, players_after, trick_cards)` | AIMemory | Môže niekto po mne prebiť túto kartu |
| `will_someone_else_take(played, players_after)` | AIMemory | "yes"/"maybe" — či niekto iný vezme štich |
| `who_has_special(suit)` | AIMemory | Set hráčov ktorí môžu mať horníka |
| `is_special_gone(suit)` | AIMemory | Či horník už padol |

---

## 12. Log formát

```
[AI Počítač 1] F-SAFE | SAFE | F1-UNDERPLAY: podliezam: 7♣
               ^^^^^^   ^^^^   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
               situácia mode   stratégia + detail
```

**Bublina:** zobrazí sa ak `last_strategy in (RISK_TRAP, RISK_SPECIAL)`
