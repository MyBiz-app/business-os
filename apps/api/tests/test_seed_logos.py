"""The `full` demo's logos: every business and branch in the manifest points at a real PNG."""

import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "app" / "seed" / "assets"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FULL_BUSINESSES = ("אדיר פיטנס", "טניס קלאב השרון", "בלייד ברברס", "מרחב - בריאות ותנועה")


def test_full_demo_logos_exist_and_are_small_pngs():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    for name in FULL_BUSINESSES:
        assert name in manifest["tenants"]
    full = [e for e in manifest["tenants"].values() if "/full-" in e["file"].replace("logos", "/")]
    full += [e for k, e in manifest["branches"].items() if "full-" in e["file"]]
    assert len(full) >= 4 + 11
    for entry in full:
        data = (ASSETS / entry["file"]).read_bytes()
        assert data.startswith(PNG_SIGNATURE)
        assert len(data) < 200_000  # the seed stores these in the database


def test_every_branch_of_the_full_demo_has_its_own_logo():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    branches = {k: v["file"] for k, v in manifest["branches"].items() if "full-" in v["file"]}
    for name in FULL_BUSINESSES:
        own = {f for k, f in branches.items() if k.startswith(f"{name}/")}
        assert len(own) >= 2
    assert len(set(branches.values())) == 11
