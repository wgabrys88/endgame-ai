from __future__ import annotations

from config import ZERO_INT, ONE_INT, TWO_INT, FLOAT_ONE
from config import (
    SIXEL_DEFAULT_PALETTE_SIZE, SIXEL_BAND_HEIGHT, SIXEL_RLE_MIN_RUN,
    SIXEL_CHAR_OFFSET, SIXEL_PERCENT_SCALE, SIXEL_RGB_MAX,
    SIXEL_DISTANCE_INITIAL, SIXEL_LORENZ_WIDTH, SIXEL_LORENZ_HEIGHT,
    SIXEL_STAGNATION_WIDTH, SIXEL_STAGNATION_HEIGHT, SIXEL_BACKGROUND_R,
    SIXEL_BACKGROUND_G, SIXEL_BACKGROUND_B, SIXEL_PALETTE_MIDPOINT,
    SIXEL_PALETTE_WARM_G, SIXEL_PALETTE_WARM_B, SIXEL_PALETTE_COOL_G,
    SIXEL_PALETTE_COOL_B, SIXEL_PALETTE_R_ATTENUATION,
    SIXEL_TRAIL_INTENSITY_BASE, SIXEL_TRAIL_INTENSITY_RANGE,
    SIXEL_TRAIL_COOL_R_RATIO, SIXEL_TRAIL_COOL_G_RATIO,
    SIXEL_TRAIL_WARM_G_RATIO, SIXEL_TRAIL_WARM_B_RATIO, SIXEL_CURRENT_R,
    SIXEL_CURRENT_G, SIXEL_CURRENT_B, STAGNATION_LOW_THRESHOLD,
    STAGNATION_MEDIUM_THRESHOLD, STAGNATION_HALT_LINE, STAGNATION_LOW_R,
    STAGNATION_LOW_G, STAGNATION_LOW_B, STAGNATION_MEDIUM_R,
    STAGNATION_MEDIUM_G, STAGNATION_MEDIUM_B, STAGNATION_HIGH_R,
    STAGNATION_HIGH_G, STAGNATION_HIGH_B, STAGNATION_HALT_R,
    STAGNATION_HALT_G, STAGNATION_HALT_B, STAGNATION_REFLECT_R,
    STAGNATION_REFLECT_G, STAGNATION_REFLECT_B,
)


def encode(pixels: list[list[tuple[int, int, int]]], width: int, height: int) -> str:
    palette: list[tuple[int, int, int]] = _extract_palette(pixels, width, height, SIXEL_DEFAULT_PALETTE_SIZE)
    color_map = _map_pixels_to_palette(pixels, width, height, palette)
    parts: list[str] = ["\x1bPq"]
    parts.append(f'"1;1;{width};{height}')
    for idx, (r, g, b) in enumerate(palette):
        pr = int(r / SIXEL_RGB_MAX * SIXEL_PERCENT_SCALE)
        pg = int(g / SIXEL_RGB_MAX * SIXEL_PERCENT_SCALE)
        pb = int(b / SIXEL_RGB_MAX * SIXEL_PERCENT_SCALE)
        parts.append(f"#{idx};2;{pr};{pg};{pb}")
    for band_start in range(ZERO_INT, height, SIXEL_BAND_HEIGHT):
        band_end = min(band_start + SIXEL_BAND_HEIGHT, height)
        band_height = band_end - band_start
        for color_idx in range(len(palette)):
            has_pixels = False
            row_data: list[str] = []
            for x in range(width):
                sixel_val = ZERO_INT
                for bit in range(band_height):
                    y = band_start + bit
                    if color_map[y][x] == color_idx:
                        sixel_val |= (ONE_INT << bit)
                        has_pixels = True
                row_data.append(chr(sixel_val + SIXEL_CHAR_OFFSET))
            if has_pixels:
                compressed = _rle_compress(row_data)
                parts.append(f"#{color_idx}{compressed}$")
        parts.append("-")
    parts.append("\x1b\\")
    return "".join(parts)


def _rle_compress(data: list[str]) -> str:
    if not data:
        return ""
    result: list[str] = []
    count = ONE_INT
    for i in range(ONE_INT, len(data)):
        if data[i] == data[i - ONE_INT]:
            count += ONE_INT
        else:
            if count >= SIXEL_RLE_MIN_RUN:
                result.append(f"!{count}{data[i - ONE_INT]}")
            else:
                result.append(data[i - ONE_INT] * count)
            count = ONE_INT
    if count >= SIXEL_RLE_MIN_RUN:
        result.append(f"!{count}{data[-ONE_INT]}")
    else:
        result.append(data[-ONE_INT] * count)
    return "".join(result)


def _extract_palette(pixels: list[list[tuple[int, int, int]]], width: int, height: int, max_colors: int) -> list[tuple[int, int, int]]:
    palette: list[tuple[int, int, int]] = []
    for i in range(max_colors):
        t = i / max(max_colors - ONE_INT, ONE_INT)
        if t < SIXEL_PALETTE_MIDPOINT:
            r = int(ZERO_INT + (SIXEL_RGB_MAX * (t * TWO_INT)))
            g = int(SIXEL_PALETTE_WARM_G - (SIXEL_PALETTE_COOL_G * (t * TWO_INT)))
            b = int(SIXEL_PALETTE_WARM_B * (ONE_INT - t * TWO_INT))
        else:
            t2 = (t - SIXEL_PALETTE_MIDPOINT) * TWO_INT
            r = int(SIXEL_RGB_MAX * (ONE_INT - t2 * SIXEL_PALETTE_R_ATTENUATION))
            g = int(SIXEL_PALETTE_COOL_G * (ONE_INT - t2))
            b = int(SIXEL_PALETTE_COOL_B * t2)
        palette.append((max(ZERO_INT, min(SIXEL_RGB_MAX, r)), max(ZERO_INT, min(SIXEL_RGB_MAX, g)), max(ZERO_INT, min(SIXEL_RGB_MAX, b))))
    return palette


def _map_pixels_to_palette(pixels: list[list[tuple[int, int, int]]], width: int, height: int, palette: list[tuple[int, int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            pr, pg, pb = pixels[y][x]
            best_idx = ZERO_INT
            best_dist = SIXEL_DISTANCE_INITIAL
            for idx, (cr, cg, cb) in enumerate(palette):
                d = (pr - cr) ** TWO_INT + (pg - cg) ** TWO_INT + (pb - cb) ** TWO_INT
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            row.append(best_idx)
        result.append(row)
    return result


def render_lorenz(x: float, y: float, z: float, history: list[tuple[float, float, float]], width: int = SIXEL_LORENZ_WIDTH, height: int = SIXEL_LORENZ_HEIGHT) -> str:
    bg = (SIXEL_BACKGROUND_R, SIXEL_BACKGROUND_G, SIXEL_BACKGROUND_B)
    pixels: list[list[tuple[int, int, int]]] = [[bg] * width for _ in range(height)]
    if not history:
        return encode(pixels, width, height)
    all_x = [p[ZERO_INT] for p in history]
    all_z = [p[TWO_INT] for p in history]
    min_x = min(all_x) - ONE_INT
    max_x = max(all_x) + ONE_INT
    min_z = min(all_z) - ONE_INT
    max_z = max(all_z) + ONE_INT
    range_x = max_x - min_x if max_x > min_x else FLOAT_ONE
    range_z = max_z - min_z if max_z > min_z else FLOAT_ONE
    total = len(history)
    for i, (hx, _hy, hz) in enumerate(history):
        px = int((hx - min_x) / range_x * (width - TWO_INT)) + ONE_INT
        py = height - ONE_INT - (int((hz - min_z) / range_z * (height - TWO_INT)) + ONE_INT)
        px = max(ZERO_INT, min(width - ONE_INT, px))
        py = max(ZERO_INT, min(height - ONE_INT, py))
        t = i / max(total - ONE_INT, ONE_INT)
        intensity = int(SIXEL_TRAIL_INTENSITY_BASE + SIXEL_TRAIL_INTENSITY_RANGE * t)
        if t < SIXEL_PALETTE_MIDPOINT:
            color = (int(intensity * SIXEL_TRAIL_COOL_R_RATIO), int(intensity * SIXEL_TRAIL_COOL_G_RATIO), intensity)
        else:
            color = (intensity, int(intensity * SIXEL_TRAIL_WARM_G_RATIO), int(intensity * SIXEL_TRAIL_WARM_B_RATIO))
        pixels[py][px] = color
    cx = int((x - min_x) / range_x * (width - TWO_INT)) + ONE_INT
    cy = height - ONE_INT - (int((z - min_z) / range_z * (height - TWO_INT)) + ONE_INT)
    cx = max(ONE_INT, min(width - TWO_INT, cx))
    cy = max(ONE_INT, min(height - TWO_INT, cy))
    for dy in range(-ONE_INT, TWO_INT):
        for dx in range(-ONE_INT, TWO_INT):
            pixels[cy + dy][cx + dx] = (SIXEL_CURRENT_R, SIXEL_CURRENT_G, SIXEL_CURRENT_B)
    return encode(pixels, width, height)


def render_stagnation(history: list[float], width: int = SIXEL_STAGNATION_WIDTH, height: int = SIXEL_STAGNATION_HEIGHT) -> str:
    bg = (SIXEL_BACKGROUND_R, SIXEL_BACKGROUND_G, SIXEL_BACKGROUND_B)
    pixels: list[list[tuple[int, int, int]]] = [[bg] * width for _ in range(height)]
    if not history:
        return encode(pixels, width, height)
    n = len(history)
    for i in range(n):
        x = int(i / max(n - ONE_INT, ONE_INT) * (width - ONE_INT))
        val = history[i]
        bar_h = int(val * (height - ONE_INT))
        if val < STAGNATION_LOW_THRESHOLD:
            color = (STAGNATION_LOW_R, STAGNATION_LOW_G, STAGNATION_LOW_B)
        elif val < STAGNATION_MEDIUM_THRESHOLD:
            color = (STAGNATION_MEDIUM_R, STAGNATION_MEDIUM_G, STAGNATION_MEDIUM_B)
        else:
            color = (STAGNATION_HIGH_R, STAGNATION_HIGH_G, STAGNATION_HIGH_B)
        for y_off in range(bar_h):
            py = height - ONE_INT - y_off
            if ZERO_INT <= py < height and ZERO_INT <= x < width:
                pixels[py][x] = color
        if i > ZERO_INT:
            prev_x = int((i - ONE_INT) / max(n - ONE_INT, ONE_INT) * (width - ONE_INT))
            prev_val = history[i - ONE_INT]
            prev_bar = int(prev_val * (height - ONE_INT))
            for fill_x in range(prev_x + ONE_INT, x):
                t = (fill_x - prev_x) / max(x - prev_x, ONE_INT)
                interp_h = int(prev_bar + (bar_h - prev_bar) * t)
                for y_off in range(interp_h):
                    py = height - ONE_INT - y_off
                    if ZERO_INT <= py < height and ZERO_INT <= fill_x < width:
                        pixels[py][fill_x] = color
    threshold_y = height - ONE_INT - int(STAGNATION_HALT_LINE * (height - ONE_INT))
    for x in range(width):
        if ZERO_INT <= threshold_y < height:
            pixels[threshold_y][x] = (STAGNATION_HALT_R, STAGNATION_HALT_G, STAGNATION_HALT_B)
    reflect_y = height - ONE_INT - int(STAGNATION_LOW_THRESHOLD * (height - ONE_INT))
    for x in range(ZERO_INT, width, SIXEL_RLE_MIN_RUN):
        if ZERO_INT <= reflect_y < height:
            pixels[reflect_y][x] = (STAGNATION_REFLECT_R, STAGNATION_REFLECT_G, STAGNATION_REFLECT_B)
    return encode(pixels, width, height)
