# tutorial/tutorial_steps.py

from game.card import Card
from config import SUITS, RANKS


def build_tutorial_hands() -> dict[int, list[Card]]:
    """
    Zostaví 4 pevné ruky (8 kariet každá) pre naskriptovanú ukážku kola.

    Toto NIE JE umelo poskladané rozdanie — sú to presné ruky zo skutočnej
    hry 4 AI hráčov (obtiažnosť "hard" pre všetkých) so seedom 679339
    (`tester_main.py --seed 679339`, prvý hráč na ťahu = Počítač 1/index 1).
    Priebeh všetkých 8 štichov v STEPS nižšie zodpovedá presne tomu, čo sa
    v tejto reálnej hre odohralo — vrátane toho, kto čo zahral a kto ktorý
    štich vyhral. Vďaka tomu ukážka pôsobí ako autentická partia, nie ako
    umelo nastavaný príklad.

    Jediné dve odchýlky od skutočného priebehu tejto hry:
    - Počítač 1 v skutočnej hre svojho zeleného horníka NEvysvietil. V
      tutoriáli ho vysvietiť necháme (naskriptované, nezávislé od toho, čo
      urobí hráč so svojím žaluďovým horníkom) — aby sa dalo naživo ukázať,
      čo znamená mať vysvietených OBOCH horníkov naraz (aj keby si hráč
      svojho nevysvietil, Počítač 1 svojho vysvietil aj tak).
    - Priebeh samotných štichov (kto čo hrá a kto vyhráva) je vždy rovnaký,
      no v jednom štichu (guľovom) má hráč skutočnú voľbu medzi dvomi
      kartami, ktoré na výsledok nemajú vplyv — pozri trick4 nižšie.
    """
    return {
        0: [  # Hráč (človek)
            Card("acorn", "under"),   # J♣
            Card("leaf", "eight"),    # 8♠
            Card("bell", "king"),     # K●
            Card("heart", "ten"),     # 10♥
            Card("leaf", "seven"),    # 7♠
            Card("acorn", "over"),    # Q♣ — žaluďový horník
            Card("acorn", "nine"),    # 9♣
            Card("bell", "eight"),    # 8●
        ],
        1: [  # Počítač 1
            Card("heart", "king"),    # K♥
            Card("leaf", "ten"),      # 10♠
            Card("acorn", "seven"),   # 7♣
            Card("leaf", "under"),    # J♠
            Card("bell", "over"),     # Q●
            Card("bell", "ace"),      # A●
            Card("heart", "seven"),   # 7♥
            Card("leaf", "over"),     # Q♠ — zelený horník
        ],
        2: [  # Počítač 2
            Card("heart", "over"),    # Q♥
            Card("bell", "nine"),     # 9●
            Card("acorn", "ten"),     # 10♣
            Card("heart", "under"),   # J♥
            Card("acorn", "ace"),     # A♣
            Card("bell", "ten"),      # 10●
            Card("acorn", "king"),    # K♣
            Card("leaf", "nine"),     # 9♠
        ],
        3: [  # Počítač 3
            Card("heart", "nine"),    # 9♥
            Card("acorn", "eight"),   # 8♣
            Card("heart", "eight"),   # 8♥
            Card("bell", "seven"),    # 7●
            Card("bell", "under"),    # J●
            Card("heart", "ace"),     # A♥
            Card("leaf", "king"),     # K♠
            Card("leaf", "ace"),      # A♠
        ],
    }


# Poradie krokov tutoriálu. "kind":
#   "text"       — len vysvetľujúci text, tlačidlo "Ďalej"
#   "penalty_overview" — úvodný prehľad trestných kariet ("cards": zoznam
#                  trojíc (Card, popis, body) — zámerne bez zmienky o
#                  vysvietení, to sa vysvetľuje až neskôr vo vlastnom
#                  kroku — vykreslený ako riadok obrázkov kariet), plus
#                  bežný "text"
#   "bullets"    — stručné body namiesto plynulého textu ("title" nadpis,
#                  "bullets" zoznam krátkych viet)
#   "phase_list" — prehľad priebehu kola s bodmi (aktuálny zvýraznený zlato),
#                  klik na "Ďalej" posunie na ďalší bod (prípadne spustí
#                  jeho "action", napr. rozdanie kariet)
#   "ai_play"    — počítač automaticky zahrá kartu pri vstupe do kroku
#   "human_play" — čaká kým hráč klikne na správnu kartu vo svojej ruke
#   "trick"      — celý štich naraz: "pre_human" sa zahrá automaticky pri
#                  vstupe do kroku (hráči na ťahu pred hráčom), potom čaká
#                  na klik na "human_card" (buď jedna konkrétna karta, alebo
#                  zoznam kariet — ak má hráč na výber viac rovnocenných
#                  možností), potom sa automaticky zahrá "post_human"
#                  (hráči na ťahu po hráčovi). Text sa mení z "text_before"
#                  na "text_after" (prípadne "text_after_by_card"/
#                  "text_after_fn", ak sa má text líšiť podľa toho, ktorú
#                  z viacerých kariet hráč zahral, resp. podľa iného stavu
#                  hry) až po odohraní hráčovej karty. Ďalší klik na
#                  "Ďalej" už priamo spustí zber štichu ("collect_trick") —
#                  žiadny samostatný "_collect" krok medzi jednotlivými
#                  štichmi neexistuje (výnimka: trick2, pozri
#                  "trick2_collect" nižšie — tam si zber vyžaduje vlastný
#                  krok, lebo panel KOLO môže ukázať pripísané body až PO
#                  dokončení animácie zberu).
#   "result"     — záverečné zhrnutie, tlačidlo "Dokončiť"
#
# Texty môžu obsahovať odstavce oddelené "\n\n" (dvojitým novým riadkom) —
# medzi nimi sa pri vykreslení vloží prázdny riadok (pozri
# tutorial_screen.py::_wrap_paragraphs), vďaka čomu dlhšie texty s viacerými
# udalosťami (napr. "Počítač 2 hrá...", "Počítač 3 hrá...") pôsobia
# prehľadnejšie než jeden súvislý blok.
STEPS = [
    {
        "kind": "penalty_overview",
        "text": (
            "CIEĽ HRY: Kto ako prvý prekročí 100 bodov, prehráva a stáva "
            "sa Chujom. Tvoj cieľ je preto jednoduchý: nazbierať čo "
            "najmenej bodov.\n\n"
            "Skôr než začneme, pozri sa, ktoré karty ti môžu "
            "priniesť trestné body — presne tým sa budeš chcieť v štichoch "
            "vyhýbať. Guľová farba nemá žiadne trestné karty. "
            "Len tie, ktoré vidíš na obrázku."
        ),
        "cards": [
            (Card("leaf", "over"), "Zelený horník", "8b"),
            (Card("acorn", "over"), "Žaluďový horník", "4b"),
            (Card("heart", "seven"), "Každá srdcová karta (×8)", "1b"),
        ],
    },
    {
        "kind": "bullets",
        "key": "ako_stich_funguje",
        "title": "AKO ŠTICH FUNGUJE",
        "bullets": [
            "Kto je prvý na rade, zahrá ľubovoľnú kartu — tá určí farbu štichu.",
            "Ostatní musia, ak môžu, priznať farbu (zahrať tú istú).",
            "Ak farbu nemáš, zahraj čokoľvek.",
            "Najvyššia karta v hranej farbe štich vyhráva.",
            "Karty zo štichu patria víťazovi a ten vedie ďalší štich.",
            "V prvom štichu kola sa nesmie viesť srdciami.",
            "Karty môžeš aj podliezať — zahrať nižšiu kartu tej istej farby, nie len vyššiu.",
        ],
    },
    {
        "kind": "phase_list",
        "phases": [
            {
                "key": "rozdanie",
                "label": "1. Rozdanie",
                "text": (
                    "Na začiatku každého kola dostane každý hráč 8 "
                    "kariet. Klikni na Ďalej a pozri sa, ako prebieha "
                    "rozdanie."
                ),
                "action": "deal",
            },
            {
                "key": "vysvietenie",
                "label": "2. Vysvietenie",
                "text": (
                    "Po rozdaní môže hráč, ktorý má zeleného alebo "
                    "žaluďového horníka, vysvietiť — teda ukázať ho "
                    "ostatným a zdvojnásobiť jeho hodnotu.\n\n"
                    "Ty máš žaluďového horníka (Q♣).\n\n"
                    "Počítač 1 má druhého, zeleného horníka (Q♠), a v "
                    "tejto hre sa ho rozhodol vysvietiť, čím stúpla "
                    "jeho hodnota z 8b na 16b."
                ),
                "instruction": "Klikni na svojho žaluďového horníka (Q♣).",
                "text_after": (
                    "Výborne! Vysvietil si žaluďového horníka (Q♣), "
                    "takže jeho hodnota stúpla zo 4 na 8 bodov.\n\n"
                    "A keďže Počítač 1 vysvietil svojho horníka tiež, sú "
                    "teraz vysvietení obaja horníci. To znamená, že aj "
                    "srdcia budú v tomto kole za 2 body namiesto 1."
                ),
                "instruction_after": (
                    "Opätovným kliknutím na horníka môžeš vysvietenie "
                    "ešte zrušiť, alebo pokračuj tlačidlom Ďalej."
                ),
                "action": "illuminate",
            },
            {
                "key": "zavazok",
                "label": "3. Záväzok",
                "text": (
                    "Pred prvým štichom sa hráči môžu zaviazať k "
                    "„Beriem všetko“ alebo „Nechytím nič“ — obe voľby "
                    "prinášajú riziko aj odmenu. Záväzky si ešte vysvetlíme neskôr.\n\n"
                    "Tlačidlá dole sú teraz aktívne a môžeš si ich "
                    "vyskúšať, v tomto tutoriáli však priebeh neovplyvnia.\n\n"
                    "Tlačidlom OK by si v ostrej hre naraz potvrdil aj "
                    "vysvietenie z predošlého kroku aj prípadný záväzok. "
                    "Hráme bez záväzku."
                ),
                "instruction": "Pokračuj kliknutím na tlačidlo OK.",
                "action": None,
            },
        ],
    },
    {
        "kind": "trick",
        "key": "trick1",
        "pre_human": [
            (1, Card("acorn", "seven")),
            (2, Card("acorn", "ten")),
            (3, Card("acorn", "eight")),
        ],
        "human_card": Card("acorn", "under"),
        "post_human": [],
        "text_before": (
            "Toto je jadro kola — postupne odohráme všetkých 8 štichov a "
            "popritom si ukážeme aj ďalšie dôležité finty.\n\n"
            "Počítač 1 začína prvý štich žaluďovou sedmičkou (7♣). Tá "
            "určuje farbu štichu a ostatní ju musia, ak môžu, priznať.\n\n"
            "Počítač 2 zahral žaluďovú desiatku (10♣) a Počítač 3 "
            "žaluďovú osmičku (8♣).\n\n"
            "Ty máš tri žalude — musíš priznať farbu."
        ),
        "text_after": (
            "Tvoj žaluďový dolník (J♣) je napokon najvyššia zahraná "
            "žaluďová karta, takže štich berieš ty.\n\n"
            "A keďže v štichu neboli žiadne body, táto výhra ťa nič "
            "nestojí. Keďže si štich vyhral, v ďalšom ideš na rade ako "
            "prvý ty."
        ),
        "human_instruction": "Klikni na svojho žaluďového dolníka (J♣) a zahraj ho.",
    },
    {
        "kind": "text",
        "key": "trick2_last_trick_prompt",
        "text": (
            "Dôležitým aspektom hry je sledovanie a počítanie kariet. "
            "Skôr než zahráš ďalšiu kartu, poďme si spočítať, koľko a "
            "aké žalude už padli."
        ),
        "instruction": (
            "Klikni na tlačidlo Posledný štich vpravo dole a pozri si, "
            "čo sa práve odohralo."
        ),
        "requires_last_trick_view": True,
    },
    {
        "kind": "trick",
        "key": "trick2",
        "pre_human": [],
        "human_card": Card("acorn", "over"),
        "post_human": [
            (1, Card("leaf", "over")),
            (2, Card("acorn", "king")),
            (3, Card("leaf", "ace")),
        ],
        "text_before": (
            "Žalude, ktoré už padli: sedmička (7♣), desiatka (10♣), "
            "osmička (8♣) a tvoj dolník (J♣) — štyri z ôsmich.\n\n"
            "Okrem tvojho horníka (Q♣) a deviatky (9♣) tak v hre "
            "zostávajú už len eso (A♣) a kráľ (K♣), obe vyššie než tvoj "
            "horník. Ak teraz zahráš svojho horníka, súperi musia priznať "
            "farbu, a tvojho horníka prebiť esom či kráľom.\n\n"
            "A presne o tom je CHUJ: počítať karty a nájsť správny "
            "okamih, keď sa nebezpečnej karty zbavíš čo najbezpečnejšie."
        ),
        # Body ("Všimni si panel KOLO...") sa spomínajú až v samostatnom
        # kroku "trick2_collect" nižšie — v momente, keď hráč zahrá
        # kartu, ešte nebežala ani animácia zberu štichu, takže panel by
        # ukazoval staré (nezmenené) skóre.
        "text_after": (
            "Počítač 1 už nemá žiadny žaluď, takže túto situáciu "
            "využíva na to, aby sa zbavil nebezpečnej karty — svojho "
            "vysvieteného zeleného horníka (Q♠) za 16 bodov.\n\n"
            "Počítač 3 tiež nemá žaluď a odhadzuje listovým esom (A♠).\n\n"
            "Počítač 2 musí priznať farbu a má už len eso (A♣) a kráľa "
            "(K♣). Nech zahrá ktorúkoľvek z nich, tvojho horníka "
            "prebije — a práve Počítač 2 tak schytá poriadnu dávku "
            "bodov. Presne podľa výpočtu!"
        ),
        "human_instruction": "Klikni na svojho žaluďového horníka (Q♣) a veď ním.",
    },
    {
        # Samostatný krok (nie zlúčený do trick2) — panel KOLO smie
        # ukázať pripísané body až TERAZ, po doletení kariet k víťazovi
        # (_finish_trick_collect ich pripíše skôr, než sa vstúpi do
        # tohto kroku — pozri _enter_step v tutorial_screen.py).
        "kind": "text",
        "key": "trick2_collect",
        "text": (
            "Všimni si panel KOLO vpravo dole: pribudli mu tam prvé "
            "trestné body, tie inkasuje víťaz štichu za bodované karty."
        ),
    },
    {
        "kind": "trick",
        "key": "trick3",
        "pre_human": [
            (2, Card("leaf", "nine")),
            (3, Card("leaf", "king")),
        ],
        "human_card": [Card("leaf", "eight"), Card("leaf", "seven")],
        "post_human": [
            (1, Card("leaf", "under")),
        ],
        "text_before": (
            "Počítač 2 vyhral predošlý štich, takže vedie znova — "
            "tentoraz listami, deviatkou (9♠).\n\n"
            "Počítač 3 priznáva kráľom (K♠).\n\n"
            "Ty máš ešte dve listové karty — priznaj farbu."
        ),
        "text_after": (
            "Počítač 1 priznáva farbu dolníkom (J♠), ale na kráľa (K♠) "
            "Počítača 3 to nestačí. Štich teda berie Počítač 3 a vedie "
            "ďalej.\n\n"
            "Zeleného horníka sme už videli v minulom štichu, takže "
            "tentoraz v štichu nie sú žiadne body."
        ),
        "human_instruction": (
            "Zahraj jednu zo svojich listových kariet — osmičku (8♠) "
            "alebo sedmičku (7♠). Obe voľby sú v poriadku."
        ),
    },
    {
        "kind": "trick",
        "key": "trick4",
        "pre_human": [
            (3, Card("bell", "under")),
        ],
        "human_card": [Card("bell", "king"), Card("bell", "eight")],
        "post_human": [
            (1, Card("bell", "ace")),
            (2, Card("bell", "ten")),
        ],
        "text_before": (
            "Počítač 3 vyhral predošlý štich a začína — dolníkom (J●).\n\n"
            "V guľových kartách sa nenachádza žiadna bodovaná karta, no "
            "keby niekto nemal gule, mohol by do štichu odhodiť "
            "bodovanú kartu — a tú by si zobral ten, kto štich vyhrá. "
            "Zahranie vysokej karty preto vždy nesie isté riziko. Čím "
            "viac kariet danej farby už išlo, tým vyššie riziko."
        ),
        "text_after": (
            "Riskol si vyššiu kartu.\n\n"
            "Počítač 1 aj tak berie štich svojím esom (A●) — "
            "najvyššou možnou guľovou kartou, ktorú nikto neprebije. "
            "Aj tento štich ostáva bez bodov — vedie ďalej "
            "Počítač 1."
        ),
        "text_after_by_card": {
            ("bell", "king"): (
                "Zahral si vyššiu kartu, ale nič tým nepokazíš.\n\n"
                "Počítač 1 aj tak berie štich svojím esom (A●) — "
                "najvyššou možnou guľovou kartou, ktorú nikto neprebije. "
                "Aj tento štich tak ostáva bez bodov — vedie ďalej "
                "Počítač 1."
            ),
            ("bell", "eight"): (
                "Podliezol si osmičkou — a tým nič neriskuješ.\n\n"
                "Počítač 1 berie štich svojím esom (A●), "
                "najvyššou možnou guľovou kartou, ktorú nikto neprebije. "
                "Aj tento štich ostáva bez bodov — vedie ďalej "
                "Počítač 1."
            ),
        },
        "human_instruction": (
            "Podlezieš osmičkou (8●), alebo riskneš aj vyššieho kráľa (K●)?"
        ),
    },
    {
        "kind": "trick",
        "key": "trick5",
        "pre_human": [
            (1, Card("heart", "seven")),
            (2, Card("heart", "over")),
            (3, Card("heart", "nine")),
        ],
        "human_card": Card("heart", "ten"),
        "post_human": [],
        "text_before": (
            "Počítač 1 vyhral predošlý štich a vedie ďalej — tentoraz "
            "srdcovou sedmičkou (7♥).\n\n"
            "Počítač 2 aj Počítač 3 priznávajú srdcia.\n\n"
            "Tebe ostala už len jedna srdcová karta, takže ju musíš "
            "zahrať."
        ),
        "text_after_fn": lambda screen: (
            (
                "Počítač 2 zahral najvyššiu srdcovú kartu v štichu — "
                "srdcového horníka (Q♥) — a štich berie.\n\n"
                "Vysvietení sú obaja horníci, takže srdcia sú teraz za "
                "2 body — tento štich je za 8 bodov. Počítač 2 si tak "
                "pripisuje všetky štyri srdcia zo štichu."
            ) if (
                screen.players[1].illuminated_leaf
                and Card("acorn", "over") in screen.illuminated_cards
            ) else (
                "Počítač 2 zahral najvyššiu srdcovú kartu v štichu — "
                "srdcového horníka (Q♥) — a štich berie.\n\n"
                "Srdcia sú za 1 bod, takže tento štich je za 4 "
                "body, ktoré si pripíše Počítač 2."
            )
        ),
        "human_instruction": "Klikni na svoje srdce (10♥) a zahraj ho.",
    },
    {
        "kind": "trick",
        "key": "trick6",
        "pre_human": [
            (2, Card("bell", "nine")),
            (3, Card("bell", "seven")),
        ],
        "human_card": [Card("bell", "king"), Card("bell", "eight")],
        "post_human": [
            (1, Card("bell", "over")),
        ],
        "text_before": (
            "Počítač 2 znova začína — deviatkou (9●).\n\n"
            "Počítač 3 priznáva sedmičkou (7●).\n\n"
            "Tebe ostala už len jedna guľová karta. Zahraj ju."
        ),
        # Ktorú z dvoch kariet si nechal na trick6, závisí od toho, ktorú
        # si zahral pri trick4 (presný opak) — a od toho zase závisí, kto
        # štich vyhráva a teda kto vedie ďalej (pozri BRANCH_B_STEPS
        # nižšie). Oboje preto rieši jedna dynamická funkcia namiesto
        # samostatného "_collect" kroku.
        "text_after_fn": lambda screen: (
            (
                "Tentoraz štich berieš TY — tvoj kráľ (K●) je v "
                "guliach vyššia karta než horník Počítača 1 (Q●).\n\n"
                "Opäť žiadne trestné karty v štichu. Odteraz vedieš ty."
            ) if screen.trick_human_played_card == Card("bell", "king") else (
                "Počítač 1 berie svojím horníkom (Q●) a štich je znova "
                "bez bodov.\n\n"
                "Počítač 1 začína ďalší štich."
            )
        ),
        "human_instruction": "Zahraj svoju poslednú guľovú kartu.",
    },
    {
        "kind": "trick",
        "key": "trick7",
        "pre_human": [
            (1, Card("heart", "king")),
            (2, Card("heart", "under")),
            (3, Card("heart", "eight")),
        ],
        "human_card": [
            Card("acorn", "nine"), Card("leaf", "eight"), Card("leaf", "seven")
        ],
        "post_human": [],
        "text_before": (
            "Ty už srdce nemáš, takže si bez farby — môžeš zahrať "
            "ktorúkoľvek zo svojich dvoch zvyšných kariet, poradie "
            "nehrá žiadnu rolu."
        ),
        "text_after": (
            "Počítač 1 zahral najvyššiu srdcovú kartu a štich opäť získava.\n\n"
            "Na konto mu pribúdajú ďalšie trestné karty."
        ),
        "human_instruction": "Zahraj ktorúkoľvek zo svojich zvyšných kariet.",
    },
    {
        "kind": "trick",
        "key": "trick8",
        "pre_human": [
            (1, Card("leaf", "ten")),
            (2, Card("acorn", "ace")),
            (3, Card("heart", "ace")),
        ],
        "human_card": [
            Card("leaf", "eight"), Card("leaf", "seven"), Card("acorn", "nine")
        ],
        "post_human": [],
        "text_before": (
            "Posledný štich kola — každému ostáva už len jedna karta.\n\n"
            "Počítač 1 vedie listovou desiatkou (10♠).\n\n"
            "Počítač 2 aj Počítač 3 odhadzujú svoje posledné karty.\n\n"
            "Zahraj aj ty svoju poslednú kartu."
        ),
        "text_after": (
            "Počítač 1 berie posledný štich svojou desiatkou (10♠) — "
            "najvyššou listovou kartou v štichu.\n\n"
            "Počítač 2 aj Počítač 3 odhodili svoje esá — žaluďové (A♣) "
            "a srdcové (A♥) — no ani jedno nie je v hranej (listovej) "
            "farbe, takže štich vyhráva (10♠).\n\n"
            "Kolo je odohrané — všetci hráči minuli svoje karty."
        ),
        "human_instruction": "Zahraj svoju poslednú kartu.",
        "round_end": True,
    },
    {
        "kind": "text",
        "key": "chujogram_wait",
        "text": (
            "5. BODOVANIE: Po odohraní všetkých 8 štichov sa trestné "
            "body spočítajú a zapíšu do CHUJOGRAMU — tabuľky s históriou "
            "celej hry."
        ),
        "instruction": (
            "Vpravo dole sa práve objavila jeho ikonka — klikni na ňu a "
            "pozri si tabuľku."
        ),
    },
    {
        "kind": "text",
        "key": "chujogram_explain",
        # Vedome NEspomíname guličky, históriu odohraných kôl, ani sériový
        # bonus za čisté kolá — všetko to spolu súvisí (bonus dáva zmysel
        # len s pochopením histórie/série) a chceme to vysvetliť spolu, až
        # neskôr (plánovaná krátka precvičovacia hra hneď po tutoriáli).
        # Bonus preto v tomto tutoriáli ani nespúšťame (pozri __init__,
        # no_penalty_streak) — text sa drží len toho, čo hráč práve videl.
        "text": (
            "Toto je Chujogram — tu sa priebežne zapisuje skóre všetkých "
            "hráčov.\n\n"
            "Všimni si posledný stĺpec: v tomto kole si nezískal ani "
            "jeden trestný bod — presne to je cieľom každého kola CHUJ-u."
        ),
    },
    {
        "kind": "result",
        "text": (
            "Takto vyzerá celé kolo CHUJ-u — od rozdania až po "
            "bodovanie.\n\n"
            "V skutočnej hre sa pokračuje ďalšími kolami, kým niekto "
            "neprekročí 100 bodov a nestane sa Chujom. Týmto sa "
            "tutoriál končí."
        ),
    },
]


# ---------------------------------------------------------------------
# Alternatívna vetva pre trick7/trick8, POUŽITÁ LEN vtedy, keď hráč pri
# trick6 zahral guľového kráľa a teda prebil horníka Počítača 1 (pozri
# "text_after_fn" pri trick6 vyššie). V takom prípade vedie ďalší (7.)
# štich hráč, nie Počítač 1 — takže aj jeho priebeh (kto čo hrá, kto
# vyhráva) je iný než v autentickom priebehu tejto hry. Mechanicky ide o
# platný priebeh: karty, ktoré ostatným hráčom zostávajú do konca kola, sú
# v OBOCH vetvách úplne rovnaké (líši sa len to, v ktorom z posledných
# dvoch štichov ktorú z nich zahrajú) — len tu už nejde o doslovnú repliku
# skutočnej partie so seedom 679339, ale o mechanicky správne dohratie tej
# istej pozície.
#
# V trick7 tu hráč (na rozdiel od všetkých ostatných "voľných" volieb v
# tutoriáli) skutočne VEDIE štich — ktorou farbou zahrá, preto priamo
# rozhoduje, kto štich vyhrá:
#   - vedie listom  -> vyhráva Počítač 1 (má ešte listovú desiatku 10♠)
#   - vedie žaluďom (9♣) -> jediný, kto ešte žaluď má, je Počítač 2 (eso
#     A♣), a musí ho priznať -> vyhráva on namiesto Počítača 1
# Kto teda povedie posledný (8.) štich, závisí od tejto voľby — preto má
# trick8 dve varianty, "trick8_p1" (vedie Počítač 1) a "trick8_p2" (vedie
# Počítač 2), medzi ktorými sa vyberá dynamicky podľa toho, kto trick7
# naozaj vyhral (pozri tutorial_screen.py, self.branch_b_trick7_winner a
# _current_step()).
BRANCH_B_STEPS = {
    "trick7": {
        "kind": "trick",
        "key": "trick7",
        "pre_human": [],
        "human_card": [
            Card("leaf", "eight"), Card("leaf", "seven"), Card("acorn", "nine")
        ],
        # Tento zoznam automatických ťahov platí rovnako pre OBE možné
        # voľby hráča — kto štich naozaj vyhrá, dopočíta samotný herný
        # engine (get_winner_index) podľa toho, ktorú farbu hráč viedol.
        "post_human": [
            (1, Card("leaf", "ten")),
            (2, Card("acorn", "ace")),
            (3, Card("heart", "eight")),
        ],
        "text_before": (
            "Tento štich si vyhral ty, takže teraz vedieš sám — a máš "
            "na výber. Ostali ti už len dve karty: posledná listová a "
            "žaluďová deviatka (9♣).\n\n"
            "Farba, ktorou povedieš, rozhodne, kto štich vyhrá aj kto "
            "potom povedie posledný štich kola. Vyskúšaj si to."
        ),
        "text_after_fn": lambda screen: (
            (
                "Počítač 1 má vyššiu listovú kartu — desiatku (10♠) — a "
                "preto štich berie.\n\n"
                "Počítač 2 ani Počítač 3 už listy nemajú, takže "
                "odhadzujú.\n\n"
                "Počítač 3 pritom odhodil aj srdcovú osmičku (8♥), "
                "ktorá má svoju hodnotu. Teraz patrí k výhre Počítača "
                "1. Počítač 1 si spolu so štichom pripisuje aj jedno "
                "srdce."
            ) if screen.trick_human_played_card.suit == "leaf" else (
                "Viedol si žaluďom — a jediný, kto ešte žaluď má, je "
                "Počítač 2 so svojím esom (A♣). Musí ho priznať, takže "
                "štich preberá on namiesto Počítača 1.\n\n"
                "Počítač 1 nemá žiaden žaluď, a tak odhadzuje bezcennú "
                "listovú desiatku (10♠). Počítač 3 tiež žaluď nemá a "
                "odhadzuje bodovanú srdcovú osmičku (8♥) —"
                "pripadne Počítaču 2"
            )
        ),
        "human_instruction": (
            "Vyber si, akou kartou povedieš štich — zvyšnou listovou (7♠), "
            "alebo žaluďovou deviatkou (9♣)."
        ),
    },
    # Vedie Počítač 1 (hráč pri trick7 viedol listom).
    "trick8_p1": {
        "kind": "trick",
        "key": "trick8",
        "pre_human": [
            (1, Card("heart", "king")),
            (2, Card("heart", "under")),
            (3, Card("heart", "ace")),
        ],
        "human_card": Card("acorn", "nine"),
        "post_human": [],
        "text_before": (
            "Posledný štich kola — každému ostáva už len jedna karta.\n\n"
            "Počítač 1 vedie srdcovým kráľom (K♥) a Počítač 2 aj "
            "Počítač 3 priznávajú srdcia.\n\n"
            "Ty už žiadne srdce nemáš, takže sa zbav poslednej žaluďovej "
            "karty, ktorá ti ostala."
        ),
        "text_after": (
            "Počítač 3 zahral najvyššie srdce — eso (A♥) — a preto "
            "štich berie. Spolu s ním získava aj všetky tri srdcia, "
            "ktoré v štichu padli.\n\n"
            "Tvoja žaluďová deviatka (9♣) nemá žiadnu hodnotu, takže na "
            "bodovanie nemala vplyv.\n\n"
            "Kolo je odohrané — všetci hráči minuli svoje karty."
        ),
        "human_instruction": "Zahraj svoju poslednú kartu — žaluďovú deviatku (9♣).",
        "round_end": True,
    },
    # Vedie Počítač 2 (hráč pri trick7 viedol žaluďom).
    "trick8_p2": {
        "kind": "trick",
        "key": "trick8",
        "pre_human": [
            (2, Card("heart", "under")),
            (3, Card("heart", "ace")),
        ],
        "human_card": [Card("leaf", "eight"), Card("leaf", "seven")],
        "post_human": [
            (1, Card("heart", "king")),
        ],
        "text_before": (
            "Posledný štich kola — každému ostáva už len jedna karta.\n\n"
            "Počítač 2 vedie srdcovým dolníkom (J♥) a Počítač 3 hneď "
            "priznáva najvyššou možnou kartou — esom (A♥).\n\n"
            "Ty žiadne srdce nemáš, takže sa zbav svojej poslednej karty."
        ),
        "text_after": (
            "Počítač 3 zahral najvyššie srdce — eso (A♥) — a preto "
            "štich berie. Spolu s ním získava aj všetky tri srdcia, "
            "ktoré v štichu padli — priznať farbu musel aj Počítač 1, "
            "ktorý dohral svojím kráľom (K♥).\n\n"
            "Tvoja karta nemá žiadnu hodnotu, takže na bodovanie nemala "
            "vplyv.\n\n"
            "Kolo je odohrané — všetci hráči minuli svoje karty."
        ),
        "human_instruction": "Zahraj svoju poslednú kartu.",
        "round_end": True,
    },
}
