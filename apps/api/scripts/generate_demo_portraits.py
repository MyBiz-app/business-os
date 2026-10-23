"""Draws AI profile portraits for the demo people (Runware, FLUX schnell) into the seed assets.

Run by hand or from a one-off workflow with RUNWARE_KEY set. Synthetic people only: nobody in
the pictures exists. Every call reports its cost, and the run stops before BUDGET_USD is spent,
counting PRIOR_SPEND_USD from earlier runs. Files that already exist are skipped, so a stopped run
resumes where it left off.

    RUNWARE_KEY=... BUDGET_USD=9 PRIOR_SPEND_USD=0.5 python scripts/generate_demo_portraits.py 700
"""

import base64
import io
import json
import os
import random
import sys
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "app" / "seed" / "assets" / "portraits" / "ai"
API = "https://api.runware.ai/v1"
MODEL = "runware:100@1"  # FLUX schnell
BATCH = 8
SIZE = 192

AGES = ["early 20s", "late 20s", "early 30s", "late 30s", "mid 40s", "late 40s", "early 50s", "60s"]
LOOKS = [
    "Israeli of Ashkenazi descent", "Israeli of Mizrahi descent", "Israeli of Ethiopian descent",
    "Arab Israeli", "Israeli of Russian descent", "Israeli of Sephardic descent",
    "Druze Israeli", "mixed-heritage Israeli",
]  # fmt: skip
HAIR_F = ["long dark wavy hair", "short bob", "curly hair", "hair in a ponytail", "shoulder-length brown hair", "short blonde hair", "long straight black hair", "hair tied in a bun"]  # fmt: skip
HAIR_M = ["short dark hair", "buzz cut", "curly hair", "short hair and a light beard",
          "balding with a stubble", "medium-length wavy hair", "gray short hair", "short brown hair"]  # fmt: skip
CLOTHES = ["a plain t-shirt", "a casual shirt", "a sports jacket", "a hoodie", "a polo shirt",
           "a knit sweater", "a work shirt", "a tank top"]  # fmt: skip
BACKGROUNDS = ["a softly blurred gym", "a softly blurred street", "a neutral studio backdrop",
               "a softly blurred office", "a softly blurred park", "a warm indoor setting"]  # fmt: skip


def prompt(gender: str, rng: random.Random) -> str:
    person = "woman" if gender == "f" else "man"
    hair = rng.choice(HAIR_F if gender == "f" else HAIR_M)
    return (
        f"Realistic profile photo headshot of a {rng.choice(LOOKS)} {person} in {rng.choice(AGES)}, "
        f"{hair}, wearing {rng.choice(CLOTHES)}, natural light, {rng.choice(BACKGROUNDS)}, "
        "looking at the camera, friendly relaxed expression, head and shoulders, sharp focus"
    )


def call(tasks: list[dict], key: str) -> list[dict]:
    request = urllib.request.Request(
        API,
        data=json.dumps(tasks).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response).get("data", [])


def shrink(raw: bytes) -> bytes:
    image = Image.open(io.BytesIO(raw)).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=68, optimize=True, progressive=True)
    return out.getvalue()


def main() -> None:
    per_gender = int(sys.argv[1])
    key = os.environ["RUNWARE_KEY"]
    budget = float(os.environ.get("BUDGET_USD", "9"))
    spent = float(os.environ.get("PRIOR_SPEND_USD", "0"))
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = [(g, n) for n in range(1, per_gender + 1) for g in ("f", "m")]
    todo = [(g, n) for g, n in wanted if not (OUT / f"{g}{n:04d}.jpg").exists()]
    print(f"{len(todo)} to draw, {len(wanted) - len(todo)} already there, spent so far ${spent:.4f}")
    cost_so_far, drawn, failed = 0.0, 0, 0
    for start in range(0, len(todo), BATCH):
        if spent + cost_so_far + 0.05 > budget:  # a batch costs well under 5 cents
            print(f"BUDGET STOP at ${spent + cost_so_far:.4f} (cap ${budget})")
            break
        group = todo[start : start + BATCH]
        tasks = [
            {
                "taskType": "imageInference", "taskUUID": str(uuid.uuid4()),
                "positivePrompt": prompt(g, random.Random(f"{g}{n}")), "model": MODEL,
                "width": 512, "height": 512, "steps": 4, "numberResults": 1,
                "outputType": "base64Data", "outputFormat": "JPEG", "includeCost": True,
                "seed": 1000 + n * 2 + (g == "m"),
            }
            for g, n in group
        ]  # fmt: skip
        try:
            results = call(tasks, key)
        except Exception as error:  # a failed call is not billed; retry the batch once
            print(f"batch {start} failed: {error!r}")
            time.sleep(5)
            failed += len(group)
            continue
        by_id = {r["taskUUID"]: r for r in results}
        for (g, n), task in zip(group, tasks, strict=True):
            result = by_id.get(task["taskUUID"])
            if not result or "imageBase64Data" not in result:
                failed += 1
                continue
            cost_so_far += float(result.get("cost") or 0)
            (OUT / f"{g}{n:04d}.jpg").write_bytes(shrink(base64.b64decode(result["imageBase64Data"])))
            drawn += 1
        print(f"drawn {drawn}, failed {failed}, run cost ${cost_so_far:.4f}", flush=True)
    print(f"DONE drawn={drawn} failed={failed} run_cost=${cost_so_far:.4f} "
          f"total_spent=${spent + cost_so_far:.4f}")


if __name__ == "__main__":
    main()
