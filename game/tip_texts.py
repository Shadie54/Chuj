# game/tip_texts.py
#
# Preklad interných AI variantov (napr. "AvoidTrick.UNDERPLAY") do viet
# pre hráča. Zámerne mimo AI — AI hovorí kódmi, GUI potrebuje slovenčinu,
# a tento slovník je jediné miesto, kde sa to stretáva. Používa ho ostrá
# hra aj tutoriál, takže tipy znejú všade rovnako.
#
# Formulácia je vždy "AI by zahrala X, lebo Y" — nie "správny ťah je X".
# AI je silná heuristika, nie riešiteľ hry (pozri Known Issues v
# 02_AI_REFERENCE.md); hráča chceme naučiť uvažovať, nie poslúchať.
#
# Kľúč je "StrategyName.VARIANT". Ak dvojica chýba, skúsi sa samotný
# VARIANT, a až potom všeobecný fallback — vďaka tomu nová (alebo
# premenovaná) AI stratégia nikdy nezhodí tipy, len dá strohejší text.

from game.card import Card

# (krátky nadpis, vysvetlenie)
_TEXTS: dict[str, tuple[str, str]] = {
    # --- vyhýbanie sa štichu -----------------------------------------
    "AvoidTrick.UNDERPLAY": (
        "Podlez to.",
        "Máš kartu nižšiu než aktuálne najvyššia v štichu — štich "
        "nezoberieš a nič neriskuješ.",
    ),
    "AvoidTrick.RISK_PICK": (
        "Zahraj strednú kartu.",
        "Príliš vysoká by štich zobrala, príliš nízka by ti ostala na "
        "horšiu chvíľu.",
    ),
    "AvoidTrick.DUMP_AK_FREE_OWN": (
        "Zbav sa vysokej karty teraz.",
        "Eso či kráľ ti neskôr nemá ako uniknúť — teraz ich vieš pustiť "
        "bez toho, aby ti zobrali štich.",
    ),
    "AvoidTrick.DUMP_AK_FREE_OPPONENT": (
        "Zbav sa vysokej karty teraz.",
        "Štich aj tak berie niekto iný — je to lacná príležitosť pustiť "
        "nebezpečnú kartu.",
    ),

    # --- odhadzovanie (dump) -----------------------------------------
    "DumpSpecial.VOID": (
        "Odhoď horníka.",
        "Farbu nemáš, takže sa vieš zbaviť najdrahšej karty v ruke — "
        "horníka schytá niekto iný.",
    ),
    "DumpSpecial.UNDERPLAY": (
        "Pusti horníka pod cudziu kartu.",
        "Horník je najdrahšia karta v ruke a teraz ňou štich nezoberieš.",
    ),
    "DumpSpecial.IMMEDIATE_90": (
        "Odhoď horníka, tebe body nepripíše.",
        "Máš 90+ bodov — horníci sa ti už nerátajú, takže je to "
        "najlacnejšia karta, akú vieš pustiť.",
    ),
    "DumpHeart.VOID": (
        "Odhoď srdce.",
        "Farbu nemáš — zbav sa srdca, každé je trestný bod.",
    ),
    "DumpHeart.UNDERPLAY": (
        "Pusti srdce pod cudziu kartu.",
        "Štich berie niekto iný, takže srdce odchádza bez toho, aby si "
        "zaň platil ty.",
    ),
    "DumpDangerous.DANGER_TRAP": (
        "Zbav sa nebezpečnej karty.",
        "Túto kartu už nikto neprebije — ak ti ostane, skôr či neskôr "
        "ňou zoberieš štich aj s bodmi.",
    ),
    "DumpDangerous.TRAP": (
        "Zbav sa zaseknutej karty.",
        "Nikto vyšší v tejto farbe už nie je vonku — čím dlhšie ju "
        "držíš, tým istejšie ňou vezmeš štich.",
    ),
    "DumpHigh.HIGH_CARD": (
        "Odhoď vysokú kartu.",
        "Nič bodované sa neponúka, tak aspoň zľahčíš ruku o kartu, ktorá "
        "by neskôr brala štichy.",
    ),

    # --- vedenie štichu ----------------------------------------------
    "LeadSafe.ESCAPE": (
        "Veď bezpečnou kartou.",
        "Niekto vyšší v tejto farbe je ešte vonku, takže ťa prebije a "
        "štich nezoberieš.",
    ),
    "LeadSafe.BELL_ESCAPE": (
        "Veď guľami.",
        "V guliach nie je žiadna trestná karta — bezpečný spôsob, ako "
        "dostať ťah z ruky.",
    ),
    "LeadSafe.EXHAUST": (
        "Vyčerpaj farbu.",
        "Ťahá súperom karty z farby, ktorú máš pokrytú, bez rizika, že "
        "schytáš body.",
    ),
    "LeadSafe.PROTECTED_ESCAPE_PRIMARY": (
        "Veď bezpečnou kartou.",
        "Necháva ti krytie pre horníka, ktorého držíš.",
    ),
    "LeadSafe.PROTECTED_ESCAPE_SECONDARY": (
        "Veď bezpečnou kartou.",
        "Z toho, čo ostalo, je to najmenej riskantná voľba.",
    ),
    "LeadSafe.HIGH_SCORE": (
        "Zbav sa prebytočného srdca.",
        "Máš 90+ bodov, takže každý trestný bod bolí — pusti ho, kým sa "
        "dá lacno.",
    ),
    "LeadSafe.FORCE_TAKE_SPECIAL": (
        "Vytlač cudzieho horníka.",
        "Súper musí priznať farbu, a ak má horníka, bude ho musieť "
        "zahrať.",
    ),
    "ForceSpecial.FORCE": (
        "Vytlač cudzieho horníka.",
        "Vedieš farbou, v ktorej súper drží horníka — musí priznať a "
        "horník môže padnúť.",
    ),
    "SetupVoid.SETUP": (
        "Priprav si void.",
        "Zbavíš sa poslednej karty tejto farby — nabudúce do nej budeš "
        "môcť odhodiť čokoľvek nebezpečné.",
    ),

    # --- vedomé branie štichu ----------------------------------------
    "AcceptTrick.FORCED_CLEAN": (
        "Zober štich, je čistý.",
        "Nič bodované v ňom nie je, takže ťa výhra nič nestojí — a "
        "získaš ťah.",
    ),
    "AcceptTrick.FORCED_POINTS": (
        "Štichu sa nevyhneš.",
        "Body v ňom sú, ale lepšiu možnosť nemáš — ber ho aspoň kartou, "
        "ktorá ti inak zavadzia.",
    ),
    "AcceptTrick.FREE_TAKE": (
        "Ber štich, teraz je to zadarmo.",
        "Horník je preč a nič bodované v štichu nie je — lacná "
        "príležitosť získať ťah.",
    ),
    "AcceptTrick.EARLY_TAKE": (
        "Ber štich zavčasu.",
        "Kým sú gule nerozohrané, je tento štich bezpečný — neskôr už "
        "nemusí byť.",
    ),
    "RiskSpecial.RISK": (
        "Riskni horníka.",
        "Niekto vyšší je ešte vonku — je šanca, že horník prejde bez "
        "toho, aby si ho schytal ty.",
    ),
    "RiskSpecial.RISK_TRAP": (
        "Riskni to.",
        "Nie je to isté, ale pomer rizika a zisku vychádza v tvoj "
        "prospech.",
    ),
    "Wait.WAIT": (
        "Počkaj si.",
        "Nič sa teraz netlačí — zahraj nenápadne a nechaj rozhodnutie na "
        "neskôr.",
    ),

    # --- mimo selectora ----------------------------------------------
    "SWEEP_COMMIT": (
        "Ideš na zhabanie všetkého!",
        "AI vyhodnotila, že máš šancu pozbierať všetky trestné karty — "
        "to je −10 bodov namiesto plusových.",
    ),
    "FORCED_SINGLE_CARD": (
        "Nemáš na výber.",
        "Toto je jediná karta, ktorú smieš zahrať.",
    ),
    "FORCED_LEAD_TRAP": (
        "Štichu sa už nevyhneš.",
        "Všetky tvoje karty sú také vysoké, že ich nikto neprebije — "
        "ktorúkoľvek zahráš, štich berieš.",
    ),
    "GLOBAL_FALLBACK": (
        "Zahraj nízku kartu.",
        "Nič výrazné sa neponúka — najnižšia karta je najbezpečnejšia "
        "voľba.",
    ),
    "DECLARATION_NONE": (
        "Pozor, hrá sa záväzok.",
        "Niekto vyhlásil „Nechytím nič“ — hra sa točí okolo toho, či mu "
        "to vyjde.",
    ),
    "DECLARATION_ALL": (
        "Hráš „Beriem všetko“.",
        "Potrebuješ všetkých 8 štichov — hraj čo najvyššie.",
    ),
}

# Ak nesedí ani "Strategy.VARIANT", ani samotný VARIANT.
_FALLBACK = ("AI by zahrala túto kartu.", "")


# ----------------------------------------------------------------------
# Vysvietenie horníka
# ----------------------------------------------------------------------
# Kľúč = dôvod z DeclarationAdvisor._should_illuminate (posledná položka
# debug tuplu). Hodnota = vysvetlenie; nadpis ("Sviet"/"Nesviet") skladá
# advisor.py podľa samotného rozhodnutia, lebo závisí aj od toho, koľko
# horníkov hráč drží.
_ILLUMINATION_REASONS: dict[str, str] = {
    "decision_yes": (
        "Máš dosť nízkych kariet v tej farbe na to, aby si horníka "
        "ubránil — zdvojnásobená hodnota je preto rozumné riziko."
    ),
    "decision_no": (
        "Krytie v tej farbe na to nestačí — ak ho schytáš, zaplatíš "
        "dvojnásobok."
    ),
    "no_reserves": (
        "Horníka nemáš čím kryť — je v tej farbe sám, takže ho zahráš "
        "hneď, ako sa farba vynesie."
    ),
    "bad_reserves": (
        "Tvoje ostatné karty v tej farbe sú privysoké — nekryjú horníka, "
        "samy ťahajú štichy."
    ),
    "leader_borderline": (
        "Vedieš v bodoch, takže si nemôžeš dovoliť riskovať — krytie je "
        "na hrane."
    ),
    "high_score_unprotected_hearts": (
        "Máš 90+ bodov a nekryté vysoké srdcia — jedno zlé kolo ťa "
        "posiela cez stovku."
    ),
    "high_score_naked_high": (
        "Máš 90+ bodov a nahú vysokú guľu bez nízkej — príliš tesné na "
        "zvyšovanie stávok."
    ),
}

_ILLUMINATION_FALLBACK = "AI by v tejto ruke volila takto."

# Skrátené znenie — použije sa, keď hráč drží OBOCH horníkov a v paneli
# treba dva dôvody vedľa seba (dlhé vety by sa tam nezmestili).
_ILLUMINATION_REASONS_SHORT: dict[str, str] = {
    "decision_yes": "krytie stačí",
    "decision_no": "krytie nestačí",
    "no_reserves": "nemáš ho čím kryť",
    "bad_reserves": "rezervy sú privysoké",
    "leader_borderline": "vedieš v bodoch, netreba riskovať",
    "high_score_unprotected_hearts": "90+ bodov a nekryté srdcia",
    "high_score_naked_high": "90+ bodov a nahá vysoká guľa",
}

_ILLUMINATION_FALLBACK_SHORT = "podľa AI"


def illumination_reason(reason_code: str, short: bool = False) -> str:
    """Vysvetlenie k rozhodnutiu o vysvietení. Nikdy nevyhodí výnimku."""
    if short:
        return _ILLUMINATION_REASONS_SHORT.get(
            reason_code, _ILLUMINATION_FALLBACK_SHORT
        )
    return _ILLUMINATION_REASONS.get(reason_code, _ILLUMINATION_FALLBACK)


def tip_text_for(strategy: str, variant: str,
                 card: Card | None = None) -> tuple[str, str]:
    """
    Vráti (nadpis, vysvetlenie) pre danú AI stratégiu a variant.
    Nikdy nevyhodí výnimku — neznámy variant dá všeobecný text.
    """
    if strategy and variant:
        text = _TEXTS.get(f"{strategy}.{variant}")
        if text:
            return text
    if variant:
        text = _TEXTS.get(variant)
        if text:
            return text
        # Posledný pokus: rovnaký variant pod inou stratégiou
        # (napr. UNDERPLAY má DumpHeart aj AvoidTrick) — radšej text
        # susednej stratégie než nič.
        for key, text in _TEXTS.items():
            if key.endswith(f".{variant}"):
                return text
    return _FALLBACK
