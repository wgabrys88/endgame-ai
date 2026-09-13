"""Stateless user prompt dla modelu wizyjnego.

System prompt zostaje STABILNY (cache). User prompt jest przebudowywany
co turę z bieżącej klatki — model NIE dostaje historii czatu.

Cel: model ma wiedzieć GDZIE JEST (aplikacja, okno, kursor, czego szuka),
nie KIM BYŁ trzy tury temu.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SYSTEM_PROMPT = """Jesteś oczami agenta pulpitu. Widzisz TĘ klatkę i opcjonalny wycinek.
Nie pamiętasz poprzednich tur. Nie wymyślaj historii.

Zasady:
- Współrzędne ZAWSZE normalized 0..1000 (lewy-górny = 0,0; prawy-dolny = 1000,1000).
- Kursor jest namalowany na obrazie. Użyj go jako kotwicy „gdzie jest mysz”.
- Najpierw pełny obraz: co to za aplikacja, jaki stan UI.
- Potem wycinek (jeśli jest): konkretne okienko / kontrolka.
- Klik, scroll, type podajesz w 0..1000 względem OBRAZU, do którego się odnosisz
  (full = cały ekran; crop = to okienko).
- Nie twierdź że skończyłeś zadanie. Skończenie ustala świadek / człowiek.
- Jeśli nie widzisz celu (np. przycisk scroll / Submit pod foldem) — powiedz
  SCROLL i w którą stronę, zamiast zgadywać klik.

Odpowiedź: zwięzły opis + jedna następna akcja.
"""


@dataclass
class WhereAmI:
    app: str = ""
    window_title: str = ""
    url_or_path: str = ""
    looking_for: str = ""
    last_effect: str = ""
    last_cost_tokens: int | None = None
    cursor_xn: int | None = None
    cursor_yn: int | None = None
    screen_w: int | None = None
    screen_h: int | None = None
    crop_box_n: tuple[int, int, int, int] | None = None
    crop_label: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def build_user_prompt(where: WhereAmI, goal: str = "", turn: int | None = None) -> str:
    lines: list[str] = []
    lines.append("Analizujesz TERAZ. User jest stateless — to cała pamięć tej tury.")
    if turn is not None:
        lines.append(f"Tura: {turn}")
    if goal.strip():
        lines.append("")
        lines.append("## cel (całe zadanie, nie plan)")
        lines.append(goal.strip())
    lines.append("")
    lines.append("## gdzie jestem")
    lines.append(f"- aplikacja: {where.app or '(nieznana — odczytaj z obrazu)'}")
    if where.window_title:
        lines.append(f"- okno: {where.window_title}")
    if where.url_or_path:
        lines.append(f"- url/path: {where.url_or_path}")
    if where.screen_w and where.screen_h:
        lines.append(f"- ekran px: {where.screen_w}x{where.screen_h}")
    if where.cursor_xn is not None and where.cursor_yn is not None:
        lines.append(
            f"- kursor (normalized 0..1000): xn={where.cursor_xn} yn={where.cursor_yn} — widoczny na screenshocie"
        )
    else:
        lines.append("- kursor: narysowany na screenshocie; odczytaj pozycję z pikseli")
    if where.looking_for:
        lines.append(f"- szukam: {where.looking_for}")
    if where.last_effect:
        lines.append(f"- ostatni skutek w świecie (nie czat): {where.last_effect}")
    if where.last_cost_tokens is not None:
        lines.append(f"- koszt poprzedniej tury: {where.last_cost_tokens} tokenów")
    if where.crop_box_n:
        x0, y0, x1, y1 = where.crop_box_n
        label = where.crop_label or "wycinek"
        lines.append(
            f"- wycinek '{label}' normalized względem PEŁNEGO ekranu: [{x0},{y0},{x1},{y1}]"
        )
    for k, v in where.extra.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## zadanie tej tury")
    lines.append("1. Opisz co widać na pełnym obrazie (applikacja, stan, fold).")
    lines.append("2. Jeśli jest drugi obraz — opisz TYLKO to okienko / miejsce.")
    lines.append("3. Podaj JEDNĄ następną akcję: CLICK xn yn | SCROLL up/down | TYPE tekst | WAIT | NEED_CROP tytuł_okna")
    lines.append("4. Jeśli celu nie widać (np. przycisk scroll / Submit poza kadrem) — SCROLL, nie zgaduj.")
    return "\n".join(lines) + "\n"


def example_chrome_costs() -> str:
    return build_user_prompt(
        WhereAmI(
            app="Google Chrome",
            window_title="Costs — X / Twitter",
            url_or_path="https://x.com/...",
            looking_for="przycisk scroll albo kontrolka dalej w dół listy costs",
            last_effect="otwarto costs, lista nie doscrollowana do końca",
            last_cost_tokens=2100,
            cursor_xn=512,
            cursor_yn=780,
            screen_w=1920,
            screen_h=1080,
            crop_box_n=(80, 60, 920, 940),
            crop_label="okno Chrome costs",
        ),
        goal="znaleźć i potwierdzić pozycję na liście costs, nie zamykać aplikacji",
        turn=7,
    )
