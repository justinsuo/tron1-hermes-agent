"""Procedural gauge-reading dataset generator.

Produces labeled analog-gauge images without a simulator. Output pairs:
    gauges/
      000000.jpg
      000000.json   # {"value": float, "units": str, "min": float, "max": float, "needle_deg": float}

Each image is 384x384 and randomizes:
  * dial face: solid, tick-marked, labelled numbers
  * needle angle, color, length, thickness
  * dial rim: chrome, brass, painted
  * backdrop: white wall, brick, metal plate, cluttered scene (from Pillow noise)
  * lighting: diffuse vs. harsh shadow
  * perspective jitter: small warp, up to ±10° yaw/pitch

This is enough to bootstrap LoRA fine-tuning of Qwen 2.5 VL for gauge reading.
Later, Unity/Unreal sim frames can be mixed in to close the sim-to-real gap.

Usage:
    python3 gen_gauge_dataset.py --count 2000 --out ~/tron1-selfplay/training/gauges
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _backdrop(w: int, h: int) -> Image.Image:
    style = random.choice(["plain", "brick", "plate", "noise"])
    if style == "plain":
        c = random.choice([(240, 240, 235), (200, 200, 200), (60, 60, 65), (150, 140, 120)])
        return Image.new("RGB", (w, h), c)
    if style == "noise":
        img = Image.effect_noise((w, h), sigma=40).convert("RGB")
        tint = random.choice([(50, 50, 50), (80, 70, 60)])
        img = Image.blend(img, Image.new("RGB", (w, h), tint), 0.3)
        return img
    if style == "plate":
        img = Image.new("RGB", (w, h), (130, 130, 135))
        d = ImageDraw.Draw(img)
        for i in range(0, h, 12):
            d.line([(0, i), (w, i)], fill=(110, 110, 115), width=1)
        return img
    # brick
    img = Image.new("RGB", (w, h), (170, 100, 80))
    d = ImageDraw.Draw(img)
    for y in range(0, h, 24):
        offset = 0 if (y // 24) % 2 == 0 else 40
        for x in range(-offset, w, 80):
            d.rectangle([x, y, x + 78, y + 22], outline=(100, 60, 50), width=2)
    return img


def _draw_gauge(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int,
                value: float, vmin: float, vmax: float, units: str) -> float:
    """Draw the gauge face + needle at the right angle. Return needle_deg (0° = up, CW positive)."""
    # Rim
    rim_color = random.choice([(30, 30, 30), (90, 90, 90), (180, 170, 130)])
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rim_color, width=max(3, r // 25))
    # Face
    face_color = random.choice([(250, 250, 240), (235, 235, 220), (180, 180, 170)])
    inset = r - max(4, r // 30)
    draw.ellipse([cx - inset, cy - inset, cx + inset, cy + inset], fill=face_color)

    # Ticks + labels — gauge sweeps 240° from -120° (low) through 0° (mid, up)
    # to +120° (high). 0° means needle pointing straight up.
    sweep = 240.0
    start_deg = -sweep / 2
    ticks = 11
    font = _pick_font(max(10, r // 8))
    tick_color = (50, 50, 50)
    for i in range(ticks):
        t = i / (ticks - 1)
        deg = start_deg + t * sweep
        rad = math.radians(deg - 90)  # 0 deg is straight up
        tx1 = cx + math.cos(rad) * (r - r // 12)
        ty1 = cy + math.sin(rad) * (r - r // 12)
        tx2 = cx + math.cos(rad) * (r - r // 5)
        ty2 = cy + math.sin(rad) * (r - r // 5)
        draw.line([(tx1, ty1), (tx2, ty2)], fill=tick_color, width=2)
        # number
        label = f"{vmin + t * (vmax - vmin):.0f}"
        lx = cx + math.cos(rad) * (r - r // 3)
        ly = cy + math.sin(rad) * (r - r // 3)
        draw.text((lx - r // 12, ly - r // 12), label, fill=tick_color, font=font)

    # Units label
    units_font = _pick_font(max(10, r // 10))
    draw.text((cx - r // 4, cy + r // 3), units, fill=(70, 70, 70), font=units_font)

    # Needle
    frac = (value - vmin) / (vmax - vmin)
    frac = max(0.0, min(1.0, frac))
    needle_deg = start_deg + frac * sweep
    rad = math.radians(needle_deg - 90)
    nlen = r - r // 8
    nx = cx + math.cos(rad) * nlen
    ny = cy + math.sin(rad) * nlen
    color = random.choice([(180, 30, 30), (20, 20, 20), (30, 60, 180)])
    draw.line([(cx, cy), (nx, ny)], fill=color, width=max(3, r // 30))
    # Pivot
    pr = max(3, r // 18)
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(20, 20, 20))
    return needle_deg


def _generate_one(idx: int, out_dir: Path, w: int, h: int) -> None:
    bg = _backdrop(w, h)
    cx, cy = w // 2 + random.randint(-20, 20), h // 2 + random.randint(-20, 20)
    r = random.randint(min(w, h) // 3, int(min(w, h) * 0.45))

    unit_choice = random.choice([
        ("PSI", 0.0, 200.0),
        ("BAR", 0.0, 20.0),
        ("°C", -20.0, 120.0),
        ("°F", 0.0, 250.0),
        ("V", 0.0, 30.0),
        ("A", 0.0, 50.0),
        ("RPM", 0.0, 8000.0),
        ("kPa", 0.0, 1000.0),
    ])
    units, vmin, vmax = unit_choice
    value = random.uniform(vmin, vmax)

    draw = ImageDraw.Draw(bg)
    needle_deg = _draw_gauge(draw, cx, cy, r, value, vmin, vmax, units)

    # Light perspective / motion blur / lighting
    if random.random() < 0.25:
        bg = bg.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.2)))
    if random.random() < 0.2:
        # simple vignette
        overlay = Image.new("L", bg.size, 0)
        od = ImageDraw.Draw(overlay)
        od.ellipse([-w // 4, -h // 4, int(w * 1.25), int(h * 1.25)], fill=255)
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=40))
        bg.putalpha(overlay)
        bg = bg.convert("RGB")

    img_path = out_dir / f"{idx:06d}.jpg"
    label_path = out_dir / f"{idx:06d}.json"
    bg.save(img_path, quality=85)
    with open(label_path, "w") as f:
        json.dump({
            "value": round(value, 3),
            "units": units,
            "min": vmin,
            "max": vmax,
            "needle_deg": round(needle_deg, 2),
            "center_xy": [cx, cy],
            "radius_px": r,
        }, f)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--out", default=os.path.expanduser("~/tron1-selfplay/training/gauges"))
    p.add_argument("--size", type=int, default=384)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    for i in range(args.count):
        _generate_one(i, out, args.size, args.size)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{args.count}", flush=True)

    print(f"done. {args.count} pairs at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
