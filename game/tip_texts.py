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
        "Príliš vysoká by štich zobrala, nízku kartu si nechaj na "
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
        "Odhoď horníka.",
        "Horník je najdrahšia karta v ruke a teraz ňou štich nezoberieš.",
    ),
    "DumpSpecial.IMMEDIATE_90": (
        "Odhoď horníka, tebe body nepripíše.",
        "Máš 90+ bodov — horníci sa ti už nerátajú.",
    ),
    "DumpHeart.VOID": (
        "Odhoď srdce.",
        "Farbu nemáš — zbav sa srdca, každé je trestný bod.",
    ),
    "DumpHeart.UNDERPLAY": (
        "Odhoď srdce.",
        "Štich berie niekto iný,",
    ),
    "DumpDangerous.DANGER_TRAP": (
        "Zbav sa nebezpečnej karty.",
        "Skôr či neskôr ňou môžeš zobrať štich"
        " aj s horníkom.",
    ),
    "DumpDangerous.TRAP": (
        "Zbav sa nebezpečnej karty.",
        "Nikto vyšší v tejto farbe už nie je vonku — čím dlhšie ju "
        "držíš, tým istejšie ňou vezmeš štich.",
    ),
    "DumpHigh.HIGH_CARD": (
        "Odhoď vysokú kartu.",
        "Aspoň zľahčíš ruku o kartu, ktorá "
        "by neskôr mohla brať štichy.",
    ),

    # --- vedenie štichu ----------------------------------------------
    "LeadSafe.ESCAPE": (
        "Veď bezpečnou kartou.",
        "Niekto vyšší v tejto farbe je ešte vonku, možno ťa prebije a "
        "štich nezoberieš.",
    ),
    "LeadSafe.BELL_ESCAPE": (
        "Veď guľami.",
        "V guliach nie sú trestné body — bezpečný spôsob, ako "
        "sa zbaviť karty",
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
        "Máš 90+ bodov, takže každý trestný bod bolí — pusti ho,"
        "kým sa dá.",
    ),
    "LeadSafe.FORCE_TAKE_SPECIAL": (
        "Vytlač cudzieho horníka.",
        "Súper musí priznať farbu, a ak má horníka, bude ho musieť "
        "zahrať.",
    ),
    "ForceSpecial.FORCE": (
        "Vytiahni cudzieho horníka.",
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
        "Nič bodované v ňom nie je, takže ťa výhra nič nestojí",
    ),
    "AcceptTrick.FORCED_POINTS": (
        "Štichu sa nevyhneš.",
        "Body v ňom sú, ale lepšiu možnosť nemáš — ber ho aspoň kartou, "
        "ktorá je najvyššia.",
    ),
    "AcceptTrick.FREE_TAKE": (
        "Ber štich, teraz je to zadarmo.",
        "Horník je preč a nič bodované v štichu nie je — lacná "
        "príležitosť zahodiť vysokú kartu",
    ),
    "AcceptTrick.EARLY_TAKE": (
        "Ber štich.",
        "Kým sú gule nerozohrané, je tento štich bezpečný — neskôr už "
        "nemusí byť.",
    ),
    "RiskSpecial.RISK": (
        "Riskni horníka.",
        "Niekto vyšší je ešte vonku — je šanca, že horník prejde bez "
        "toho, aby si ho schytal ty.",
    ),
    "RiskSpecial.RISK_TRAP": (
        "Môžeš to risknúť.",
        "Nie je to isté, ale možno nemá horníka",
    ),
    "Wait.WAIT": (
        "Počkaj si.",
        "Možno zatiaľ berieš štich,"
        " ale je možné, že ťa ešte prebijú",
    ),

    # --- mimo selectora ----------------------------------------------
    "SWEEP_COMMIT": (
        "Poď po všetkých kartách!",
        "AI vyhodnotila, že máš šancu pozbierať všetky trestné karty — "
        "to je šanca odpísať −10 bodov",
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
    # Tieto dve sú len núdzový fallback pre prípad, že by niekedy niekto
    # zavolal illumination_reason() bez reserve_quality/risk_level/
    # comp_breakdown (bežne sa tak nikdy nestane — game/advisor.py ich
    # vždy posiela a text sa poskladá cez _illumination_decision_text()
    # nižšie, presne podľa toho, čo sa v danej ruke reálne stalo).
    "decision_yes": (
        "AI vyhodnotila, že krytie aj zvyšok ruky sú v poriadku — "
        "vysvietenie sa oplatí."
    ),
    "decision_no": (
        "AI vyhodnotila, že riziko je teraz príliš vysoké na vysvietenie."
    ),
    "no_reserves": (
        "Horníka nemáš čím kryť — je v tej farbe sám, takže "
        "hneď, ako sa farba zahrá, asi ho schytáš."
    ),
    "bad_reserves": (
        "Tvoje ostatné karty v tej farbe sú privysoké — asi by som"
        "ho nesvietil"
    ),
    "leader_borderline": (
        "Vedieš v bodoch, takže si nemôžeš dovoliť riskovať — krytie je "
        "na hrane."
    ),
    "high_score_unprotected_hearts": (
        "Máš 90+ bodov a nekryté vysoké srdcia — jedno-dve zlé kolá ťa "
        "pošlú cez stovku."
    ),
    "high_score_naked_high": (
        "Máš 90+ bodov a vysokú guľu bez nízkej — príliš tesné na "
        "zvyšovanie stávok."
    ),
}

_ILLUMINATION_FALLBACK = "AI by v tejto ruke volila takto."

# Skrátené znenie — použije sa, keď hráč drží OBOCH horníkov a v paneli
# treba dva dôvody vedľa seba (dlhé vety by sa tam nezmestili).
_ILLUMINATION_REASONS_SHORT: dict[str, str] = {
    # Rovnaký núdzový fallback ako vyššie — bežne sa nepoužije, pozri
    # illumination_reason().
    "decision_yes": "oplatí sa riskovať",
    "decision_no": "riziko je vysoké",
    "no_reserves": "nemáš ho čím kryť",
    "bad_reserves": "rezervy sú privysoké",
    # Skrátené z "vedieš v bodoch, netreba riskovať" — pri dvoch
    # horníkoch (obaja s týmto dôvodom naraz) to už nepretiahol panel
    # (nájdené 2026-09-26 vyčerpávajúcim testom všetkých párov krátkych
    # dôvodov — pozri test_tip_fit_exhaustive.py).
    "leader_borderline": "vedieš v bodoch",
    "high_score_unprotected_hearts": "90+ bodov a nekryté srdcia",
    "high_score_naked_high": "90+ bodov a vysoká guľa",
}

_ILLUMINATION_FALLBACK_SHORT = "podľa AI"

# Mená farieb pre hráča (nominatív, používa sa len v texte o "poistke"
# nižšie — inde sa farby ukazujú symbolom, pozri Advisor._SPECIAL_NAMES).
_SUIT_NAMES_NOM = {"heart": "srdce", "bell": "gule", "leaf": "zelená", "acorn": "žalude"}


def _poistka_phrase(comp_breakdown: dict | None) -> str | None:
    """
    Veta o "poistke" (void farba / posledná pozícia v poradí) — presne to,
    čo _compensation_count() v game/ai_declaration.py reálne napočítal.

    Vracia None, ak žiadna poistka nie je — vtedy sa o nej v tipe
    zámerne nepíše vôbec nič (rozhodnutie z konzultácie s userom:
    negatívna veta "nemáš žiadnu poistku" len pridáva slová bez úžitku).
    """
    if not comp_breakdown:
        return None
    parts = []
    void = comp_breakdown.get("void")
    if void:
        names = [_SUIT_NAMES_NOM.get(s, s) for s in void]
        if len(names) > 2:
            parts.append("máš viacero voľných farieb")
        elif len(names) == 1:
            parts.append(f"máš voľnú farbu: {names[0]}")
        else:
            parts.append(f"máš voľné: {', '.join(names)}")
    if comp_breakdown.get("position"):
        parts.append("si posledný na rade")
    return " a ".join(parts) if parts else None


def _illumination_decision_text(is_yes: bool, reserve_quality: str,
                                risk_level: str | None,
                                comp_breakdown: dict | None) -> str:
    """
    Poskladá vetu pre decision_yes/decision_no z toho, čo sa v ruke
    reálne stalo — namiesto jedného pevného textu na kód. Dôvod: tento
    kód sa priraďuje, až keď je samotné krytie horníka už vyhodnotené
    (zlé krytie sa odchytí skôr — no_reserves/bad_reserves/
    leader_borderline), takže "nie" tu takmer vždy znamená "krytie je
    OK/na hrane, ale zvyšok ruky je rizikový a chýba poistka" — nie
    "krytie nestačí", ako pôvodne tvrdil statický text (nález: seed
    1745156702, hráč mal dobré krytie žaluďov, no tip hovoril o zlom
    krytí).

    Len pre JEDNÉHO drženého horníka (game/advisor.py) — pri dvoch sa
    zámerne používa vždy skrátená verzia (nezmestí sa dvakrát, pozri
    diskusiu o TIP_PANEL_H).
    """
    good_reserve = reserve_quality in ("strong", "good")
    coverage = ("Krytie v tejto farbe je dobré" if good_reserve
                else "Krytie v tejto farbe je len na hrane")
    parts = [coverage]
    if risk_level == "medium":
        parts.append("časť ruky je rizikovejšia")
    elif risk_level == "critical":
        parts.append("zvyšok ruky je dosť rizikový")
    poistka = _poistka_phrase(comp_breakdown)
    if poistka:
        parts.append(f"ale {poistka}")
    verdict = "vysvietenie sa oplatí" if is_yes else "radšej nesvieť"
    return f"{', '.join(parts)} — {verdict}."


def illumination_reason(reason_code: str, short: bool = False,
                        reserve_quality: str | None = None,
                        risk_level: str | None = None,
                        comp_breakdown: dict | None = None) -> str:
    """
    Vysvetlenie k rozhodnutiu o vysvietení. Nikdy nevyhodí výnimku.

    Pre "decision_yes"/"decision_no" je text SKLADANÝ z reserve_quality/
    risk_level/comp_breakdown (presné dôvody danej ruky), keď ich
    volajúci pošle — game/advisor.py ich vždy posiela. Ostatné kódy
    (no_reserves, bad_reserves, leader_borderline, high_score_*) majú
    už teraz 1:1 vzťah k dôvodu, tie ostávajú jednoduchý slovníkový
    lookup.
    """
    if reason_code in ("decision_yes", "decision_no") and reserve_quality:
        is_yes = reason_code == "decision_yes"
        good_reserve = reserve_quality in ("strong", "good")
        if short:
            if is_yes:
                return "krytie stačí" if good_reserve else "krytie na hrane, ale stačí"
            return "riziko v ruke je vysoké" if good_reserve else "krytie je na hrane"
        return _illumination_decision_text(
            is_yes, reserve_quality, risk_level, comp_breakdown
        )

    if short:
        return _ILLUMINATION_REASONS_SHORT.get(
            reason_code, _ILLUMINATION_FALLBACK_SHORT
        )
    return _ILLUMINATION_REASONS.get(reason_code, _ILLUMINATION_FALLBACK)


def _pair(value) -> tuple[str, str] | None:
    """
    Prevedie záznam zo slovníka na dvojicu (nadpis, vysvetlenie).

    Znie to zbytočne obranne, ale nie je: tieto texty sa prepisujú ručne
    a stačí jedna čiarka navyše medzi dvoma časťami vety, aby zo záznamu
    bola trojica. Kedysi to zhodilo rozohratú hru priamo v ťahu — tip je
    pomôcka, takže zle napísaný text smie pokaziť nanajvýš seba. Dlhšiu
    n-ticu preto spojíme späť do jednej vety a kratšiu doplníme.
    """
    if isinstance(value, str):
        return value, ""
    if isinstance(value, (tuple, list)):
        parts = [str(p) for p in value if p is not None]
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(p.strip() for p in parts[1:]).strip()
    return None


def tip_text_for(strategy: str, variant: str,
                 card: Card | None = None) -> tuple[str, str]:
    """
    Vráti (nadpis, vysvetlenie) pre danú AI stratégiu a variant.
    Nikdy nevyhodí výnimku — neznámy ani zle zapísaný variant dá
    všeobecný text.
    """
    candidates = []
    if strategy and variant:
        candidates.append(_TEXTS.get(f"{strategy}.{variant}"))
    if variant:
        candidates.append(_TEXTS.get(variant))
        # Posledný pokus: rovnaký variant pod inou stratégiou
        # (napr. UNDERPLAY má DumpHeart aj AvoidTrick) — radšej text
        # susednej stratégie než nič.
        for key, text in _TEXTS.items():
            if key.endswith(f".{variant}"):
                candidates.append(text)
                break
    for value in candidates:
        if value:
            pair = _pair(value)
            if pair is not None:
                return pair
    return _FALLBACK
