"""The product's name and contact details, from brand.json next to this file.

brand.json is a copy of packages/i18n/brand.json, the one brand file (the API image is built from
apps/api alone). `pnpm brand:sync` refreshes the copy and a test fails when it is stale. Texts are
written with the name spelled WRITTEN; `with_brand` swaps in the current name."""

import json
from pathlib import Path
from typing import Any, Final

BRAND: Final[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("brand.json")).read_text(encoding="utf-8")
)

NAME: Final[str] = BRAND["name"]
EMAILS: Final[dict[str, str]] = BRAND["emails"]
WRITTEN: Final = "MyBiz"  # how the texts in messages/*.json and prompts spell the product


def with_brand(value: Any) -> Any:
    """The texts inside `value` (a string, list or dict) with the written name replaced."""
    if NAME == WRITTEN:
        return value
    if isinstance(value, str):
        return value.replace(WRITTEN, NAME)
    if isinstance(value, list):
        return [with_brand(item) for item in value]
    if isinstance(value, dict):
        return {key: with_brand(item) for key, item in value.items()}
    return value
