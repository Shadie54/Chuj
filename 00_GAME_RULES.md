# Pravidlá hry CHUJ

## Základné info
- 4 hráči: 1 človek + 3 AI
- 32 kariet: 4 farby × 8 rankov
- Hrá sa proti smeru hodinových ručičiek
- Poradie: 0 = Hráč (dole), 1 = Počítač 1 (vľavo), 2 = Počítač 2 (hore), 3 = Počítač 3 (vpravo)

## Karty
```
SUITS = ["heart", "bell", "leaf", "acorn"]
RANKS = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]
Symboly: heart=♥  bell=●  leaf=♠  acorn=♣
rank_order: ace=7 (najvyšší) → seven=0 (najnižší)
Špeciálne: leaf-over (Q♠) = zelený horník, acorn-over (Q♣) = žaluďový horník
```

## Priebeh kola
1. Rozdanie — každý dostane 8 kariet (4+4)
2. Vysvietenie — možnosť priznať horníka/ov
3. Záväzok — možnosť vyhlásiť Beriem všetko / Nechytím nič
4. 8 štichov
5. Bodovanie

## Pravidlá štichov
- Leader zahrá ľubovoľnú kartu → určí farbu štichu
- Ostatní MUSIA priznať farbu (zahrať kartu rovnakej farby)
- Ak nemáš danú farbu → zahraj čokoľvek (void)
- Najvyššia karta v hranej farbe vyhráva štich
- V prvom štichu sa nesmie viesť červeň (heart)
- Karty sa môžu podliezať (zahrať ľubovoľnú nižšiu kartu tej istej farby)
- Víťaz štichu začína nasledujúci štich

## Bodovanie kariet
| Karta | Základná hodnota | Vysvietená |
|-------|-----------------|------------|
| Všetky heart | 1b každá | 2b každá (ak obaja horníci vysvietení) |
| Q♠ (zelený horník) | 8b | 16b |
| Q♣ (žaluďový horník) | 4b | 8b |
| Ostatné | 0b | 0b |

Max 20b za kolo (bez vysvietenia), max 40b (obaja vysvietení).

## Vysvietenie
- Pred prvým štichom možno uznať jedného alebo oboch horníkov
- Vysvietený horník = dvojnásobok bodov
- Ak sú obaja vysvietení → heart = 2b namiesto 1b

## Záväzky
**Beriem všetko (declaration = "all")**
- Splnený (všetkých 8 štichov): −20b pre deklaranta, ostatní 0b
- Nesplnený: +20b pre deklaranta, ostatní 0b

**Nechytím nič (declaration = "none")**
- Splnený (0 štichov): −10b pre deklaranta, ostatní 0b
- Nesplnený: +10b pre deklaranta (`DECLARATION_FAIL_PENALTY`), ostatní 0b
- Kolo sa ukončí okamžite po štichu kde deklarant prvýkrát chytí štich

## Špeciálne pravidlá
- **Sweep**: chytíš všetky trestné karty v kole → −10b (ostatní 0b) — `SHOOT_MOON_BONUS`
- **Séria**: 5 kôl za sebou bez trestného bodu → −10b bonus (`NO_PENALTY_STREAK=5`, `NO_PENALTY_BONUS=-10`)
- **Reset**: presne 100b → skóre sa resetuje na 90b (`WINNING_SCORE=100`, `RESET_SCORE=90`)
- **90b pravidlo**: `HIGH_SCORE_THRESHOLD=90` — nad 90b sa horníci nepočítajú (0b pre deklaranta)
- **Prehra**: prekročenie 100b → hráč je "Chuj"

## Streak logika (`player.update_streak`)
- Prerušenie: `actual_points > 0`
- Pokračovanie: `actual_points == 0` — sweep bonus, splnený záväzok nepreruší streak
- `no_penalty_streak` štartuje na `-1` (prvé kolo sa nezapočíta ako séria)
