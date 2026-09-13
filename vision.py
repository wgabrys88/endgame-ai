"""The eyes and the pixel-hand (seated tool). A fresh screen PHOTOGRAPH is laid before you EVERY
turn in [environment] as an image attached to THIS request: the full desktop, with the system
cursor painted onto it. Remove this file and the organism loses its eyes.

Offered by bare name in the actor namespace (coordinates are the SAME 0..1000 grid as the
cursor xn/yn reported in [environment]; the taskbar is the strip along the bottom edge, its
left end x~0; the Start button is the leftmost icon on that strip, its centre near
xn~15, yn~975 on a 1920x1080 screen):
  vision.click(xn, yn) - move the cursor to (xn, yn) and left-click there NOW
  vision.move(xn, yn)  - move the cursor to (xn, yn) without clicking
  vision.scroll(clicks=1, down=True) - wheel-scroll in place (down/up)
  vision.grab()        - re-photograph now; returns {screen_w, screen_h, cursor_xn, cursor_yn}
  vision.windows()     - read-only: visible top-level windows now, each {title, rect}

The IMAGE is your primary sensor: LOOK at it, locate what you need by its position in the
photograph, and click by its (xn, yn) with vision.click. When a target sits BELOW the visible
fold, SCROLL then re-look; never claim a control is missing when it may simply be below the fold.
The witness sees the same kind of image and judges by the effect it independently observes.
"""
from __future__ import annotations

from types import SimpleNamespace

_FRAME = None


def _capture(bb, cfg):
    from vision_chat.vision_frame import grab

    obs = (cfg or {}).get("observation", {}) if cfg else {}
    tw = obs.get("vision_target_w") or None
    th = obs.get("vision_target_h") or None
    goal = (bb.get("goal") or "").strip() if bb is not None else ""
    return grab(
        goal=goal,
        target_w=int(tw) if tw else None,
        target_h=int(th) if th else None,
    )


def environment(bb, cfg=None):
    """Kernel perception hook: photograph the screen and attach it to the next request."""
    global _FRAME
    try:
        frame = _capture(bb, cfg)
    except Exception:
        _FRAME = None
        return
    _FRAME = frame
    note = "VISION (image attached): screen %dx%d, cursor xn=%d yn=%d" % (
        frame.screen_w, frame.screen_h, frame.cursor_xn, frame.cursor_yn)
    titles = [w.get("title") for w in (frame.windows or []) if (w.get("title") or "").strip()]
    if titles:
        note += "\nvisible windows: " + "; ".join(titles[:20])
    existing = bb.get("environment") or ""
    bb.set("environment", (existing + "\n\n" + note).strip())


def vision_input():
    """Kernel transport hook: the image content-parts to attach, or None when no frame."""
    global _FRAME
    if _FRAME is None:
        return None
    parts = [{"type": "image_url",
              "image_url": {"url": "data:image/png;base64," + _FRAME.full_b64()}}]
    if _FRAME.crop_png:
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:image/png;base64," + _FRAME.crop_b64()}})
    return parts


def namespace(context=None):
    from vision_chat import winapi as w

    ctx = context or {}
    kind = ctx.get("kind", "actor")

    def grab(crop_title=None):
        global _FRAME
        from vision_chat.vision_frame import grab as _grab

        _FRAME = _grab(crop_title=crop_title)
        return {
            "screen_w": _FRAME.screen_w,
            "screen_h": _FRAME.screen_h,
            "cursor_xn": _FRAME.cursor_xn,
            "cursor_yn": _FRAME.cursor_yn,
        }

    def windows():
        global _FRAME
        src = (_FRAME.windows if _FRAME is not None else None)
        if not src:
            src = w.enum_windows()
        return [{"title": x.get("title") or "", "rect": x.get("rect") or {}} for x in src]

    ns = {"grab": grab, "windows": windows}
    if kind == "witness":
        return {"vision": SimpleNamespace(**ns)}

    def move(xn, yn):
        sw, sh = w.move_mouse_norm(xn, yn)
        return {"ok": True, "xn": int(xn), "yn": int(yn), "screen": [sw, sh]}

    def click(xn, yn):
        sw, sh = w.move_mouse_norm(xn, yn)
        w.click_mouse()
        return {"ok": True, "xn": int(xn), "yn": int(yn), "screen": [sw, sh]}

    def scroll(clicks=1, down=True):
        if down:
            w.scroll_down(int(clicks))
        else:
            w.scroll_up(int(clicks))
        return {"ok": True, "clicks": int(clicks), "down": bool(down)}

    ns["click"] = click
    ns["move"] = move
    ns["scroll"] = scroll
    return {"vision": SimpleNamespace(**ns)}
