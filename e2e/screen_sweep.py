"""Screenshot sweep: every given page in Hebrew and English, light and dark, at three widths
(phone 390, laptop 1440, large screen 1920). Used to review the redesign (design round 2) and to
catch direction, dark-mode and width problems before they ship.

Also checks, per shot, that nothing makes the page scroll sideways.

Usage (web app running, see e2e/README.md):
    uv run --with playwright python e2e/screen_sweep.py                  # the public pages
    uv run --with playwright python e2e/screen_sweep.py / /pricing       # just these paths
    SWEEP_BASE=https://business-os-alpha-drab.vercel.app uv run --with playwright python e2e/screen_sweep.py

Screenshots go to e2e/screenshots/sweep/<locale>-<theme>/<width>/<page>.png (git-ignored).
Exit code 1 when a page scrolls sideways.
"""

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

import helpers as h

BASE = os.environ.get("SWEEP_BASE", h.BASE)
PUBLIC_PAGES = [
    "/", "/features", "/ai-team", "/industries", "/industries/fitness", "/pricing", "/about", "/contact",
    "/getting-started", "/legal/terms", "/legal/privacy", "/legal/accessibility",
    "/login", "/signup", "/forgot-password", "/start",
]  # fmt: skip
LOCALES = {"he": "he-IL", "en": "en-US"}
WIDTHS = {"390": (390, 844), "1440": (1440, 900), "1920": (1920, 1080)}
THEMES = ("light", "dark")


def slug(path: str) -> str:
    return path.strip("/").replace("/", "_") or "home"


def reveal_all(page) -> None:
    """Scroll to the bottom in steps so fade-in-on-scroll sections (Reveal) are visible in the shot."""
    page.evaluate(
        """async () => {
            const step = Math.max(300, innerHeight / 2);
            for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
                scrollTo(0, y);
                await new Promise((r) => setTimeout(r, 60));
            }
            scrollTo(0, 0);
        }"""
    )
    page.wait_for_timeout(600)


def main(pages: list[str]) -> int:
    out = pathlib.Path(h.OUT) / "sweep"
    sideways: list[str] = []
    shots = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=h.chromium())
        for lang, locale in LOCALES.items():
            for theme in THEMES:
                for width, (w, hgt) in WIDTHS.items():
                    context = browser.new_context(
                        locale=locale, color_scheme=theme, viewport={"width": w, "height": hgt}
                    )
                    page = context.new_page()
                    folder = out / f"{lang}-{theme}" / width
                    folder.mkdir(parents=True, exist_ok=True)
                    for path in pages:
                        page.goto(BASE + path)
                        h.ready(page)
                        reveal_all(page)
                        page.screenshot(path=str(folder / f"{slug(path)}.png"), full_page=True)
                        shots += 1
                        overflow = page.evaluate(
                            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                        )
                        if overflow > 1:
                            sideways.append(f"{lang}/{theme}/{width} {path} (+{overflow}px)")
                    context.close()
        browser.close()
    print(f"{shots} screenshots in {out}")
    for line in sideways:
        print("scrolls sideways:", line)
    return 1 if sideways else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or PUBLIC_PAGES))
