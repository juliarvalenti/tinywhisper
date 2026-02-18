#!/usr/bin/env python3
"""Generate TinyWhisper macOS app icon: feather with sound ripples.

A quill feather (tiny/light) with sound ripple arcs emanating from the tip,
on a dark rounded rectangle background. Coral (#FF6B6B) on dark (#1E1E1E).
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent.parent
ICONSET_DIR = ROOT / "TinyWhisper.iconset"

ICON_SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def draw_icon(size: int) -> Image.Image:
    """Draw the feather + ripples icon at the given size."""
    # Work at 4x for antialiasing, then downscale
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background: white rounded square (macOS Big Sur+ style)
    margin = int(s * 0.02)
    radius = int(s * 0.22)
    bg_color = (255, 255, 255, 255)
    d.rounded_rectangle([margin, margin, s - margin, s - margin], radius=radius, fill=bg_color)

    # Subtle border
    border_color = (200, 200, 200, 80)
    d.rounded_rectangle(
        [margin, margin, s - margin, s - margin],
        radius=radius, outline=border_color, width=max(1, s // 200),
    )

    feather_color = (120, 120, 120, 255)  # medium gray
    cx, cy = s * 0.50 + (s / 256) * 10, s * 0.50  # nudged right ~10px at 256

    # --- Feather ---
    feather_len = s * 0.62
    feather_width = s * 0.17
    angle = math.radians(-40)  # tilted up-left

    # Shaft endpoints
    tip_x = cx - math.cos(angle) * feather_len * 0.5
    tip_y = cy - math.sin(angle) * feather_len * 0.5
    base_x = cx + math.cos(angle) * feather_len * 0.5
    base_y = cy + math.sin(angle) * feather_len * 0.5

    # Perpendicular for width
    perp_x = -math.sin(angle)
    perp_y = math.cos(angle)

    # Build feather outline as a leaf/quill shape
    points = []
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        px = tip_x + (base_x - tip_x) * t
        py = tip_y + (base_y - tip_y) * t
        w = math.sin(t * math.pi) * feather_width
        if t < 0.15:
            w *= t / 0.15
        points.append((px + perp_x * w * 0.6, py + perp_y * w * 0.6))

    for i in range(steps, -1, -1):
        t = i / steps
        px = tip_x + (base_x - tip_x) * t
        py = tip_y + (base_y - tip_y) * t
        w = math.sin(t * math.pi) * feather_width
        if t < 0.15:
            w *= t / 0.15
        points.append((px - perp_x * w * 0.4, py - perp_y * w * 0.4))

    d.polygon(points, fill=feather_color)

    # Central shaft (slightly darker)
    shaft_color = (90, 90, 90, 180)
    shaft_w = max(2, s // 100)
    d.line([(tip_x, tip_y), (base_x, base_y)], fill=shaft_color, width=shaft_w)

    # Quill tip extension
    quill_ext = s * 0.08
    quill_end_x = base_x + math.cos(angle) * quill_ext
    quill_end_y = base_y + math.sin(angle) * quill_ext
    d.line(
        [(base_x, base_y), (quill_end_x, quill_end_y)],
        fill=feather_color, width=max(1, shaft_w // 2),
    )

    # --- Sound ripples from feather tip ---
    ripple_cx = tip_x + s * 0.04
    ripple_cy = tip_y - s * 0.01
    ripple_rgb = (120, 120, 120)

    for i, r in enumerate([s * 0.10, s * 0.17, s * 0.24]):
        alpha = int(180 - i * 50)
        arc_w = max(2, int(s * 0.015))
        color = (*ripple_rgb, alpha)
        bbox = [ripple_cx - r, ripple_cy - r, ripple_cx + r, ripple_cy + r]
        d.arc(bbox, start=200, end=310, fill=color, width=arc_w)

    # Apply rounded rect mask for transparent corners
    mask = Image.new("L", (s, s), 0)
    mask_d = ImageDraw.Draw(mask)
    mask_d.rounded_rectangle([margin, margin, s - margin, s - margin], radius=radius, fill=255)
    img.putalpha(mask)

    # Downscale with high-quality resampling
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main():
    ICONSET_DIR.mkdir(exist_ok=True)
    for filename, px in ICON_SIZES:
        icon = draw_icon(px)
        icon.save(str(ICONSET_DIR / filename), "PNG")
        print(f"  {filename} ({px}x{px})")
    print(f"\nIconset written to {ICONSET_DIR}")


if __name__ == "__main__":
    main()
