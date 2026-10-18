"""Wide-screen check in a real browser (design round 7, R15): the console and the account page at
phone, laptop, large and ultra-wide widths. Nothing may scroll sideways, a form room stays within
its 1600px cap, and a table page uses the room it is given.

    uv run --with playwright --with "psycopg[binary]" python e2e/wide_screens.py <console owner email>
"""

import faulthandler
import sys

from playwright.sync_api import sync_playwright

import helpers as h

OWNER = sys.argv[1]
WIDTHS = (390, 1440, 1920, 2560)
CAP = 1600  # Container size "settings" (100rem)
# (path, "capped" = a form room, "open" = a table or board that may use the whole screen)
PAGES = [("/account", "capped"), ("/platform", "open"), ("/platform/businesses", "open"), ("/platform/billing", "capped")]
problems: list[str] = []
faulthandler.dump_traceback_later(1200, exit=True)  # a hang shows where it stood instead of running to the job limit

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=h.chromium())
    page = browser.new_context(locale="he-IL", viewport={"width": 1440, "height": 900}).new_page()
    page.set_default_timeout(120000)  # the first visit of each console page is compiled on demand
    page.set_default_navigation_timeout(180000)
    print("signing in", flush=True)
    h.login(page, OWNER)
    print("signed in", flush=True)
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 1000})
        for path, kind in PAGES:
            page.goto(f"{h.BASE}{path}")
            h.ready(page)
            m = page.evaluate(
                """() => ({
                    scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    main: document.getElementById("main")?.getBoundingClientRect().width ?? 0,
                })"""
            )
            label = f"{path} at {width}"
            print(label, m, flush=True)
            if m["scroll"] > 0:
                problems.append(f"{label}: scrolls sideways by {m['scroll']}px")
            if m["main"] == 0:
                problems.append(f"{label}: no <main id=main> found")
            elif kind == "capped" and m["main"] > CAP + 1:
                problems.append(f"{label}: form room is {m['main']:.0f}px, cap is {CAP}px")
            elif kind == "open" and width >= 1920 and m["main"] <= CAP:
                problems.append(f"{label}: table page stays at {m['main']:.0f}px on a {width}px screen")
    browser.close()

if problems:
    print("\n".join(problems))
    sys.exit(1)
print("wide screens ok")
