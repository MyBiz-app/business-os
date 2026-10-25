"""Fetches illustrated avatars (DiceBear "avataaars", CC0) for demo people who get no AI portrait.

Illustrations only: nobody in them exists. Writes JPEGs to app/seed/assets/portraits/illustrated.

    python scripts/generate_demo_illustrated_avatars.py 80
"""

import io
import random
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

OUT = (
    Path(__file__).resolve().parent.parent / "app" / "seed" / "assets" / "portraits" / "illustrated"
)
BASE = "https://api.dicebear.com/9.x/avataaars/png"
TOPS = {
    "f": "bob,bun,curly,curvy,straight01,straight02,straightAndStrand,longButNotTooLong,bigHair",
    "m": "shortCurly,shortFlat,shortRound,shortWaved,theCaesar,theCaesarAndSidePart,sides,shaggy",
}
SKIN = "edb98a,d08b5b,ffdbb4,ae5d29,614335"
HAIR = "2c1b18,4a312c,724133,a55728,b58143,e8e1e1"
CLOTHING = "hoodie,shirtCrewNeck,shirtVNeck,collarAndSweater,graphicShirt,blazerAndShirt"
BACKGROUND = "e8eef5,f3e8ee,e8f3ee,f3efe8,ece8f3"


def fetch(gender: str, number: int) -> bytes:
    query = {
        "seed": f"{gender}{number}",
        "size": "192",
        "top": TOPS[gender],
        "skinColor": SKIN,
        "hairColor": HAIR,
        "clothing": CLOTHING,
        "backgroundColor": BACKGROUND,
        "facialHairProbability": "0" if gender == "f" else "35",
        "accessories": "prescription01,prescription02,round",
        "accessoriesProbability": "15",
        "eyes": "default,happy",
        "eyebrows": "defaultNatural,flatNatural,raisedExcitedNatural",
        "mouth": "smile,twinkle,default",
    }
    url = f"{BASE}?{urllib.parse.urlencode(query)}"
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https URL)
        image = Image.open(io.BytesIO(response.read())).convert("RGB")
    out = io.BytesIO()
    image.save(out, "JPEG", quality=80, optimize=True)
    return out.getvalue()


def main() -> None:
    per_gender = int(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    random.seed(1)
    for gender in ("f", "m"):
        for number in range(1, per_gender + 1):
            path = OUT / f"{gender}{number:03d}.jpg"
            if not path.exists():
                path.write_bytes(fetch(gender, number))
    print(f"{len(list(OUT.glob('*.jpg')))} avatars in {OUT}")


if __name__ == "__main__":
    main()
