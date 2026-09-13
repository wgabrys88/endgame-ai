"""Normalized coordinates.

Dwie skale, obie akceptowane na wejściu:

- 0..1     — ułamek ekranu / okna (lewy-górny = 0,0)
- 0..1000  — skala Franza / windows-ai-agent-toolset (xn, yn)

Wyjście do modelu ZAWSZE w 0..1000 (int), bo mały model lepiej
trzyma trzy cyfry niż ułamki. Pixel = round(n/1000 * (size-1)).
"""
from __future__ import annotations

from typing import Sequence


Norm = float | int


def _to_thousand(v: Norm) -> int:
    x = float(v)
    if 0.0 <= x <= 1.0:
        x = x * 1000.0
    if x < 0:
        x = 0.0
    elif x > 1000.0:
        x = 1000.0
    return int(round(x))


def clamp_n(v: Norm) -> int:
    return _to_thousand(v)


def n_to_px(n: Norm, size: int) -> int:
    if size <= 1:
        return 0
    return int(round((_to_thousand(n) / 1000.0) * (size - 1)))


def px_to_n(px: int, size: int) -> int:
    if size <= 1:
        return 0
    n = int(round((px / float(size - 1)) * 1000.0))
    if n < 0:
        return 0
    if n > 1000:
        return 1000
    return n


def box_to_px(
    box: Sequence[Norm],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    """box = (x0, y0, x1, y1) w 0..1 albo 0..1000 → piksele inkluzywne-lewo, ekskluzywne-prawo."""
    if len(box) != 4:
        raise ValueError("box must be 4 numbers: x0 y0 x1 y1")
    x0 = n_to_px(box[0], width)
    y0 = n_to_px(box[1], height)
    x1 = n_to_px(box[2], width) + 1
    y1 = n_to_px(box[3], height) + 1
    if x1 <= x0:
        x1 = min(width, x0 + 1)
    if y1 <= y0:
        y1 = min(height, y0 + 1)
    x0 = max(0, min(x0, width))
    y0 = max(0, min(y0, height))
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    return x0, y0, x1, y1


def px_box_to_n(
    left: int, top: int, right: int, bottom: int, width: int, height: int
) -> tuple[int, int, int, int]:
    return (
        px_to_n(left, width),
        px_to_n(top, height),
        px_to_n(max(left, right - 1), width),
        px_to_n(max(top, bottom - 1), height),
    )


def format_n(n: int) -> str:
    return f"{int(n):04d}" if False else f"{int(n)}"
