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
#   "trick_demo" — úplne prvý krok: privítanie + "čo je štich" na
#                  najjednoduchšej možnej úrovni, bez rúk/mien hráčov.
#                  Ako "text" (obyčajný "text" + "title", tlačidlo "Ďalej"),
#                  navyše sa pod/vedľa panelu v slučke prehráva animácia
#                  4 kariet, ktoré sa postupne objavia v strede stola a po
#                  chvíli spolu zmiznú (vykresľuje
#                  TutorialDirector._draw_trick_demo()).
#   "penalty_overview" — úvodný prehľad trestných kariet, vycentrovaný
#                  rovnako ako "trick_demo" (pozri
#                  TutorialDirector._draw_centered_penalty_overview).
#                  "cards": zoznam dvojíc (Card, popis, body) pre zeleného
#                  a žaluďového horníka, každý ako samostatná karta.
#                  "hearts"/"hearts_label"/"hearts_points": všetkých 8
#                  sŕdc ako jeden mierne prekrytý vejár so spoločným
#                  popisom a bodmi pod ním. Zámerne bez zmienky o
#                  vysvietení, to sa vysvetľuje až neskôr vo vlastnom
#                  kroku. Plus bežný "text".
#   "bullets"    — stručné body namiesto plynulého textu ("title" nadpis,
#                  "bullets" zoznam krátkych viet)
#   "phase_list" — prehľad priebehu kola s bodmi (aktuálny zvýraznený zlato),
#                  klik na "Ďalej" posunie na ďalší bod (prípadne spustí
#                  jeho "action", napr. rozdanie kariet). Bod "rozdanie" má
#                  navyše "bullets_after" — "ako štich funguje", zobrazí sa
#                  v TOM ISTOM bode hneď po doletení kariet, tlačidlo
#                  "Ďalej" až potom posunie na "Vysvietenie" (pozri
#                  TutorialDirector.panel_content()/handle_click()).
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
# gui/lesson_panel.py::wrap_paragraphs), vďaka čomu dlhšie texty s viacerými
# udalosťami (napr. "Počítač 2 hrá...", "Počítač 3 hrá...") pôsobia
# prehľadnejšie než jeden súvislý blok.
STEPS = [
    {
        "kind": "trick_demo",
        "key": "intro_trick_demo",
        "title": "VITAJ V HRE CHUJ!",
        "text": (
            "Chuj je štichová kartová hra pre 4 hráčov so sedmovými "
            "kartami. Počas hry sa snažíš vyhnúť trestným kartám – "
            "srdciam, zelenému horníkovi a žaluďovému horníkovi – a "
            "nazbierať čo najmenej bodov. Kto ako prvý prekročí 100 "
            "bodov, prehráva a stáva sa Chujom.\n\n"
            "Čo je štich?\n\n"
            "V každom štichu zahrá každý zo štyroch hráčov jednu kartu. "
            "Hráč, ktorý štich vyhrá, zoberie všetky štyri zahrané karty."
        ),
    },
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
        ],
        # Všetkých 8 sŕdc, od esa zostupne (RANKS je už v tomto poradí) —
        # vykreslia sa ako mierne prekrytý vejár (pozri
        # TutorialDirector._draw_penalty_cards_row), nie len jedna karta
        # ako zástupca.
        "hearts": [Card("heart", rank) for rank in RANKS],
        "hearts_label": "Každá srdcová karta (×8)",
        "hearts_points": "1b",
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
                # Po rozdaní (karty už doleteli) sa v TOMTO ISTOM bode
                # "Rozdanie" namiesto textu vyššie zobrazí toto — bez
                # nového riadku v prehľade hore a bez samostatného kroku
                # (pozri TutorialDirector.panel_content()/handle_click()).
                # Skupiny [3, 2, 2] — "" medzi nimi vloží prázdny riadok
                # bez odrážky (pozri LessonPanel.wrap_bullets).
                "bullets_after": [
                    "Hráč, ktorý začína štich, zahrá ľubovoľnú kartu. Tá určí farbu štichu.",
                    "Ostatní musia priznať farbu – zahrať kartu rovnakej farby.",
                    "Ak túto farbu nemáš, môžeš zahrať čokoľvek.",
                    "",
                    "Štich vyhráva najvyššia karta vo farbe, ktorou sa začínalo.",
                    "Víťaz zoberie všetky štyri karty a začína ďalší štich.",
                    "",
                    "V prvom štichu sa nesmie začínať srdcovou kartou.",
                    "Nemusíš zahrať vyššiu kartu – môžeš aj podliezť (zahrať nižšiu kartu rovnakej farby).",
                ],
            },
            {
                "key": "vysvietenie",
                "label": "2. Vysvietenie",
                "text": (
                    "Pred prvým štichom môžeš zeleného alebo žaluďového "
                    "horníka vysvietiť, ak ho máš v ruke. Tým ho ukážeš "
                    "ostatným hráčom a zdvojnásobíš jeho bodovú "
                    "hodnotu.\n\n"
                    "Počítač 1 už vysvietil zeleného horníka (Q♠), čím "
                    "zvýšil jeho hodnotu z 8 na 16 bodov. Ty máš "
                    "žaluďového horníka (Q♣) a môžeš sa rozhodnúť, či "
                    "ho vysvietiš tiež."
                ),
                "instruction": "Klikni na svojho žaluďového horníka (Q♣).",
                "text_after": (
                    "Vysvietil si žaluďového horníka! Keď sú vysvietení "
                    "obaja horníci, zdvojnásobí sa aj hodnota sŕdc. "
                    "Inak zostávajú za 1 bod.\n\n"
                    "Teraz platí:\n"
                    "* Zelený horník: 8 → 16 b\n"
                    "* Žaluďový horník: 4 → 8 b\n"
                    "* Každé srdce: 1 → 2 b"
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
                    "Pred prvým štichom si môžeš zvoliť záväzok "
                    "„Beriem všetko“ alebo „Nechytím nič“. Vybrať "
                    "môžeš len jeden; opätovným kliknutím ho zrušíš. "
                    "Pravidlá záväzkov si vysvetlíme neskôr.\n\n"
                    "V tomto tutoriáli hráme bez záväzku – jeho výber "
                    "priebeh hry neovplyvní.\n\n"
                    "Tlačidlom OK definitívne potvrdíš vysvietenie aj "
                    "prípadný záväzok. Potom už svoje voľby nemôžeš "
                    "zmeniť."
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
            "Počítač 1 začal žaluďovou sedmičkou (7♣), čím určil farbu "
            "štichu. Ostatní hráči priznali žalude.\n\n"
            "Teraz si na rade ty. Keďže máš žalude aj v ruke, musíš "
            "priznať farbu."
        ),
        "text_after": (
            "Tvoj dolník (J♣) je najvyššia karta v štichu, takže "
            "všetky štyri karty berieš ty.\n\n"
            "V štichu nie sú žiadne trestné body. Keďže si vyhral, "
            "ďalší štich začínaš ty."
        ),
        "human_instruction": "Zahraj žaluďového dolníka (J♣).",
    },
    {
        "kind": "text",
        "key": "trick2_last_trick_prompt",
        "text": (
            "Sledovať, ktoré karty už padli a ktoré sú ešte v hre, je "
            "veľmi dôležité. Pomáha ti to odhadnúť, čo môžu zahrať "
            "súperi, a plánovať ďalšie ťahy.\n\n"
            "Ak si nepamätáš posledné zahrané karty, môžeš si ich "
            "kedykoľvek pozrieť cez tlačidlo Posledný štich."
        ),
        "instruction": (
            "Klikni na „Posledný štich“ vpravo dole. Spoločne si "
            "spočítame, ktoré žalude už padli."
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
            "V prvom štichu padli štyri žalude: 7, 8, 10 a dolník.\n\n"
            "Ty máš horníka (Q♣) a deviatku (9♣). V hre tak zostávajú "
            "už len eso a kráľ – obe karty sú vyššie než tvoj "
            "horník.\n\n"
            "Teraz môžeš využiť počítanie kariet a bezpečne sa zbaviť "
            "trestného horníka."
        ),
        # Body ("Všimni si panel KOLO...") sa spomínajú až v samostatnom
        # kroku "trick2_collect" nižšie — v momente, keď hráč zahrá
        # kartu, ešte nebežala ani animácia zberu štichu, takže panel by
        # ukazoval staré (nezmenené) skóre.
        "text_after": (
            "Počítač 1 už nemal žalude, preto odhodil svojho "
            "vysvieteného zeleného horníka za 16 bodov. Ani Počítač 3 "
            "už žalude nemal.\n\n"
            "Počítač 2 ako jediný mal žalude a zahral kráľa. Tým "
            "prebil tvojho horníka a zobral celý štich.\n\n"
            "A kde je posledné žaluďové eso? Keďže ostatní dvaja "
            "súperi už žalude nemajú, musí ho mať Počítač 2.\n\n"
            "Vďaka sledovaniu kariet tak dokážeš nielen plánovať svoje "
            "ťahy, ale aj postupne odhaľovať, čo majú súperi v rukách."
        ),
        "human_instruction": "Zahraj žaluďového horníka (Q♣).",
    },
    {
        # Samostatný krok (nie zlúčený do trick2) — panel KOLO smie
        # ukázať pripísané body až TERAZ, po doletení kariet k víťazovi
        # (body sa pripíšu skôr, než sa vstúpi do tohto kroku — pozri
        # _enter_step v tutorial/tutorial_director.py).
        "kind": "text",
        "key": "trick2_collect",
        # Koľko bodov Počítač 2 týmto štichom reálne získal, závisí od
        # toho, či si hráč v kroku "vysvietenie" svojho žaluďového
        # horníka vysvietil (voliteľné, dá sa aj zrušiť) — vysvietený
        # je za 8b, nevysvietený za 4b. Horník Počítača 1 je vysvietený
        # vždy (naskriptovaná odchýlka, pozri 07_TUTORIAL_REFACTOR_
        # CATALOG.md §6), takže jeho 16b sú isté v oboch vetvách.
        "text_fn": lambda screen: (
            (
                "Vpravo dole sa ti teraz zobrazuje tabuľka KOLO. "
                "Ukazuje, koľko trestných bodov už jednotliví hráči v "
                "tomto kole získali.\n\n"
                "Počítač 2 práve zobral oboch vysvietených horníkov, "
                "preto mu pribudlo 24 bodov (16 + 8).\n\n"
                "Ikony pri menách ti počas celého kola pripomínajú, "
                "kto ktorého horníka vysvietil."
            ) if Card("acorn", "over") in screen.illuminated_cards else (
                "Vpravo dole sa ti teraz zobrazuje tabuľka KOLO. "
                "Ukazuje, koľko trestných bodov už jednotliví hráči v "
                "tomto kole získali.\n\n"
                "Počítač 2 práve zobral oboch horníkov — tvojho "
                "žaluďového aj vysvieteného zeleného od Počítača 1 — "
                "preto mu pribudlo 20 bodov (16 + 4). Tvoj horník "
                "nebol vysvietený, takže má nižšiu hodnotu.\n\n"
                "Ikony pri menách ti počas celého kola pripomínajú, "
                "kto ktorého horníka vysvietil."
            )
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
            "Počítač 2 začal listovou deviatkou (9♠) a Počítač 3 "
            "zahral kráľa (K♠).\n\n"
            "Máš ešte dve listové karty, takže musíš priznať farbu."
        ),
        "text_after": (
            "Počítač 1 zahral listového dolníka (J♠), no najvyšší "
            "zostáva kráľ Počítača 3. Ten berie štich a začína "
            "ďalší.\n\n"
            "V tomto štichu neboli žiadne trestné body."
        ),
        "human_instruction": (
            "Zahraj listovú osmičku (8♠) alebo sedmičku (7♠). Obe "
            "možnosti sú v poriadku."
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
            "Počítač 3 začal guľovým dolníkom (J●).\n\n"
            "Gule síce nemajú trestné body, no hráč, ktorý už gule "
            "nemá, môže do štichu odhodiť trestnú kartu. Preto sa nie "
            "vždy oplatí zahrať vysoko."
        ),
        "text_after": (
            "Zvolil si vyššiu kartu, no Počítač 1 zahral guľové eso "
            "(A●) a štich vyhral.\n\n"
            "Tentoraz v ňom neboli žiadne trestné body. Ďalší štich "
            "začína Počítač 1."
        ),
        "text_after_by_card": {
            ("bell", "king"): (
                "Zvolil si vyššiu kartu, no Počítač 1 zahral guľové "
                "eso (A●) a štich vyhral.\n\n"
                "Tentoraz v ňom neboli žiadne trestné body. Ďalší "
                "štich začína Počítač 1."
            ),
            ("bell", "eight"): (
                "Zvolil si nižšiu kartu a pokúsil sa vyhnúť výhre "
                "štichu. Počítač 1 zahral guľové eso (A●) a štich "
                "vyhral.\n\n"
                "Ani v tomto štichu neboli žiadne trestné body. Ďalší "
                "štich začína Počítač 1."
            ),
        },
        "human_instruction": (
            "Podlezieš osmičkou (8●), alebo skúsiš vyššieho kráľa (K●)?"
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
            "Počítač 1 začal srdcovou sedmičkou (7♥). Ostatní hráči "
            "tiež zahrali srdcia.\n\n"
            "Tebe zostala jediná srdcová karta, takže ju musíš zahrať."
        ),
        "text_after_fn": lambda screen: (
            (
                "Počítač 2 zahral najvyššiu kartu – srdcového horníka "
                "(Q♥) – a vyhral štich.\n\n"
                "Keďže sú vysvietení obaja horníci, každé srdce má "
                "hodnotu 2 body. Za štyri srdcia si teda Počítač 2 "
                "pripisuje 8 trestných bodov."
            ) if (
                screen.players[1].illuminated_leaf
                and Card("acorn", "over") in screen.illuminated_cards
            ) else (
                "Počítač 2 zahral najvyššiu kartu – srdcového horníka "
                "(Q♥) – a vyhral štich.\n\n"
                "Každé srdce má hodnotu 1 bod. Za štyri srdcia si teda "
                "Počítač 2 pripisuje 4 trestné body."
            )
        ),
        "human_instruction": "Zahraj srdcovú desiatku (10♥).",
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
            "Počítač 2 začal guľovou deviatkou (9●) a Počítač 3 "
            "zahral sedmičku (7●).\n\n"
            "Zostala ti už len jedna guľová karta, takže ju musíš "
            "zahrať."
        ),
        # Ktorú z dvoch kariet si nechal na trick6, závisí od toho, ktorú
        # si zahral pri trick4 (presný opak) — a od toho zase závisí, kto
        # štich vyhráva a teda kto vedie ďalej (pozri BRANCH_B_STEPS
        # nižšie). Oboje preto rieši jedna dynamická funkcia namiesto
        # samostatného "_collect" kroku.
        "text_after_fn": lambda screen: (
            (
                "Tvoj kráľ (K●) prebil guľového horníka (Q●) Počítača "
                "1, takže štich berieš ty.\n\n"
                "V štichu neboli žiadne trestné body. Ďalší štich "
                "začínaš ty."
            ) if screen.trick_human_played_card == Card("bell", "king") else (
                "Počítač 1 vyhral štich guľovým horníkom (Q●).\n\n"
                "Ani v tomto štichu neboli trestné body. Ďalší štich "
                "začína Počítač 1."
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
            "Počítač 1 začal srdcovou kartou, no ty už žiadne srdce "
            "nemáš. Môžeš preto zahrať ktorúkoľvek zo svojich "
            "zostávajúcich kariet."
        ),
        "text_after": (
            "Počítač 1 zahral najvyššie srdce a vyhral aj tento "
            "štich.\n\n"
            "Získava tak ďalšie trestné body."
        ),
        "human_instruction": "Zahraj jednu zo svojich dvoch kariet.",
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
            "Posledný štich kola! Každému hráčovi zostala už len "
            "jedna karta."
        ),
        "text_after": "Posledný štich vyhral Počítač 1. Kolo sa skončilo.",
        "human_instruction": "Zahraj svoju poslednú kartu.",
        "round_end": True,
    },
    {
        "kind": "text",
        "key": "chujogram_wait",
        "text": (
            "Odohrali sme všetkých 8 štichov. Trestné body sa teraz "
            "zapíšu do Chujogramu, kde môžeš sledovať výsledky celej "
            "hry."
        ),
        "instruction": "Klikni na ikonu Chujogramu vpravo dole a otvor tabuľku.",
    },
    {
        "kind": "text",
        "key": "chujogram_explain",
        # Guličky, ktoré tento text vysvetľuje, sú priamo v Chujograme
        # (pri hráčovi s najvyšším skóre v danom kole) — NIE guličky z
        # panelu KOLO. Históriu odohraných kôl ani sériový bonus za
        # čisté kolá naďalej zámerne nespomíname — to spolu súvisí
        # (bonus dáva zmysel len s pochopením histórie/série) a chceme
        # to vysvetliť spolu, až neskôr (plánovaná krátka precvičovacia
        # hra hneď po tutoriáli). Bonus preto v tomto tutoriáli ani
        # nespúšťame (pozri __init__, no_penalty_streak).
        "text": (
            "Toto je Chujogram – tabuľka, do ktorej sa po každom kole "
            "zapisujú trestné body všetkých hráčov.\n\n"
            "Pozri sa na svoje skóre: v tomto kole si nezískal ani "
            "jeden trestný bod. Presne o to sa v CHUJ-ovi snažíš!\n\n"
            "Pri hráčovi s najvyšším počtom trestných bodov sa v "
            "každom kole zobrazí bodka. Tieto bodky sa postupne "
            "spájajú čiarami a vytvárajú diagram – náš Chujogram."
        ),
    },
    {
        "kind": "result",
        "text": (
            "Práve si odohral celé kolo CHUJ-u – od rozdania kariet až "
            "po záverečné bodovanie.\n\n"
            "V skutočnej hre pokračujete ďalšími kolami, až kým "
            "niekto neprekročí 100 trestných bodov a nestane sa "
            "Chujom.\n\n"
            "Teraz si pripravený vyskúšať tréningovú hru, v ktorej ti "
            "bude počas hrania pomáhať poradca."
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
# naozaj vyhral (pozri tutorial/tutorial_director.py::step_for_trick(),
# ktorý víťaza číta priamo z odohratých štichov).
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
            "Vyhral si predchádzajúci štich, takže teraz začínaš "
            "ty.\n\n"
            "Zostali ti dve karty: listová sedmička (7♠) a žaluďová "
            "deviatka (9♣)."
        ),
        "text_after_fn": lambda screen: (
            (
                "Počítač 1 má vyššiu listovú kartu – desiatku (10♠) – "
                "a preto štich berie."
            ) if screen.trick_human_played_card.suit == "leaf" else (
                "Počítač 2 zahral žaluďové eso (A♣), ktorým prebil "
                "tvoju deviatku a vyhral štich."
            )
        ),
        "human_instruction": "Vyber si, ktorou kartou začneš.",
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
            "Posledný štich kola! Každému hráčovi zostala už len "
            "jedna karta."
        ),
        "text_after": "Posledný štich vyhral Počítač 3. Kolo sa skončilo.",
        "human_instruction": "Zahraj svoju poslednú kartu.",
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
            "Posledný štich kola! Každému hráčovi zostala už len "
            "jedna karta."
        ),
        "text_after": "Posledný štich vyhral Počítač 3. Kolo sa skončilo.",
        "human_instruction": "Zahraj svoju poslednú kartu.",
        "round_end": True,
    },
}
