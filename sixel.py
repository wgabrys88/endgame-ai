from __future__ import annotations


def encode(pixels: list[list[tuple[int, int, int]]], width: int, height: int) -> str:
    palette: list[tuple[int, int, int]] = _extract_palette(pixels, width, height, 64)
    color_map = _map_pixels_to_palette(pixels, width, height, palette)
    parts: list[str] = ["\x1bPq"]
    parts.append(f'"1;1;{width};{height}')
    for idx, (r, g, b) in enumerate(palette):
        pr = int(r / 255 * 100)
        pg = int(g / 255 * 100)
        pb = int(b / 255 * 100)
        parts.append(f"#{idx};2;{pr};{pg};{pb}")
    for band_start in range(0, height, 6):
        band_end = min(band_start + 6, height)
        band_height = band_end - band_start
        for color_idx in range(len(palette)):
            has_pixels = False
            row_data: list[str] = []
            for x in range(width):
                sixel_val = 0
                for bit in range(band_height):
                    y = band_start + bit
                    if color_map[y][x] == color_idx:
                        sixel_val |= (1 << bit)
                        has_pixels = True
                row_data.append(chr(sixel_val + 63))
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
    count = 1
    for i in range(1, len(data)):
        if data[i] == data[i - 1]:
            count += 1
        else:
            if count >= 4:
                result.append(f"!{count}{data[i - 1]}")
            else:
                result.append(data[i - 1] * count)
            count = 1
    if count >= 4:
        result.append(f"!{count}{data[-1]}")
    else:
        result.append(data[-1] * count)
    return "".join(result)


def _extract_palette(pixels: list[list[tuple[int, int, int]]], width: int, height: int, max_colors: int) -> list[tuple[int, int, int]]:
    palette: list[tuple[int, int, int]] = []
    for i in range(max_colors):
        t = i / max(max_colors - 1, 1)
        if t < 0.5:
            r = int(0 + (255 * (t * 2)))
            g = int(200 - (100 * (t * 2)))
            b = int(50 * (1 - t * 2))
        else:
            t2 = (t - 0.5) * 2
            r = int(255 * (1 - t2 * 0.3))
            g = int(100 * (1 - t2))
            b = int(200 * t2)
        palette.append((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
    return palette


def _map_pixels_to_palette(pixels: list[list[tuple[int, int, int]]], width: int, height: int, palette: list[tuple[int, int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            pr, pg, pb = pixels[y][x]
            best_idx = 0
            best_dist = 999999
            for idx, (cr, cg, cb) in enumerate(palette):
                d = (pr - cr) ** 2 + (pg - cg) ** 2 + (pb - cb) ** 2
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            row.append(best_idx)
        result.append(row)
    return result


def render_lorenz(x: float, y: float, z: float, history: list[tuple[float, float, float]], width: int = 200, height: int = 60) -> str:
    bg = (10, 10, 20)
    pixels: list[list[tuple[int, int, int]]] = [[bg] * width for _ in range(height)]
    if not history:
        return encode(pixels, width, height)
    all_x = [p[0] for p in history]
    all_z = [p[2] for p in history]
    min_x = min(all_x) - 1
    max_x = max(all_x) + 1
    min_z = min(all_z) - 1
    max_z = max(all_z) + 1
    range_x = max_x - min_x if max_x > min_x else 1.0
    range_z = max_z - min_z if max_z > min_z else 1.0
    total = len(history)
    for i, (hx, _hy, hz) in enumerate(history):
        px = int((hx - min_x) / range_x * (width - 2)) + 1
        py = height - 1 - (int((hz - min_z) / range_z * (height - 2)) + 1)
        px = max(0, min(width - 1, px))
        py = max(0, min(height - 1, py))
        t = i / max(total - 1, 1)
        intensity = int(80 + 175 * t)
        if t < 0.5:
            color = (int(intensity * 0.3), int(intensity * 0.8), intensity)
        else:
            color = (intensity, int(intensity * 0.4), int(intensity * 0.7))
        pixels[py][px] = color
    cx = int((x - min_x) / range_x * (width - 2)) + 1
    cy = height - 1 - (int((z - min_z) / range_z * (height - 2)) + 1)
    cx = max(1, min(width - 2, cx))
    cy = max(1, min(height - 2, cy))
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            pixels[cy + dy][cx + dx] = (255, 255, 255)
    return encode(pixels, width, height)


def render_stagnation(history: list[float], width: int = 200, height: int = 40) -> str:
    bg = (10, 10, 20)
    pixels: list[list[tuple[int, int, int]]] = [[bg] * width for _ in range(height)]
    if not history:
        return encode(pixels, width, height)
    n = len(history)
    for i in range(n):
        x = int(i / max(n - 1, 1) * (width - 1))
        val = history[i]
        bar_h = int(val * (height - 1))
        if val < 0.3:
            color = (50, 200, 80)
        elif val < 0.6:
            color = (220, 180, 30)
        else:
            color = (220, 50, 50)
        for y_off in range(bar_h):
            py = height - 1 - y_off
            if 0 <= py < height and 0 <= x < width:
                pixels[py][x] = color
        if i > 0:
            prev_x = int((i - 1) / max(n - 1, 1) * (width - 1))
            prev_val = history[i - 1]
            prev_bar = int(prev_val * (height - 1))
            for fill_x in range(prev_x + 1, x):
                t = (fill_x - prev_x) / max(x - prev_x, 1)
                interp_h = int(prev_bar + (bar_h - prev_bar) * t)
                for y_off in range(interp_h):
                    py = height - 1 - y_off
                    if 0 <= py < height and 0 <= fill_x < width:
                        pixels[py][fill_x] = color
    threshold_y = height - 1 - int(0.95 * (height - 1))
    for x in range(width):
        if 0 <= threshold_y < height:
            pixels[threshold_y][x] = (100, 30, 30)
    reflect_y = height - 1 - int(0.3 * (height - 1))
    for x in range(0, width, 4):
        if 0 <= reflect_y < height:
            pixels[reflect_y][x] = (60, 60, 100)
    return encode(pixels, width, height)
