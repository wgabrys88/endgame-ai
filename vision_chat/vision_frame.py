"""Jedna klatka percepcji: pełny zrzut + opcjonalny wycinek.

Na Windowsie woła winapi (kursor ZAWSZE namalowany).
Na innych OS-ach rzuca jasny błąd przy capture — reszta pakietu działa.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Sequence

from .coords import box_to_px, px_box_to_n
from .stateless_prompt import WhereAmI, build_user_prompt


@dataclass
class Frame:
    full_png: bytes
    crop_png: bytes | None
    screen_w: int
    screen_h: int
    cursor_xn: int
    cursor_yn: int
    crop_box_n: tuple[int, int, int, int] | None
    crop_label: str
    windows: list[dict]
    user_prompt: str

    def full_b64(self) -> str:
        return base64.b64encode(self.full_png).decode("ascii")

    def crop_b64(self) -> str | None:
        return base64.b64encode(self.crop_png).decode("ascii") if self.crop_png else None


def _winapi():
    from . import winapi as w

    return w


def grab(
    *,
    goal: str = "",
    looking_for: str = "",
    last_effect: str = "",
    last_cost_tokens: int | None = None,
    app: str = "",
    window_title: str = "",
    url_or_path: str = "",
    crop_title: str | None = None,
    crop_box: Sequence[float] | None = None,
    target_w: int | None = None,
    target_h: int | None = None,
    turn: int | None = None,
    extra: dict | None = None,
) -> Frame:
    w = _winapi()
    try:
        w.init_dpi()
    except Exception:
        pass
    screen_w, screen_h = w.get_screen_size()
    tw = int(target_w or screen_w)
    th = int(target_h or screen_h)
    full_png, sw, sh = w.capture_screenshot_png(tw, th)
    screen_w, screen_h = sw, sh
    _cx, _cy, cursor_xn, cursor_yn = w.cursor_pos_normalized(screen_w, screen_h)
    windows = w.enum_windows()
    crop_png = None
    crop_box_n = None
    crop_label = ""

    picked = None
    if crop_title:
        picked = w.find_window(crop_title)
        if picked is None:
            for win in windows:
                if crop_title.lower() in (win.get("title") or "").lower():
                    picked = win
                    break
    if picked is None and window_title:
        picked = w.find_window(window_title)

    if picked:
        r = picked["rect"]
        crop_png, _cw, _ch = w.capture_region_png(r["left"], r["top"], r["right"], r["bottom"])
        ox, oy = w.get_virtual_origin()
        crop_box_n = px_box_to_n(
            r["left"] - ox, r["top"] - oy, r["right"] - ox, r["bottom"] - oy, screen_w, screen_h
        )
        crop_label = picked.get("title") or crop_title or window_title
        if not app:
            app = (picked.get("title") or "").split(" - ")[-1] or picked.get("title") or ""
        if not window_title:
            window_title = picked.get("title") or ""
    elif crop_box is not None:
        x0, y0, x1, y1 = box_to_px(crop_box, screen_w, screen_h)
        ox, oy = w.get_virtual_origin()
        crop_png, _cw, _ch = w.capture_region_png(ox + x0, oy + y0, ox + x1, oy + y1)
        crop_box_n = px_box_to_n(x0, y0, x1, y1, screen_w, screen_h)
        crop_label = "normalized-box"

    where = WhereAmI(
        app=app,
        window_title=window_title,
        url_or_path=url_or_path,
        looking_for=looking_for,
        last_effect=last_effect,
        last_cost_tokens=last_cost_tokens,
        cursor_xn=cursor_xn,
        cursor_yn=cursor_yn,
        screen_w=screen_w,
        screen_h=screen_h,
        crop_box_n=crop_box_n,
        crop_label=crop_label,
        extra=extra or {},
    )
    prompt = build_user_prompt(where, goal=goal, turn=turn)
    return Frame(
        full_png=full_png,
        crop_png=crop_png,
        screen_w=screen_w,
        screen_h=screen_h,
        cursor_xn=cursor_xn,
        cursor_yn=cursor_yn,
        crop_box_n=crop_box_n,
        crop_label=crop_label,
        windows=windows,
        user_prompt=prompt,
    )
