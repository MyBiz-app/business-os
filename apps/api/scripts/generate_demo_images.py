"""Draws the demo images the seed uses: business and branch logos and a pool of portraits.

    uv run --with pillow python scripts/generate_demo_images.py

Everything is synthetic and drawn here (no photos, no generated faces of real people), so the
files in `app/seed/assets/` can be committed and the seed stays reproducible. The seed itself
only reads the files; Pillow is needed just to regenerate them.
"""

import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.seed.common import DEMOS, PLATFORM_BUSINESSES

ASSETS = Path(__file__).resolve().parent.parent / "app" / "seed" / "assets"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SCALE = 4  # drawn at four times the size, then shrunk, for smooth edges

# Colors per branch kind (strength, pilates, crossfit...), used for branch logos.
KIND_COLORS = {
    "gym": "#c2410c",
    "pilates": "#7c3aed",
    "crossfit": "#b45309",
    "padel_tennis": "#4d7c0f",
    "hair_salon": "#be185d",
}
KIND_ICONS = {"gym": "bars", "pilates": "ring", "crossfit": "bolt", "padel_tennis": "ball"}
# The business's Latin initials (names in Hebrew have no letters this font can draw).
LATIN = {
    "אדיר פיטנס": "AF",
    "סטודיו": "S",
}
ICONS = ("ring", "bars", "leaf", "bolt", "hex", "wave")


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def _shade(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)  # type: ignore[return-value]


def _png(image: Image.Image, size: int) -> bytes:
    out = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def _jpeg(image: Image.Image, size: int) -> bytes:
    out = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).convert("RGB").save(out, "JPEG", quality=88)
    return out.getvalue()


def logo(color: str, icon: str, letters: str) -> bytes:
    n = 256 * SCALE
    base = _rgb(color)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    # A diagonal gradient inside a rounded square.
    grad = Image.new("RGB", (n, n))
    px = grad.load()
    for y in range(n):
        for x in range(n):
            px[x, y] = _shade(base, 1.2 - 0.55 * (x + y) / (2 * n))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, n - 1, n - 1), radius=n // 4, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 235)
    soft = (255, 255, 255, 70) if letters else (255, 255, 255, 225)
    c = n // 2
    if icon == "ring":
        d.ellipse(
            (c - 0.36 * n, c - 0.36 * n, c + 0.36 * n, c + 0.36 * n), outline=soft, width=n // 18
        )
        d.ellipse(
            (c - 0.22 * n, c - 0.22 * n, c + 0.22 * n, c + 0.22 * n), outline=soft, width=n // 24
        )
    elif icon == "bars":
        for i, h in enumerate((0.32, 0.5, 0.4)):
            x0 = n * (0.22 + 0.2 * i)
            d.rounded_rectangle(
                (x0, n * (0.78 - h), x0 + n * 0.14, n * 0.78), radius=n // 40, fill=soft
            )
    elif icon == "leaf":
        d.pieslice((n * 0.15, n * 0.15, n * 0.85, n * 0.85), 180, 270, fill=soft)
        d.pieslice((n * 0.15, n * 0.15, n * 0.85, n * 0.85), 0, 90, fill=soft)
    elif icon == "bolt":
        d.polygon(
            [
                (0.56 * n, 0.12 * n),
                (0.26 * n, 0.55 * n),
                (0.47 * n, 0.55 * n),
                (0.40 * n, 0.88 * n),
                (0.74 * n, 0.42 * n),
                (0.52 * n, 0.42 * n),
            ],
            fill=soft,
        )
    elif icon == "hex":
        import math

        d.polygon(
            [
                (
                    c + 0.38 * n * math.cos(math.pi / 3 * k + 0.5),
                    c + 0.38 * n * math.sin(math.pi / 3 * k + 0.5),
                )
                for k in range(6)
            ],
            outline=soft,
            width=n // 22,
        )
    elif icon == "ball":
        d.ellipse(
            (c - 0.34 * n, c - 0.34 * n, c + 0.34 * n, c + 0.34 * n), outline=soft, width=n // 20
        )
        d.arc(
            (c - 0.34 * n - 0.3 * n, c - 0.34 * n, c + 0.04 * n, c + 0.34 * n),
            -60,
            60,
            fill=soft,
            width=n // 24,
        )
    else:  # wave
        for i in range(3):
            y = n * (0.34 + 0.16 * i)
            d.arc((n * 0.1, y - 0.1 * n, n * 0.5, y + 0.1 * n), 0, 180, fill=soft, width=n // 24)
            d.arc((n * 0.5, y - 0.1 * n, n * 0.9, y + 0.1 * n), 180, 360, fill=soft, width=n // 24)
    if letters:
        font = ImageFont.truetype(FONT, int(n * (0.42 if len(letters) < 3 else 0.32)))
        d.text((c, c), letters, font=font, fill=white, anchor="mm")
    return _png(img, 256)


SKIN = ["#f1c9a5", "#e5b48b", "#d19a6e", "#b97c53", "#8d5a3b", "#6b4229"]
HAIR = ["#1c1a1a", "#3b2a20", "#5a3b27", "#8a5a34", "#b98a4e", "#8f8f8f", "#a33b2b"]
SHIRT = ["#2563eb", "#0f766e", "#7c3aed", "#dc2626", "#d97706", "#374151", "#0891b2", "#be185d"]
BG = ["#dbeafe", "#fde68a", "#d1fae5", "#fce7f3", "#e0e7ff", "#fee2e2", "#e5e7eb", "#ccfbf1"]


def portrait(rng: random.Random, female: bool) -> bytes:
    n = 256 * SCALE
    u = n / 100
    bg = _rgb(rng.choice(BG))
    skin = _rgb(rng.choice(SKIN))
    hair = _rgb(rng.choice(HAIR))
    shirt = _rgb(rng.choice(SHIRT))
    img = Image.new("RGB", (n, n), bg)
    d = ImageDraw.Draw(img)
    # Soft vignette behind the head.
    d.ellipse((12 * u, 8 * u, 88 * u, 84 * u), fill=_shade(bg, 0.94))
    # Shoulders and shirt.
    d.ellipse((12 * u, 70 * u, 88 * u, 130 * u), fill=shirt)
    d.polygon([(40 * u, 74 * u), (50 * u, 86 * u), (60 * u, 74 * u)], fill=_shade(skin, 0.9))
    # Neck.
    d.rounded_rectangle((42 * u, 58 * u, 58 * u, 80 * u), radius=3 * u, fill=_shade(skin, 0.92))
    style = rng.choice(["long", "bob", "bun"] if female else ["short", "buzz", "side"])
    # Hair behind the head.
    if style == "long":
        d.rounded_rectangle((26 * u, 22 * u, 74 * u, 76 * u), radius=20 * u, fill=hair)
    elif style == "bob":
        d.rounded_rectangle((27 * u, 24 * u, 73 * u, 62 * u), radius=16 * u, fill=hair)
    elif style == "bun":
        d.ellipse((42 * u, 8 * u, 58 * u, 24 * u), fill=hair)
    # Ears and head.
    d.ellipse((29 * u, 40 * u, 36 * u, 52 * u), fill=_shade(skin, 0.95))
    d.ellipse((64 * u, 40 * u, 71 * u, 52 * u), fill=_shade(skin, 0.95))
    d.ellipse((31 * u, 22 * u, 69 * u, 66 * u), fill=skin)
    # Hair in front.
    if style in ("long", "bob", "bun"):
        d.pieslice((29 * u, 19 * u, 71 * u, 52 * u), 180, 360, fill=hair)
        if style != "bun":
            d.polygon([(31 * u, 38 * u), (50 * u, 26 * u), (31 * u, 26 * u)], fill=hair)
    elif style == "short":
        d.pieslice((29 * u, 18 * u, 71 * u, 50 * u), 180, 360, fill=hair)
    elif style == "buzz":
        d.pieslice((30 * u, 20 * u, 70 * u, 50 * u), 195, 345, fill=_shade(hair, 1.0))
    else:  # side
        d.pieslice((29 * u, 17 * u, 71 * u, 50 * u), 175, 365, fill=hair)
        d.polygon([(31 * u, 36 * u), (60 * u, 24 * u), (31 * u, 24 * u)], fill=hair)
    # Face.
    eye = (38, 32, 28)
    for x in (41, 59):
        d.ellipse(((x - 2.6) * u, 43 * u, (x + 2.6) * u, 47.5 * u), fill=(250, 250, 250))
        d.ellipse(((x - 1.5) * u, 43.6 * u, (x + 1.5) * u, 46.8 * u), fill=eye)
        d.line(
            ((x - 4) * u, 40.5 * u, (x + 4) * u, 40 * u), fill=_shade(hair, 0.9), width=int(1.1 * u)
        )
    d.line((50 * u, 47 * u, 49 * u, 54 * u), fill=_shade(skin, 0.8), width=int(0.9 * u))
    d.arc((43 * u, 52 * u, 57 * u, 62 * u), 20, 160, fill=(150, 60, 60), width=int(1.3 * u))
    if not female and rng.random() < 0.35:
        d.pieslice((33 * u, 48 * u, 67 * u, 70 * u), 0, 180, fill=_shade(hair, 0.9))
        d.arc((43 * u, 52 * u, 57 * u, 62 * u), 20, 160, fill=(235, 235, 235), width=int(1.3 * u))
    if rng.random() < 0.25:
        for x in (41, 59):
            d.ellipse(
                ((x - 5.5) * u, 40.5 * u, (x + 5.5) * u, 50.5 * u),
                outline=(40, 40, 50),
                width=int(0.8 * u),
            )
        d.line((46.5 * u, 45 * u, 53.5 * u, 45 * u), fill=(40, 40, 50), width=int(0.8 * u))
    return _jpeg(img, 256)


def main() -> None:
    (ASSETS / "logos").mkdir(parents=True, exist_ok=True)
    (ASSETS / "portraits").mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {"tenants": {}, "branches": {}, "portraits": {"f": [], "m": []}}

    specs = [spec for specs in DEMOS.values() for spec in specs] + [
        s for s, _ in PLATFORM_BUSINESSES
    ]
    seen: set[str] = set()
    for index, spec in enumerate(specs):
        if spec.name in seen:
            continue
        seen.add(spec.name)
        latin = "".join(w[0] for w in spec.name.split() if w[0].isascii() and w[0].isalpha())[
            :2
        ].upper()
        letters = latin or LATIN.get(spec.name) or ""
        file = f"logos/b{len(seen):02d}.png"
        (ASSETS / file).write_bytes(logo(spec.color, ICONS[index % len(ICONS)], letters))
        manifest["tenants"][spec.name] = {"file": file, "color": spec.color}
        for branch in spec.branches:
            kind = branch.kind or spec.vertical
            color = KIND_COLORS.get(kind, spec.color)
            key = f"logos/br{len(manifest['branches']) + 1:02d}.png"
            initial = ""
            (ASSETS / key).write_bytes(
                logo(color, KIND_ICONS.get(kind, ICONS[(index + 2) % len(ICONS)]), initial)
            )
            manifest["branches"][f"{spec.name}/{branch.name}"] = {"file": key, "color": color}
    # Extra branch kinds used when a business gets a new branch later (the crossfit branch).
    for kind in ("crossfit",):
        key = f"logos/kind-{kind}.png"
        (ASSETS / key).write_bytes(logo(KIND_COLORS[kind], KIND_ICONS[kind], "CF"))
        manifest["branches"][f"kind:{kind}"] = {"file": key, "color": KIND_COLORS[kind]}

    for gender, female in (("f", True), ("m", False)):
        for i in range(24):
            name = f"portraits/{gender}{i + 1:02d}.jpg"
            (ASSETS / name).write_bytes(portrait(random.Random(f"{gender}{i}"), female))
            manifest["portraits"][gender].append(name)
    (ASSETS / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
