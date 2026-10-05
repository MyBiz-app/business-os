"""The business app (Expo web): a staff member signs in with an email code, sees today, opens a
session and checks a client in, finds a client, and reads the key numbers.
Usage: python e2e/business_app.py <owner email of a business with data>"""

import pathlib
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

APP = "http://localhost:8082"
OWNER = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
a11y: list[str] = []


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']}: {v['nodes'][0]['target']}")
    page.screenshot(path=f"{h.OUT}/bizapp-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
    page.goto(APP)
    page.get_by_label("אימייל").wait_for(timeout=60000)
    page.get_by_label("אימייל").fill(OWNER)
    page.get_by_role("button", name="שליחת קוד").click()
    page.get_by_label("קוד בן 6 ספרות").wait_for(timeout=30000)
    page.get_by_label("קוד בן 6 ספרות").fill(h.otp(OWNER))
    page.get_by_role("button", name="כניסה").click()
    page.get_by_role("heading", name="סטודיו פלואו (דמו)").wait_for(timeout=60000)
    check(page, "today")
    print("1. signed in and the day is showing: ok")

    # Open the first session of the day and check someone in.
    page.get_by_text("07:00").click()
    page.get_by_text("מי מגיע").first.wait_for(timeout=30000)
    check(page, "session")
    check_in = page.get_by_role("button", name="סימון הגעה").first
    if check_in.count():
        check_in.click()
        expect(page.get_by_text("הגיע/ה").first).to_be_visible(timeout=20000)
        print("2. checked a client in: ok")
    else:
        print("2. nobody to check in today (skipped)")

    page.get_by_text("השבוע").first.click()
    page.get_by_text("מתאמנים").last.click()
    page.get_by_label("חיפוש").wait_for(timeout=30000)
    page.get_by_label("חיפוש").fill("א")
    page.get_by_label("חיפוש").press("Enter")
    page.wait_for_timeout(2000)
    check(page, "clients")
    page.get_by_text("05", exact=False).first.click()
    page.get_by_text("מסלול").first.wait_for(timeout=30000)
    check(page, "client")
    print("3. found a client and opened their page: ok")

    page.go_back(); h.app_ready(page)
    page.get_by_text("מספרים", exact=True).last.click()
    page.get_by_role("heading", name="מספרים מרכזיים").wait_for(timeout=30000)
    expect(page.get_by_text("הכנסות")).to_be_visible()
    check(page, "numbers")
    page.get_by_text("אני", exact=True).last.click()
    page.get_by_role("heading", name="אני").wait_for(timeout=30000)
    check(page, "me")
    print("4. numbers and settings: ok")

    print("a11y:", a11y or "ok")
    assert not a11y
