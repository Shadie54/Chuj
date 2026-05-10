# Pravidlá hry CHUJ

## Základné info
- 4 hráči: 1 človek + 3 AI
- 32 kariet: 4 farby × 8 rankov
- Hrá sa proti smeru hodinových ručičiek
- Poradie hráčov: 0 = Hráč (dole), 1 = Počítač 1 (vpravo), 2 = Počítač 2 (hore), 3 = Počítač 3 (vľavo)

## Farby a ranky
SUITS = ["heart", "bell", "leaf", "acorn"]
RANKS = ["ace", "king", "over", "under", "ten", "nine", "eight", "seven"]
Symboly: heart=♥  bell=●  leaf=♠  acorn=♣
- rank_order: ace=7 (najvyšší) → seven=0 (najnižší)
- Špeciálne karty: leaf-over (Q♠) = zelený horník, acorn-over (Q♣) = žaluďový horník

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
| Všetky červené (heart) | 1b každá | 2b každá (ak obaja horníci vysvietení) |
| Zelený horník (Q♠) | 8b | 16b |
| Žaluďový horník (Q♣) | 4b | 8b |
| Ostatné karty | 0b | 0b |
- Max 20b za kolo (bez vysvietenia)
- Max 40b za kolo (obaja vysvietení)

## Vysvietenie
- Pred prvým štichom možno uznať jedného alebo oboch horníkov
- Vysvietený horník je viditeľný (otočená karta lícom v ruke)
- Vysvietený horník = dvojnásobok bodov
- Ak sú obaja vysvietení → červené = 2b namiesto 1b

## Záväzky
### Beriem všetko (declaration = "all")
- Hráč musí vyhrať všetkých 8 štichov
- Splnený: −20b pre deklaranta, ostatní 0b
- Nesplnený: +20b pre deklaranta, ostatní 0b

### Nechytím nič (declaration = "none")
- Hráč nesmie chytiť žiadny štich
- Splnený: −10b pre deklaranta, ostatní 0b
- Nesplnený: deklarant 0b, ostatní −10b každý
- Kolo sa ukončí okamžite po štichu kde deklarant prvýkrát chytí štich

## Špeciálne pravidlá
- Sweep: chytíš všetky trestné karty v kole → −10b (ostatní 0b)
- Séria: 5 kôl za sebou bez trestného bodu → −10b bonus
- Reset: presne 100b → skóre sa resetuje na 90b
- 90b pravidlo: nad 90b sa horníci nepočítajú (0b)
- Prehra: prekročenie 100b → hráč je "Chuj"

## Terminológia
- Horník = špeciálna karta (leaf-over alebo acorn-over)
- Podliezanie = zahrať nižšiu kartu tej istej farby
- Void = nemáš danú farbu
- Trap karta = najvyššia ostávajúca karta farby (zoberie štich)
- Escape karta = karta s coverage (niekto vyšší vonku) — môže podliezť ale nie je garantované
- Safe karta = garantovane bezpečná (všetky cudzie karty v danej farbe sú vyššie)
- Coverage = karty vyššie ako moja karta ktoré sú ešte v hre
- Štich = jeden round kde každý zahráva 1 kartu
- Sweep = chytenie všetkých trestných kariet jedným hráčom