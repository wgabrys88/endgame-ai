"""The eyes (seated tool). A fresh screen photograph is laid before you EVERY turn in
[environment] as an image attached to THIS request: the full desktop, with the system cursor
painted onto it. Remove this file and the organism loses its eyes (it keeps only the UI tree).

Offered by bare name in the actor namespace:
  vision.grab(crop_title=None) - re-photograph now; returns {screen_w, screen_h, cursor_xn,
                                                         cursor_yn, crop_label}

Use the image to orient: which app is open, what state its UI is in, and what sits BELOW the
visible fold (which the UI tree reads as 'absent'). If a control is off-fold, SCROLL then
re-look; never claim a control is missing when it may simply be below the fold. The image is
part of [environment], not a separate plan.
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
    if frame.crop_png and frame.crop_box_n:
        note += ", crop '%s' [%s]" % (
            frame.crop_label or "window",
            ",".join(str(int(x)) for x in frame.crop_box_n),
        )
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
    def grab(crop_title=None):
        global _FRAME
        from vision_chat.vision_frame import grab as _grab

        _FRAME = _grab(crop_title=crop_title)
        return {
            "screen_w": _FRAME.screen_w,
            "screen_h": _FRAME.screen_h,
            "cursor_xn": _FRAME.cursor_xn,
            "cursor_yn": _FRAME.cursor_yn,
            "crop_label": _FRAME.crop_label,
        }

    return {"vision": SimpleNamespace(grab=grab)}
