"""Accessibility scan (axe-core) of the public pages of a live site, no login.

Light on traffic by design: a few pages, two language/theme variants, phone and laptop widths.
Usage:
    SWEEP_BASE=https://business-os-alpha-drab.vercel.app \
        uv run --with playwright --with axe-playwright-python python e2e/staging_axe.py [out.json]
The JSON lists every violation (rule, impact, help URL, count, first selector) per page and variant.
"""

import json
import os
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

import helpers as h

BASE = os.environ.get("SWEEP_BASE", h.BASE)
PAGES = [
    "/", "/features", "/ai-team", "/industries", "/pricing", "/about", "/contact", "/getting-started",
    "/legal/terms", "/legal/privacy", "/legal/accessibility", "/login", "/signup", "/forgot-password",
]  # fmt: skip
VARIANTS = (
    ("he-light-1440", "he-IL", "light", (1440, 900)),
    ("en-dark-390", "en-US", "dark", (390, 844)),
)


def main(out_path: str) -> None:
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=h.chromium())
        for name, locale, scheme, (w, hgt) in VARIANTS:
            page = browser.new_context(
                locale=locale, color_scheme=scheme, viewport={"width": w, "height": hgt}
            ).new_page()
            for path in PAGES:
                response = page.goto(BASE + path)
                h.ready(page)
                violations = Axe().run(page).response["violations"]
                results.append(
                    {
                        "variant": name,
                        "path": path,
                        "status": response.status if response else None,
                        "violations": [
                            {
                                "rule": v["id"],
                                "impact": v["impact"],
                                "help": v["help"],
                                "url": v["helpUrl"],
                                "count": len(v["nodes"]),
                                "example": v["nodes"][0]["target"],
                            }
                            for v in violations
                        ],
                    }
                )
                print(name, path, len(violations))
        browser.close()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "axe-staging.json")
