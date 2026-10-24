"""Signs in on a live site with SWEEP_EMAIL / SWEEP_PASSWORD (environment only, never stored) and saves a
Playwright storage state for sweep_live.py. Usage: python e2e/sweep_login.py <base> <out.json>"""

import os
import sys

from playwright.sync_api import sync_playwright

base, out = sys.argv[1].rstrip("/"), sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = b.new_context(locale="en-US", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(base + "/login", wait_until="networkidle")
    page.locator("input[name=email]").fill(os.environ["SWEEP_EMAIL"])
    page.locator("input[name=password]").fill(os.environ["SWEEP_PASSWORD"])
    page.get_by_role("button", name="Log in", exact=True).click()
    page.wait_for_timeout(8000)
    print("landed:", page.url)
    print(page.inner_text("body")[:400].replace("\n", " | "))
    page.screenshot(path=out + ".png")
    ctx.storage_state(path=out)
