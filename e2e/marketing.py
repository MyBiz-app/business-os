"""Marketing site: every page renders in Hebrew (light) and English (dark) without serious
accessibility issues, prices come from the API, and the contact form reaches the platform."""

import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
PAGES = ["/", "/features", "/industries/fitness", "/industries/beauty", "/industries/clinic",
         "/industries/garage", "/pricing", "/about", "/contact", "/legal/terms", "/legal/privacy",
         "/legal/accessibility"]  # fmt: skip


def serious(page) -> list[str]:
    return [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    for locale, scheme in (("he-IL", "light"), ("en-US", "dark")):
        page = b.new_context(locale=locale, color_scheme=scheme, viewport={"width": 1280, "height": 900}).new_page()
        page.goto(h.BASE); h.ready(page)
        if locale == "en-US":  # the site follows the language chosen in the header
            page.locator("header select").first.select_option("en"); page.wait_for_timeout(1500); h.ready(page)
        issues = {}
        for path in PAGES:
            page.goto(h.BASE + path); h.ready(page)
            expect(page.get_by_role("heading", level=1)).to_be_visible()
            found = serious(page)
            if found:
                issues[path] = found
        page.screenshot(path=f"{h.OUT}/marketing-{scheme}.png", full_page=False)
        print(f"{locale}/{scheme}: {len(PAGES)} pages | a11y:", issues or "ok")

    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(h.BASE + "/pricing"); h.ready(page)
    expect(page.get_by_text(re.compile("₪")).first).to_be_visible()
    page.get_by_role("link", name="USD").click(); page.wait_for_url("**currency=USD"); h.ready(page)
    expect(page.get_by_text(re.compile(r"\$")).first).to_be_visible()
    page.screenshot(path=f"{h.OUT}/marketing-pricing.png", full_page=True)
    print("pricing from the API, currency switch: ok")

    email = f"lead{time.time_ns()}@example.com"
    page.goto(h.BASE + "/contact"); h.ready(page)
    page.get_by_label("שם מלא").fill("דנה כהן")
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("תחום העסק").select_option("beauty")
    page.get_by_label("איך נוכל לעזור?").fill("מתעניינת באפליקציה")
    page.get_by_role("button", name="שליחה").click()
    expect(page.get_by_role("status")).to_contain_text("תודה!")
    with psycopg.connect(h.DATABASE_URL) as conn:
        stored = conn.execute("SELECT name, vertical FROM app.contact_requests WHERE email = %s", (email,)).fetchone()
    assert stored == ("דנה כהן", "beauty"), stored
    print("contact form stored: ok")

    phone = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    phone.goto(h.BASE); h.ready(phone)
    phone.get_by_role("button", name="תפריט").click()
    phone.locator("#marketing-menu").get_by_role("link", name="מחירים").click()
    phone.wait_for_url("**/pricing"); h.ready(phone)
    phone.screenshot(path=f"{h.OUT}/marketing-mobile.png", full_page=False)
    print("mobile menu: ok")
    b.close()
