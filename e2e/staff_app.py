"""The MyBiz team app (Expo web): a team member signs in, sees what needs attention, searches
businesses, and handles a request from the inbox. Usage: python e2e/staff_app.py <team email>"""

import pathlib
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

APP = "http://localhost:8083"
STAFF = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
a11y: list[str] = []


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']}: {v['nodes'][0]['target']}")
    page.screenshot(path=f"{h.OUT}/staffapp-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
    page.goto(APP)
    page.get_by_label("אימייל").wait_for(timeout=60000)
    page.get_by_label("אימייל").fill(STAFF)
    page.get_by_role("button", name="שליחת קוד").click()
    page.get_by_label("קוד בן 6 ספרות").wait_for(timeout=30000)
    page.get_by_label("קוד בן 6 ספרות").fill(h.otp(STAFF))
    page.get_by_role("button", name="כניסה").click()
    page.get_by_text("פניות פתוחות").wait_for(timeout=60000)
    expect(page.get_by_text("עסקים חדשים השבוע")).to_be_visible()
    check(page, "home")
    print("1. signed in, the day's work is showing: ok")

    page.get_by_text("עסקים", exact=True).last.click()
    page.get_by_label("חיפוש עסק").wait_for(timeout=30000)
    page.get_by_label("חיפוש עסק").fill("פלואו")
    page.wait_for_timeout(1500)
    expect(page.get_by_text("סטודיו פלואו (דמו)").first).to_be_visible()
    check(page, "businesses")
    print("2. found a business: ok")

    page.get_by_text("פניות", exact=True).last.click()
    page.get_by_role("heading", name="פניות").wait_for(timeout=30000)
    take = page.get_by_role("button", name="אני מטפל/ת").first
    if take.count():
        take.click()
        page.wait_for_timeout(2500)
        expect(page.get_by_text("בטיפול").first).to_be_visible()
        print("3. took a request: ok")
    else:
        print("3. no open request to take (skipped)")
    check(page, "inbox")

    page.get_by_text("אני", exact=True).last.click()
    page.get_by_role("heading", name="אני").wait_for(timeout=30000)
    expect(page.get_by_text("הרמה שלך", exact=False)).to_be_visible()
    check(page, "me")
    print("4. settings and permissions: ok")

    print("a11y:", a11y or "ok")
    assert not a11y
