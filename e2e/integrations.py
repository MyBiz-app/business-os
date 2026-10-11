"""Integrations (X13) in the business web app and the MyBiz console: settings → Integrations
lists the payments, invoicing and messaging providers (built in by default); choosing the
built-in simulated provider explicitly makes it the business's own connection and
disconnecting goes back to the default. The console lists every capability with its default.
Hebrew/light on a wide screen, English/dark on a phone, with axe.

Usage: python e2e/integrations.py <owner email with a business> <MyBiz team owner email>"""

import pathlib
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER, TEAM = sys.argv[1], sys.argv[2]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        issues.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/integrations-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    h.login(page, OWNER)
    page.goto(f"{h.BASE}/settings"); h.ready(page)
    page.get_by_role("link", name="חיבורים לספקים").click()
    page.wait_for_url("**/settings/integrations"); h.ready(page)
    for title in ("סליקה", "חשבוניות וקבלות", "וואטסאפ ו-SMS"):
        expect(page.get_by_role("heading", name=title)).to_be_visible()
    expect(page.get_by_text("בשימוש: ברירת המחדל של MyBiz.").first).to_be_visible()
    check(page, "settings")
    print("1. settings → integrations: three services on the defaults: ok")

    payments = page.locator("section[aria-labelledby=integration-payments]")
    payments.get_by_text("החלפת ספק או הגדרות").click()
    payments.get_by_role("button", name="שמירת החיבור").click()
    expect(payments.get_by_text("חיבור משלך, מאז")).to_be_visible()
    payments.get_by_role("button", name="ניתוק (חזרה לברירת המחדל)").click()
    expect(payments.get_by_text("בשימוש: ברירת המחדל של MyBiz.")).to_be_visible()
    print("2. connected the business's own provider and went back to the default: ok")

    phone = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844})
    page = phone.new_page()
    h.login(page, TEAM)
    phone.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    page.goto(f"{h.BASE}/platform/integrations"); h.ready(page)
    for title in ("Payments", "Invoices and receipts", "WhatsApp and SMS", "Email", "AI assistant", "File storage"):
        expect(page.get_by_role("heading", name=title)).to_be_visible()
    check(page, "console-en-dark")
    print("3. the console lists every service with its default (English, dark, phone): ok")
    b.close()

if issues:
    print("ISSUES:", *issues, sep="\n  ")
    sys.exit(1)
print("integrations: all steps passed, no accessibility issues")
