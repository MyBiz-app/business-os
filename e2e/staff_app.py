"""The MyBiz team app (Expo web), on a phone. A team member signs in and sees what needs
attention (numbers, open requests, new businesses), finds and sorts businesses, opens one (its
numbers, modules, invoices) and gives it more trial days, then handles a request: takes it,
moves its status and writes internal notes. Then the main screens in English with dark mode.
Accessibility (axe, serious and critical) is checked on every screen.

Usage: python e2e/staff_app.py <team email of a MyBiz owner> (e.g. after app.seed --demo platform)"""

import pathlib
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

APP = "http://localhost:8083"
STAFF = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
a11y: list[str] = []
errors: list[str] = []


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']}: {v['nodes'][0]['target']}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        a11y.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/staffapp-{label}.png", full_page=True)


def sign_in(page, email_label: str, send: str, code_label: str, enter: str) -> None:
    page.goto(APP)
    page.get_by_label(email_label).wait_for(timeout=60000)
    page.get_by_label(email_label).fill(STAFF)
    page.get_by_role("button", name=send).click()
    page.get_by_label(code_label).wait_for(timeout=30000)
    page.wait_for_timeout(2000)  # let the new code's email arrive (older ones are still there)
    page.get_by_label(code_label).fill(h.otp(STAFF))
    page.get_by_role("button", name=enter).click()


def tab(page, name: str) -> None:
    """Opens a tab, first going back from pushed screens (they cover the tab bar)."""
    target = page.get_by_role("tab", name=name).last
    for _ in range(4):
        if target.is_visible():
            break
        page.go_back()
        page.wait_for_timeout(800)
    target.click()


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda dialog: dialog.accept())
    sign_in(page, "אימייל", "שליחת קוד", "קוד בן 6 ספרות", "כניסה")
    page.get_by_text("פניות פתוחות").first.wait_for(timeout=60000)
    expect(page.get_by_text("עסקים חדשים השבוע")).to_be_visible()
    expect(page.get_by_text("לקוחות פעילים")).to_be_visible()
    check(page, "home")
    print("1. signed in; numbers, open requests and new businesses: ok")

    tab(page, "עסקים")
    page.get_by_label("חיפוש עסק").wait_for(timeout=30000)
    page.get_by_role("tab", name="הכי הרבה לקוחות").click()
    check(page, "businesses")
    page.get_by_label("חיפוש עסק").fill("מוסך")
    page.locator("[role=button]").filter(has_text="מוסך").first.click()
    page.get_by_role("heading", name="המספרים").wait_for(timeout=30000)
    expect(page.get_by_text("חשבוניות")).to_be_visible()
    page.get_by_role("tab", name="30").click()
    page.get_by_role("button", name="הוספת 30 ימים").click()
    expect(page.get_by_text("תקופת הניסיון מסתיימת עכשיו")).to_be_visible(timeout=20000)
    check(page, "business")
    print("2. found a business, its numbers and invoices, more trial days: ok")

    tab(page, "פניות")
    page.get_by_role("heading", name="פניות").wait_for(timeout=30000)
    check(page, "inbox")
    page.locator("[role=button]").filter(has_text="חדשה").last.click()  # the home tab, also mounted, comes first
    page.get_by_role("heading", name="סטטוס").wait_for(timeout=30000)
    page.get_by_role("button", name="אני מטפל/ת").click()
    expect(page.get_by_text("בטיפול שלך")).to_be_visible(timeout=20000)
    page.get_by_label("הערות פנימיות").fill("דיברתי איתם, שולחים הצעה מחר")
    page.get_by_role("button", name="שמירת הערות").click()
    expect(page.get_by_text("ההערות נשמרו.")).to_be_visible(timeout=20000)
    page.get_by_role("tablist", name="סטטוס").get_by_role("tab", name="טופלה").click()
    expect(page.get_by_text("עודכן.")).to_be_visible(timeout=20000)
    check(page, "request")
    print("3. took a request, wrote notes and marked it done: ok")

    tab(page, "אני")
    page.get_by_role("heading", name="אני").wait_for(timeout=30000)
    expect(page.get_by_text("הרמה שלך", exact=False)).to_be_visible()
    check(page, "me")
    print("4. settings and permissions: ok")

    dark = b.new_context(
        locale="en-US", viewport={"width": 390, "height": 844}, is_mobile=True, color_scheme="dark"
    ).new_page()
    dark.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(dark, "Email", "Send code", "6-digit code", "Sign in")
    dark.get_by_text("Open requests").first.wait_for(timeout=60000)
    check(dark, "home-en-dark")
    tab(dark, "Businesses")
    dark.locator("[role=button]").filter(has_text="clients").first.click()
    dark.get_by_role("heading", name="The numbers").wait_for(timeout=30000)
    check(dark, "business-en-dark")
    tab(dark, "Inbox")
    dark.get_by_role("heading", name="Inbox").wait_for(timeout=30000)
    check(dark, "inbox-en-dark")
    print("5. English and dark mode: ok")

    print("page errors:", errors or "none")
    print("a11y:", a11y or "ok")
    assert not a11y and not errors
