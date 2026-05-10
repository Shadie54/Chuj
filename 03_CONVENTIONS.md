# Konvencie projektu CHUJ

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

## Tester
- Spúšťa sa z koreňa projektu: `python tester_main.py`
- Random scenár: AI sami rozhodnú o vysvietení cez `decide_illumination()`
- Override vysvietenia a first playera cez setup bar (klik = okamžitý reset)
- Seed z hry → `python tester_main.py --seed 487123` = identické rozdanie

## Projekt je "vibe coding"
- Vysvetli nuansy ak si niečo neistý
- Pre triviálne zmeny (typo, jasný bug) urob priamo bez pýtania
- Pre architektúrne zmeny počkaj na potvrdenie
- Pri návrhu: najprv koncept so súhlasom, potom implementácia