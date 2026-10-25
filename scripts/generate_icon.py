"""Draws the Lizard icon (a gecko basking on a warm background) and writes it to lizard/assets/.

The generated files are committed, so this only needs to run after changing the
design. It needs Pillow (see requirements-dev.txt): ``python scripts/generate_icon.py``
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "lizard" / "assets"

CANVAS = 1024  # drawn large, then scaled down for smooth edges
BACKGROUND_TOP = (255, 184, 64)
BACKGROUND_BOTTOM = (214, 64, 36)
GECKO = (24, 92, 56)
SPOTS = (92, 168, 96)
EYE = (255, 226, 120)
PUPIL = (20, 30, 24)
SIZES = (16, 24, 32, 48, 64, 128, 256)

Point = tuple[float, float]


def _rounded_background() -> Image.Image:
    column = Image.new("RGBA", (1, CANVAS))
    column.putdata([
        tuple(round(a + (b - a) * y / (CANVAS - 1)) for a, b in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM)) + (255,)
        for y in range(CANVAS)
    ])
    gradient = column.resize((CANVAS, CANVAS), Image.Resampling.NEAREST)
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, CANVAS - 40, CANVAS - 40), radius=210, fill=255)
    background = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    background.paste(gradient, mask=mask)
    return background


def _disc(draw: ImageDraw.ImageDraw, center: Point, radius: float, fill: tuple[int, ...]) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _limb(draw: ImageDraw.ImageDraw, points: list[Point], width: float, fill: tuple[int, ...]) -> None:
    """Straight segments with rounded joints."""
    draw.line(points, fill=fill, width=round(width), joint="curve")
    for point in points:
        _disc(draw, point, width / 2, fill)


def _catmull_rom(points: list[Point], steps: int = 40) -> list[Point]:
    """A smooth curve through ``points``."""
    padded = [points[0], *points, points[-1]]
    curve = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1:i + 3]
        for step in range(steps):
            t = step / steps
            curve.append(tuple(
                0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3)
                for a, b, c, d in zip(p0, p1, p2, p3)
            ))
    curve.append(points[-1])
    return curve


def _foot(draw: ImageDraw.ImageDraw, wrist: Point, direction: float, color: tuple[int, ...]) -> None:
    """Four splayed toes ending in round gecko toe pads, fanned around ``direction`` (degrees)."""
    for spread in (-54, -18, 18, 54):
        angle = math.radians(direction + spread)
        tip = (wrist[0] + math.cos(angle) * 62, wrist[1] + math.sin(angle) * 62)
        _limb(draw, [wrist, tip], 20, color)
        _disc(draw, tip, 19, color)


def draw_gecko() -> Image.Image:
    layer = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx = 470

    # Tail: a curl that thins towards the tip.
    tail = _catmull_rom([(cx, 640), (cx + 10, 760), (cx + 80, 850), (cx + 190, 870), (cx + 290, 820),
                         (cx + 320, 720), (cx + 270, 650), (cx + 205, 665)])
    for i, point in enumerate(tail):
        _disc(draw, point, 56 - 44 * i / (len(tail) - 1), GECKO)

    # Legs: shoulder/hip, elbow/knee, wrist; then the toes.
    for side in (-1, 1):
        front = [(cx + side * 60, 370), (cx + side * 170, 330), (cx + side * 200, 235)]
        back = [(cx + side * 55, 600), (cx + side * 165, 640), (cx + side * 185, 745)]
        _limb(draw, front, 54, GECKO)
        _limb(draw, back, 58, GECKO)
        _foot(draw, front[-1], -90 - side * 30, GECKO)
        _foot(draw, back[-1], 90 + side * 30, GECKO)

    # Body, neck and head.
    draw.ellipse((cx - 108, 300, cx + 108, 660), fill=GECKO)
    draw.ellipse((cx - 62, 260, cx + 62, 380), fill=GECKO)
    draw.ellipse((cx - 98, 130, cx + 98, 330), fill=GECKO)
    draw.ellipse((cx - 70, 95, cx + 70, 230), fill=GECKO)

    # Markings along the back, and the eyes.
    for y, size in ((420, 26), (500, 30), (580, 24)):
        _disc(draw, (cx - 40, y), size, SPOTS)
        _disc(draw, (cx + 40, y + 30), size, SPOTS)
    for side in (-1, 1):
        eye = (cx + side * 70, 200)
        _disc(draw, eye, 30, EYE)
        draw.ellipse((eye[0] - 7, eye[1] - 22, eye[0] + 7, eye[1] + 22), fill=PUPIL)
    return layer


def _fit(layer: Image.Image, box: int) -> Image.Image:
    """Scale the drawing so it fits a centered ``box`` x ``box`` square, clear of the rounded corners."""
    cropped = layer.crop(layer.getchannel("A").getbbox())
    scale = box / max(cropped.size)
    cropped = cropped.resize((round(cropped.width * scale), round(cropped.height * scale)), Image.Resampling.LANCZOS)
    fitted = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    fitted.alpha_composite(cropped, ((CANVAS - cropped.width) // 2, (CANVAS - cropped.height) // 2))
    return fitted


def draw_icon() -> Image.Image:
    image = _rounded_background()
    gecko = _fit(draw_gecko().rotate(-14, resample=Image.Resampling.BICUBIC, center=(512, 512)), 790)
    shadow = Image.new("RGBA", gecko.size, (90, 20, 0, 0))
    shadow.putalpha(gecko.getchannel("A").point(lambda alpha: alpha * 0.45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    image.alpha_composite(shadow, (14, 22))
    image.alpha_composite(gecko)
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = draw_icon()
    master.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "lizard.png", optimize=True)
    for size in (48, 64):
        master.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS / f"lizard-{size}.png", optimize=True)
    master.resize((512, 512), Image.Resampling.LANCZOS).save(ASSETS / "lizard-512.png", optimize=True)
    preview = Image.new("RGBA", (sum(SIZES) + 10 * (len(SIZES) + 1), max(SIZES) + 20), (255, 255, 255, 255))
    x = 10
    for size in SIZES:
        preview.alpha_composite(master.resize((size, size), Image.Resampling.LANCZOS), (x, 10 + max(SIZES) - size))
        x += size + 10
    preview_path = Path(__file__).resolve().parent.parent / "build" / "icon-preview.png"
    preview_path.parent.mkdir(exist_ok=True)
    preview.save(preview_path)
    print(f"Icons written to {ASSETS} (size preview: {preview_path})")


if __name__ == "__main__":
    main()
