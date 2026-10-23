"""Builds the logos of the `full` demo (4 businesses, 11 branches) from AI-made brand marks.

    uv run --with pillow python scripts/generate_demo_logos.py

The four business marks (and the yoga one, used by the pilates and yoga branch) are made once
with an image model and kept as small PNGs in `app/seed/assets/logos/ai/`. Each branch logo is
its business mark with a band under it naming the branch, drawn here so all branches of a
business look like one family. The script writes the PNGs the seed stores
(`logos/full-<business>[-<branch>].png`) and adds their entries to `manifest.json`; existing
entries are left alone.
"""

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "app" / "seed" / "assets"
BASE = ASSETS / "logos" / "ai"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIZE = 512
MARK = 400  # the business mark, shrunk to leave room for the branch name

# kind -> (names the seed may use, base mark, brand color for the list's accent)
BUSINESSES = {
    "fitness": (["אדיר פיטנס", "Adir Fitness"], "#111111"),
    "tennis": (["טניס קלאב השרון", "Sharon Tennis Club"], "#15803d"),
    "barbers": (["בלייד ברברס", "Blade Barbers"], "#b45309"),
    "clinic": (["מרחב - בריאות ותנועה", "Merhav Clinic"], "#0d9488"),
}
# kind -> [(file key, label under the logo, branch name in the seed, base mark)]
BRANCHES = {
    "fitness": [
        ("tel-aviv", "TEL AVIV · STRENGTH", "תל אביב - כוח", "fitness"),
        ("beer-sheva", "BEER SHEVA · STRENGTH", "באר שבע - כוח", "fitness"),
        ("ramat-gan", "RAMAT GAN · PILATES & YOGA", "רמת גן - פילאטיס ויוגה", "yoga"),
        ("haifa", "HAIFA · CROSSFIT", "חיפה - קרוספיט", "fitness"),
        ("jerusalem", "JERUSALEM · MARTIAL ARTS", "ירושלים - לחימה", "fitness"),
    ],
    "tennis": [
        ("herzliya", "HERZLIYA", "הרצליה", "tennis"),
        ("rishon", "RISHON LEZION", "ראשון לציון", "tennis"),
    ],
    "barbers": [
        ("florentin", "TEL AVIV · FLORENTIN", "תל אביב - פלורנטין", "barbers"),
        ("ashdod", "ASHDOD · HAROVA", "אשדוד - הרובע", "barbers"),
    ],
    "clinic": [
        ("petah-tikva", "PETAH TIKVA · PHYSIO", "פתח תקווה - פיזיותרפיה", "clinic"),
        ("kfar-saba", "KFAR SABA · NUTRITION", "כפר סבא - תזונה", "clinic"),
    ],
}


def _luma(rgb: tuple[int, ...]) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _save(image: Image.Image, name: str) -> str:
    path = ASSETS / "logos" / name
    image.save(path, "PNG", optimize=True)
    return f"logos/{name}"


def branch_logo(base: str, label: str) -> Image.Image:
    mark = Image.open(BASE / f"{base}.png").convert("RGB")
    background = mark.getpixel((6, 6))  # the mark's own flat background
    # Crop the mark to its content (the models leave wide margins) and fit it above the band.
    flat = Image.new("RGB", mark.size, background)
    box = ImageChops.difference(mark, flat).convert("L").point(lambda v: 255 if v > 24 else 0)
    left, top, right, bottom = box.getbbox() or (0, 0, *mark.size)
    pad = 24
    mark = mark.crop((max(left - pad, 0), max(top - pad, 0), right + pad, bottom + pad))
    mark.thumbnail((MARK, 330), Image.LANCZOS)
    canvas = Image.new("RGB", (SIZE, SIZE), background)
    canvas.paste(mark, ((SIZE - mark.width) // 2, 40 + (330 - mark.height) // 2))
    ink = (255, 255, 255) if _luma(background) < 140 else (24, 24, 24)
    draw = ImageDraw.Draw(canvas)
    size = 34
    while size > 14:
        font = ImageFont.truetype(FONT, size)
        if draw.textlength(label, font=font) <= SIZE - 56:
            break
        size -= 1
    width = draw.textlength(label, font=font)
    draw.text(((SIZE - width) / 2, 436), label, font=font, fill=ink)
    draw.line(((SIZE / 2 - 40, 428), (SIZE / 2 + 40, 428)), fill=ink, width=2)
    return canvas


def main() -> None:
    manifest_path = ASSETS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for kind, (names, color) in BUSINESSES.items():
        file = _save(Image.open(BASE / f"{kind}.png").convert("RGB"), f"full-{kind}.png")
        for name in names:
            manifest["tenants"][name] = {"file": file, "color": color}
        for key, label, branch, base in BRANCHES[kind]:
            branch_file = _save(branch_logo(base, label), f"full-{kind}-{key}.png")
            for name in names:
                manifest["branches"][f"{name}/{branch}"] = {"file": branch_file, "color": color}
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
