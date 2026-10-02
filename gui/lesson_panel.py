# gui/lesson_panel.py
#
# Bočný panel s výkladom lekcie — veľký textový panel pri ľavom okraji,
# ktorým tutoriál hovorí s hráčom, plus tlačidlo "Ďalej".
#
# Presunuté z tutorial/tutorial_screen.py (_draw_panel a wrap metódy)
# v rámci refaktoru kapitoly 1 (etapa 3, pozri
# claude/08_TUTORIAL_REFACTOR_DESIGN.md §5). Panel zámerne NEVIE nič o
# krokoch tutoriálu — dostane hotový obsah a nakreslí ho. Prekladom
# "krok scenára -> obsah panelu" sa zaoberá tutorial/tutorial_director.py.
#
# Žije v gui/ (a nie v tutorial/) preto, že je to rodina gui/tip_panel.py
# a majú ho používať aj ďalšie kapitoly tutoriálu.

import pygame

from config import (
    COLOR_WHITE, COLOR_GOLD, COLOR_GRAY, COLOR_PANEL_BG,
    COLOR_BUTTON_PRIMARY, BUTTON_RADIUS,
    FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, get_font,
    TABLE_CENTER_X, CARD_SIZE_MEDIUM, HAND_CONFIGS,
)

# Panel začína pod horným pásom s názvom kapitoly.
PANEL_TOP = 90
PANEL_LEFT = 20
PANEL_MIN_W = 400
PANEL_MAX_W = 650
PANEL_PAD_X = 30          # odsadenie textu od okraja panelu
TEXT_TOP_OFFSET = 46      # text vždy začína takto nízko pod hornou hranou

# Dve veľkosti písma: ak sa text pri strednom nezmestí do dostupnej výšky,
# panel prepne na menšie namiesto toho, aby rástol ďalej dole.
LINE_H_MEDIUM, LABEL_LINE_H_MEDIUM = 32, 30
LINE_H_SMALL, LABEL_LINE_H_SMALL = 24, 24

BUTTON_H = 46


class LessonPanel:
    """Panel s výkladom lekcie pri ľavom okraji obrazovky."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_small = get_font(FONT_SIZE_SMALL)
        self.font_medium = get_font(FONT_SIZE_MEDIUM)

        # Panel smie prekryť iba ruku Počítača 3 (karty rubom, na priebeh
        # to nemá vplyv) — nesmie však zasiahnuť ani do stredu stola
        # (karty štichu), ani do vlastnej ruky hráča dole. Obe hranice
        # počítame z reálnej geometrie stola a ruky (config konštanty),
        # takže to funguje pri akomkoľvek rozlíšení.
        table_left_x = TABLE_CENTER_X - 150 - CARD_SIZE_MEDIUM[0] // 2
        self.max_right = table_left_x - 40
        self.max_bottom = HAND_CONFIGS[0]["y"] - 30

        # Spodná a pravá hrana naposledy nakresleného panelu — číta ich
        # kreslenie prehľadu trestných kariet, aby sa panelu vyhlo.
        self.last_bottom: int = PANEL_TOP + 260
        self.last_right: int = PANEL_LEFT + PANEL_MIN_W
        # Tlačidlo "Ďalej" z posledného kreslenia (prázdne = nie je).
        self.next_button = pygame.Rect(0, 0, 0, 0)

    # ------------------------------------------------------------------
    # Kreslenie
    # ------------------------------------------------------------------

    def draw(self, counter: str | None = None,
             labels: list[tuple[str, bool]] = (),
             title: str | None = None,
             paragraphs: str | None = None,
             bullets: list[str] | None = None,
             instruction: str | None = None,
             button_label: str | None = None,
             x_offset: int = 0) -> pygame.Rect:
        """
        Nakreslí panel a vráti obdĺžnik tlačidla "Ďalej".

        counter: napr. "Krok 3/17" — malý sivý text v hlavičke.
        labels: [(text, je_aktívny)] — zoznam bodov nad textom
            (Rozdanie / Vysvietenie / Záväzok); aktívny je zlatý.
        title: voliteľný zlatý nadpis nad obsahom.
        paragraphs: telo textu; odstavce oddelené "\\n\\n" sa oddelia
            prázdnym riadkom.
        bullets: alternatíva k paragraphs — zoznam krátkych viet, každá
            dostane odrážku.
        instruction: zlatá inštrukcia pod textom ("Zahraj J♣").
        button_label: text tlačidla, alebo None = tlačidlo sa nekreslí
            (hráč má najprv vykonať akciu, ktorú mu prikazuje inštrukcia).
        x_offset: posun doprava, keď je vysunutý Chujogram (ten zaberá
            vlastný pás naľavo). Panel sa tým zároveň zúži.

        Vracia prázdny Rect, keď sa tlačidlo nekreslí — volajúci tak
        nemusí riešiť None.
        """
        px = PANEL_LEFT + max(0, int(x_offset))
        py = PANEL_TOP
        panel_w = max(PANEL_MIN_W, min(PANEL_MAX_W, self.max_right - px))
        inner_w = panel_w - 2 * PANEL_PAD_X
        available_h = self.max_bottom - py
        show_button = button_label is not None

        def layout(font, line_h, label_line_h):
            if bullets is not None:
                lines = self.wrap_bullets(bullets, font, inner_w)
            else:
                lines = self.wrap_paragraphs(paragraphs or "", font, inner_w)
            instruction_lines = (
                self.wrap_text(instruction, font, inner_w) if instruction else []
            )
            content_h = len(labels) * label_line_h
            if labels:
                content_h += 14          # medzera medzi zoznamom a textom
            if title:
                content_h += line_h + 10  # nadpis + medzera pred obsahom
            content_h += (len(lines) + len(instruction_lines)) * line_h
            # Zlatá inštrukcia je samostatný odstavec — oddelí sa od textu
            # prázdnym riadkom, rovnako ako sa oddeľujú odstavce medzi
            # sebou. Bez toho splývala s poslednou vetou výkladu.
            if lines and instruction_lines:
                content_h += line_h
            # Pod textom treba vyhradiť miesto na tlačidlo (medzera +
            # výška + spodný okraj), alebo aspoň spodný okraj bez neho.
            panel_h = (TEXT_TOP_OFFSET + content_h
                       + (20 + BUTTON_H + 16 if show_button else 24))
            return lines, instruction_lines, panel_h

        body_font, line_h, label_line_h = (
            self.font_medium, LINE_H_MEDIUM, LABEL_LINE_H_MEDIUM
        )
        lines, instruction_lines, panel_h = layout(
            body_font, line_h, label_line_h
        )
        if panel_h > available_h:
            body_font, line_h, label_line_h = (
                self.font_small, LINE_H_SMALL, LABEL_LINE_H_SMALL
            )
            lines, instruction_lines, panel_h = layout(
                body_font, line_h, label_line_h
            )
        panel_h = min(panel_h, available_h)
        self.last_bottom = py + panel_h
        self.last_right = px + panel_w

        surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surface.fill((*COLOR_PANEL_BG, 235))
        self.screen.blit(surface, (px, py))
        pygame.draw.rect(
            self.screen, COLOR_GOLD, (px, py, panel_w, panel_h),
            width=2, border_radius=14
        )

        if counter:
            counter_surf = self.font_small.render(counter, True, COLOR_GRAY)
            self.screen.blit(counter_surf, (px + 20, py + 14))

        ty = py + TEXT_TOP_OFFSET
        text_x = px + PANEL_PAD_X

        for label_text, is_active in labels:
            color = COLOR_GOLD if is_active else COLOR_GRAY
            self.screen.blit(body_font.render(label_text, True, color),
                             (text_x, ty))
            ty += label_line_h
        if labels:
            ty += 14

        if title:
            self.screen.blit(body_font.render(title, True, COLOR_GOLD),
                             (text_x, ty))
            ty += line_h + 10

        for line in lines:
            self.screen.blit(body_font.render(line, True, COLOR_WHITE),
                             (text_x, ty))
            ty += line_h

        if lines and instruction_lines:
            ty += line_h          # prázdny riadok pred inštrukciou

        for line in instruction_lines:
            self.screen.blit(body_font.render(line, True, COLOR_GOLD),
                             (text_x, ty))
            ty += line_h

        if not show_button:
            self.next_button = pygame.Rect(0, 0, 0, 0)
            return self.next_button

        text_surf = self.font_medium.render(button_label, True, COLOR_WHITE)
        btn_w = text_surf.get_width() + 50
        self.next_button = pygame.Rect(
            px + panel_w - btn_w - 20,
            py + panel_h - BUTTON_H - 16,
            btn_w, BUTTON_H
        )
        overlay = pygame.Surface((btn_w, BUTTON_H), pygame.SRCALPHA)
        overlay.fill((*COLOR_BUTTON_PRIMARY, 230))
        self.screen.blit(overlay, self.next_button.topleft)
        pygame.draw.rect(
            self.screen, COLOR_GOLD, self.next_button,
            width=2, border_radius=BUTTON_RADIUS
        )
        self.screen.blit(
            text_surf, text_surf.get_rect(center=self.next_button.center)
        )
        return self.next_button

    # ------------------------------------------------------------------
    # Zalamovanie textu
    # ------------------------------------------------------------------

    @staticmethod
    def wrap_text(text: str, font: pygame.font.Font,
                  max_width: int) -> list[str]:
        """Zalomí text na riadky, ktoré sa zmestia do max_width."""
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            test = f"{current} {word}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def wrap_paragraphs(text: str, font: pygame.font.Font,
                        max_width: int) -> list[str]:
        """Ako wrap_text, ale rešpektuje odstavce oddelené dvojitým novým
        riadkom ("\\n\\n") — medzi odstavce vloží prázdny riadok. Vďaka
        tomu texty s viacerými udalosťami za sebou (napr. "Počítač 2
        hrá...", "Počítač 3 hrá...") pôsobia prehľadnejšie než jeden
        súvislý blok.

        Odstavec môže obsahovať aj tesný odrážkový zoznam — riadky
        oddelené jednoduchým "\\n", kde položky zoznamu začínajú "* "
        (napr. "Teraz platí:\\n* Zelený horník: ...\\n* Žaluďový
        horník: ..."). Takéto riadky sa vykreslia s odrážkou a bez
        medzery medzi sebou (na rozdiel od odstavcov); nebulletované
        riadky v tom istom odstavci (napr. úvodné "Teraz platí:")
        ostávajú normálnym textom."""
        marker, indent = "•  ", "   "
        marker_w = font.size(marker)[0]
        lines: list[str] = []
        for i, para in enumerate(text.split("\n\n")):
            if i > 0:
                lines.append("")
            if "\n* " in para or para.startswith("* "):
                for item in para.split("\n"):
                    item = item.strip()
                    if not item:
                        continue
                    if item.startswith("* "):
                        wrapped = LessonPanel.wrap_text(
                            item[2:].strip(), font, max_width - marker_w
                        )
                        for j, line in enumerate(wrapped):
                            lines.append(
                                f"{marker if j == 0 else indent}{line}"
                            )
                    else:
                        lines.extend(
                            LessonPanel.wrap_text(item, font, max_width)
                        )
            else:
                lines.extend(LessonPanel.wrap_text(para, font, max_width))
        return lines

    @staticmethod
    def wrap_bullets(bullets: list[str], font: pygame.font.Font,
                     max_width: int) -> list[str]:
        """Rozdelí zoznam krátkych viet na riadky s odrážkou na začiatku
        každej vety a odsadením na pokračovacích riadkoch — výsledok sa
        kreslí tou istou slučkou ako riadky z wrap_text.

        Prázdny reťazec ("") v zozname sa chápe ako oddeľovač skupín —
        vloží prázdny riadok bez odrážky, rovnako ako "\\n\\n" oddeľuje
        odstavce vo wrap_paragraphs. Vďaka tomu môžu súvisiace body
        vizuálne tvoriť samostatné skupiny (napr. [3, 2, 2])."""
        marker, indent = "•  ", "   "
        marker_w = font.size(marker)[0]
        lines: list[str] = []
        for bullet in bullets:
            if bullet == "":
                lines.append("")
                continue
            wrapped = LessonPanel.wrap_text(bullet, font, max_width - marker_w)
            for i, line in enumerate(wrapped):
                lines.append(f"{marker if i == 0 else indent}{line}")
        return lines

    def __repr__(self) -> str:
        return f"LessonPanel(bottom={self.last_bottom})"
