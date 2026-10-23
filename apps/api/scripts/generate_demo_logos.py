"""Draws the logos of the `full` demo (4 businesses, 11 branches) as SVG and renders them to PNG.

    uv run --with cairosvg --with pillow python scripts/generate_demo_logos.py

The SVG sources are written to `app/seed/assets/logos/svg/` and are the files to edit; the PNGs
(256 px, what the seed stores) and the manifest entries are derived from them. The marks are pure
shapes (no text), so they render the same everywhere and need no fonts. It only adds entries to
`manifest.json`, so it can run before or after `generate_demo_images.py`.
"""

import json
from pathlib import Path

import cairosvg

ASSETS = Path(__file__).resolve().parent.parent / "app" / "seed" / "assets"
SVG_DIR = ASSETS / "logos" / "svg"

# Glyphs are drawn white on a 256x256 canvas, centered on (128, 128).
STROKE = 'fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round"'
GLYPHS: dict[str, str] = {
    "dumbbell": """
        <rect x="68" y="119" width="120" height="18" rx="9" fill="#fff"/>
        <rect x="50" y="88" width="26" height="80" rx="9" fill="#fff"/>
        <rect x="30" y="104" width="22" height="48" rx="7" fill="#fff" opacity=".85"/>
        <rect x="180" y="88" width="26" height="80" rx="9" fill="#fff"/>
        <rect x="204" y="104" width="22" height="48" rx="7" fill="#fff" opacity=".85"/>""",
    "kettlebell": f"""
        <path d="M86 118 V86 Q86 54 128 54 Q170 54 170 86 V118" {STROKE} stroke-width="20"/>
        <path d="M64 156 A64 64 0 0 1 192 156 V176 Q192 198 170 198 H86 Q64 198 64 176 Z" fill="#fff"/>
        <rect x="100" y="150" width="56" height="12" rx="6" fill="#000" opacity=".16"/>""",
    "barbell": """
        <rect x="26" y="121" width="204" height="14" rx="7" fill="#fff"/>
        <rect x="56" y="62" width="26" height="132" rx="10" fill="#fff"/>
        <rect x="88" y="86" width="18" height="84" rx="8" fill="#fff" opacity=".85"/>
        <rect x="174" y="62" width="26" height="132" rx="10" fill="#fff"/>
        <rect x="150" y="86" width="18" height="84" rx="8" fill="#fff" opacity=".85"/>""",
    "lotus": f"""
        <path d="M128 62 C154 96 154 140 128 176 C102 140 102 96 128 62Z" fill="#fff"/>
        <path d="M80 92 C116 98 134 138 128 178 C92 172 70 134 80 92Z" fill="#fff" opacity=".82"/>
        <path d="M176 92 C140 98 122 138 128 178 C164 172 186 134 176 92Z" fill="#fff" opacity=".82"/>
        <path d="M64 196 Q128 226 192 196" {STROKE} stroke-width="12"/>""",
    "bolt": """
        <polygon points="150,48 82,142 120,142 106,210 176,112 136,112" fill="#fff"/>""",
    "belt": """
        <rect x="26" y="110" width="204" height="34" rx="7" fill="#fff" opacity=".9"/>
        <polygon points="106,150 90,214 120,214 128,150" fill="#fff"/>
        <polygon points="128,150 136,214 166,214 150,150" fill="#fff" opacity=".85"/>
        <rect x="98" y="92" width="60" height="70" rx="14" fill="#fff"/>
        <rect x="112" y="108" width="32" height="38" rx="8" fill="#000" opacity=".18"/>""",
    "tennis-ball": f"""
        <clipPath id="ball"><circle cx="128" cy="128" r="74"/></clipPath>
        <circle cx="128" cy="128" r="74" {STROKE} stroke-width="12"/>
        <g clip-path="url(#ball)">
          <path d="M66 54 Q120 128 66 202" {STROKE} stroke-width="12"/>
          <path d="M190 54 Q136 128 190 202" {STROKE} stroke-width="12"/>
        </g>""",
    "racket": f"""
        <clipPath id="head"><ellipse cx="128" cy="100" rx="52" ry="62"/></clipPath>
        <ellipse cx="128" cy="100" rx="52" ry="62" {STROKE} stroke-width="14"/>
        <g clip-path="url(#head)" stroke="#fff" stroke-width="5" opacity=".8">
          <path d="M104 40V166M128 38V168M152 40V166M70 76H186M66 100H190M70 124H186"/>
        </g>
        <path d="M128 164 V214" {STROKE} stroke-width="16"/>""",
    "court": f"""
        <rect x="58" y="70" width="140" height="116" rx="6" {STROKE} stroke-width="10"/>
        <path d="M128 70V186M58 128H198" {STROKE} stroke-width="8"/>
        <path d="M58 100H198M58 156H198" {STROKE} stroke-width="5" opacity=".6"/>""",
    "scissors": f"""
        <circle cx="94" cy="184" r="22" {STROKE} stroke-width="12"/>
        <circle cx="162" cy="184" r="22" {STROKE} stroke-width="12"/>
        <path d="M106 166 L168 54M150 166 L88 54" {STROKE} stroke-width="14"/>""",
    "razor": """
        <rect x="34" y="150" width="112" height="32" rx="16" fill="#fff"/>
        <g transform="rotate(-48 140 166)">
          <path d="M140 150 H228 Q242 150 234 164 Q226 182 140 182 Z" fill="#fff" opacity=".92"/>
          <path d="M140 150 H232" stroke="#000" stroke-opacity=".25" stroke-width="5"/>
        </g>
        <circle cx="140" cy="166" r="9" fill="#000" opacity=".28"/>""",
    "pole": """
        <clipPath id="capsule"><rect x="92" y="40" width="72" height="176" rx="36"/></clipPath>
        <rect x="92" y="40" width="72" height="176" rx="36" fill="#fff"/>
        <g clip-path="url(#capsule)" fill="#000" opacity=".28">
          <polygon points="70,60 186,16 186,52 70,96"/>
          <polygon points="70,112 186,68 186,104 70,148"/>
          <polygon points="70,164 186,120 186,156 70,200"/>
          <polygon points="70,216 186,172 186,208 70,252"/>
        </g>""",
    "spine": """
        <rect x="96" y="44" width="64" height="30" rx="13" fill="#fff"/>
        <rect x="88" y="82" width="80" height="32" rx="14" fill="#fff" opacity=".9"/>
        <rect x="84" y="122" width="88" height="34" rx="15" fill="#fff" opacity=".82"/>
        <rect x="92" y="164" width="72" height="32" rx="14" fill="#fff" opacity=".74"/>
        <rect x="102" y="204" width="52" height="14" rx="7" fill="#fff" opacity=".66"/>""",
    "apple": """
        <path d="M128 92 C102 70 64 90 74 136 C82 174 108 200 128 188 C148 200 174 174 182 136 C192 90 154 70 128 92Z" fill="#fff"/>
        <path d="M128 92 C128 66 142 50 164 46 C164 72 152 88 128 92Z" fill="#fff" opacity=".8"/>""",
    "cross": f"""
        <rect x="106" y="54" width="44" height="148" rx="14" fill="#fff"/>
        <rect x="54" y="106" width="148" height="44" rx="14" fill="#fff"/>
        <path d="M70 206 Q128 232 186 206" {STROKE} stroke-width="10" opacity=".75"/>""",
}

# key -> (kind, display name used in the preview, seed names, color, glyph). `kind` is only used
# for the file name. Seed names are the exact business and branch names the `full` demo uses.
BUSINESSES = [
    ("fitness", "Adir Fitness", ["אדיר פיטנס", "Adir Fitness"], "#ea580c", "dumbbell"),
    ("tennis", "Sharon Tennis Club", ["טניס קלאב השרון", "Sharon Tennis Club"], "#15803d", "tennis-ball"),
    ("barbers", "Blade Barbers", ["בלייד ברברס", "Blade Barbers"], "#1f2937", "pole"),
    ("clinic", "Merhav Clinic", ["מרחב - בריאות ותנועה", "Merhav Clinic"], "#0d9488", "cross"),
]  # fmt: skip
# business index -> [(file key, display name, branch name in the seed, color, glyph)]
BRANCHES = {
    "fitness": [
        ("tel-aviv", "Tel Aviv - Strength", "תל אביב - כוח", "#c2410c", "kettlebell"),
        ("beer-sheva", "Beer Sheva - Strength", "באר שבע - כוח", "#dc2626", "barbell"),
        ("ramat-gan", "Ramat Gan - Pilates & Yoga", "רמת גן - פילאטיס ויוגה", "#9333ea", "lotus"),
        ("haifa", "Haifa - CrossFit", "חיפה - קרוספיט", "#b45309", "bolt"),
        ("jerusalem", "Jerusalem - Martial Arts", "ירושלים - לחימה", "#be123c", "belt"),
    ],
    "tennis": [
        ("herzliya", "Herzliya", "הרצליה", "#166534", "racket"),
        ("rishon", "Rishon LeZion", "ראשון לציון", "#65a30d", "court"),
    ],
    "barbers": [
        ("florentin", "Tel Aviv - Florentin", "תל אביב - פלורנטין", "#b45309", "scissors"),
        ("ashdod", "Ashdod - HaRova", "אשדוד - הרובע", "#475569", "razor"),
    ],
    "clinic": [
        ("petah-tikva", "Petah Tikva - Physio", "פתח תקווה - פיזיותרפיה", "#0e7490", "spine"),
        ("kfar-saba", "Kfar Saba - Nutrition", "כפר סבא - תזונה", "#65a30d", "apple"),
    ],
}  # fmt: skip
# The barbers' accent is gold on a dark tile; the rest are white on a color.
GOLD = {"barbers": "#f59e0b"}


def _mix(color: str, target: int, amount: float) -> str:
    rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (target - c) * amount):02x}" for c in rgb)


def svg(color: str, glyph: str, accent: str | None = None) -> str:
    light, dark = _mix(color, 255, 0.18), _mix(color, 0, 0.32)
    body = GLYPHS[glyph]
    if accent:  # recolor the white shapes of the glyph
        body = body.replace('"#fff"', f'"{accent}"').replace('stroke="#fff"', f'stroke="{accent}"')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/>
    </linearGradient>
    <clipPath id="tile"><rect width="256" height="256" rx="64"/></clipPath>
  </defs>
  <rect width="256" height="256" rx="64" fill="url(#bg)"/>
  <circle cx="200" cy="48" r="120" fill="#fff" opacity=".07" clip-path="url(#tile)"/>
  <g>{body}
  </g>
</svg>
"""


def main() -> None:
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = ASSETS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for kind, _name, seed_names, color, glyph in BUSINESSES:
        stem = f"full-{kind}"
        source = svg(color, glyph, GOLD.get(kind))
        (SVG_DIR / f"{stem}.svg").write_text(source)
        cairosvg.svg2png(bytestring=source.encode(), write_to=str(ASSETS / "logos" / f"{stem}.png"))
        for seed_name in seed_names:
            manifest["tenants"][seed_name] = {"file": f"logos/{stem}.png", "color": color}
        for key, _label, branch_name, b_color, b_glyph in BRANCHES[kind]:
            b_stem = f"full-{kind}-{key}"
            b_source = svg(b_color, b_glyph, GOLD.get(kind))
            (SVG_DIR / f"{b_stem}.svg").write_text(b_source)
            cairosvg.svg2png(
                bytestring=b_source.encode(), write_to=str(ASSETS / "logos" / f"{b_stem}.png")
            )
            for seed_name in seed_names:
                manifest["branches"][f"{seed_name}/{branch_name}"] = {
                    "file": f"logos/{b_stem}.png",
                    "color": b_color,
                }
    manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
