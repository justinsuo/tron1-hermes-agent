"""Render a procedural gauge PNG into assets/gauge.png with a ground-truth label.

Called at sim startup to randomize the gauge reading each session. The ground
truth is written to assets/gauge_truth.json so the self-play grader can score
read-wall-gauge attempts.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for p in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def render(out_png: Path, out_json: Path, seed: int | None = None) -> dict:
    if seed is not None:
        random.seed(seed)
    size = 512
    img = Image.new("RGB", (size, size), (235, 235, 220))
    d = ImageDraw.Draw(img)

    cx = cy = size // 2
    r = size // 2 - 20
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(40, 40, 40), width=8)
    d.ellipse([cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10], fill=(245, 245, 235))

    units, vmin, vmax = random.choice([
        ("PSI", 0.0, 200.0),
        ("BAR", 0.0, 20.0),
        ("°C", -20.0, 120.0),
        ("V", 0.0, 30.0),
    ])
    value = random.uniform(vmin + 0.1 * (vmax - vmin), vmin + 0.9 * (vmax - vmin))

    sweep = 240.0
    start = -sweep / 2
    font = _font(32)
    for i in range(11):
        t = i / 10
        deg = start + t * sweep
        rad = math.radians(deg - 90)
        x1 = cx + math.cos(rad) * (r - 18)
        y1 = cy + math.sin(rad) * (r - 18)
        x2 = cx + math.cos(rad) * (r - 50)
        y2 = cy + math.sin(rad) * (r - 50)
        d.line([(x1, y1), (x2, y2)], fill=(30, 30, 30), width=4)
        label = f"{vmin + t * (vmax - vmin):.0f}"
        lx = cx + math.cos(rad) * (r - 90) - 18
        ly = cy + math.sin(rad) * (r - 90) - 18
        d.text((lx, ly), label, fill=(20, 20, 20), font=font)

    # Units label
    units_font = _font(40)
    d.text((cx - 30, cy + 80), units, fill=(40, 40, 40), font=units_font)

    # Needle
    frac = (value - vmin) / (vmax - vmin)
    needle_deg = start + frac * sweep
    rad = math.radians(needle_deg - 90)
    nx = cx + math.cos(rad) * (r - 30)
    ny = cy + math.sin(rad) * (r - 30)
    d.line([(cx, cy), (nx, ny)], fill=(180, 30, 30), width=8)
    d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(20, 20, 20))

    img.save(out_png)

    truth = {
        "value": round(value, 2),
        "units": units,
        "min": vmin,
        "max": vmax,
        "needle_deg": round(needle_deg, 2),
        "seed": seed,
    }
    out_json.write_text(json.dumps(truth))
    return truth


def render_three(root: Path, base_seed: int | None = None) -> dict:
    """Render three gauges (N, E, W) each with a different seed. Write a
    combined truth file `gauges_truth.json`."""
    root.mkdir(exist_ok=True)
    truths: dict[str, dict] = {}
    for wall in ("N", "E", "W"):
        seed = (base_seed or random.randint(0, 10**6)) ^ hash(wall) & 0xFFFF
        t = render(root / f"gauge_{wall}.png",
                   root / f"gauge_{wall}_truth.json",
                   seed=seed)
        truths[wall] = t
    (root / "gauges_truth.json").write_text(
        __import__("json").dumps(truths, indent=2))
    # Also keep the legacy single-gauge file so old code still works
    render(root / "gauge.png", root / "gauge_truth.json",
           seed=base_seed if base_seed is not None else random.randint(0, 10**6))
    return truths


if __name__ == "__main__":
    root = Path(__file__).parent / "assets"
    root.mkdir(exist_ok=True)
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randint(0, 10**6)
    truths = render_three(root, base_seed=seed)
    for wall, t in truths.items():
        print(f"gauge {wall}: {t['value']} {t['units']}")
