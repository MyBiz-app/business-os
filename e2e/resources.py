"""Courts and rooms by the hour (#41) in the business web app: a room of the main branch is
marked "for rent by the hour" with opening hours, a resource service gets a price per hour and
its court, and the front desk reserves the court for a client from the day grid, which then
shows the reservation. Hebrew/light on a wide screen, then the grid in English/dark on a phone.

Usage: python e2e/resources.py <owner email with data> (its password is helpers.PASSWORD)"""

import pathlib
import re
import sys
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
COURT = f"מגרש פאדל {time.time_ns() % 10000}"
SERVICE = f"השכרת מגרש {time.time_ns() % 10000}"
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
    page.screenshot(path=f"{h.OUT}/resources-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    h.login(page, OWNER)

    # 1. A room of the main branch becomes a court for rent, open every day 08:00-22:00.
    page.goto(f"{h.BASE}/locations"); h.ready(page)
    page.locator("main a[href^='/locations/']:not([href$='/new'])").first.click()
    page.wait_for_url("**/locations/**"); h.ready(page)
    add = page.locator("form").filter(has=page.get_by_role("button", name="הוספת חדר"))
    add.get_by_label("שם החדר").fill(COURT)
    add.get_by_label("להשכרה לפי שעה").check()
    add.get_by_role("button", name="הוספת חדר").click()
    page.get_by_role("link", name=f"שעות פתיחה: {COURT}").click()
    page.wait_for_url("**/rooms/**"); h.ready(page)
    for button in page.get_by_role("button", name="הוספת טווח –").all():
        button.click()
    page.get_by_role("button", name="שמירה").click()
    expect(page.get_by_text("נשמר", exact=False).first).to_be_visible(timeout=20000)
    check(page, "room-hours")
    print("1. a court for rent with opening hours: ok")

    # 2. A resource service: by the hour, 60-120 minutes in 30-minute steps, ₪140 an hour.
    page.goto(f"{h.BASE}/services/new"); h.ready(page)
    page.get_by_label("שם", exact=True).fill(SERVICE)
    page.get_by_label("איך מזמינים").select_option("resource")
    page.get_by_label("מחיר לשעה", exact=False).fill("140")
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/services"); h.ready(page)
    page.get_by_role("link", name=SERVICE).first.click()
    page.get_by_role("heading", name="מגרשים וחדרים").wait_for(timeout=30000)
    page.get_by_label(COURT).check()
    page.get_by_role("button", name="שמירה").last.click()
    expect(page.get_by_text("נשמר", exact=False).first).to_be_visible(timeout=20000)
    check(page, "service")
    print("2. a service by the hour, served by the court: ok")

    # 3. The front desk reserves the court tomorrow for 90 minutes, from the day grid.
    page.goto(f"{h.BASE}/resources"); h.ready(page)
    page.get_by_role("link", name="היום הבא").click()
    page.wait_for_url("**/resources?date=**"); h.ready(page)
    what = page.locator("select[name=service]")
    what.select_option(what.locator("option", has_text=SERVICE).get_attribute("value"))
    page.locator("select[name=minutes]").select_option("90")
    page.get_by_role("button", name="הצגת זמנים").first.click(); h.ready(page)
    expect(page.get_by_text(re.compile(r"מחיר:.*210"))).to_be_visible(timeout=20000)
    check(page, "reserve")
    page.get_by_role("button", name="הזמנה", exact=True).click()
    page.wait_for_url("**/schedule/**booked=1**", timeout=30000); h.ready(page)
    print("3. reserved the court for a client: ok")

    page.goto(f"{h.BASE}/resources"); h.ready(page)
    page.get_by_role("link", name="היום הבא").click()
    page.wait_for_url("**/resources?date=**"); h.ready(page)
    expect(page.get_by_role("list", name=COURT).get_by_role("link")).to_have_count(1)
    check(page, "grid")
    print("4. the reservation is on the day grid: ok")

    # English, dark, a phone: the grid scrolls sideways inside its own region, not the page.
    phone = b.new_context(locale="en-US", viewport={"width": 390, "height": 844}, color_scheme="dark").new_page()
    phone.context.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    h.login(phone, OWNER)
    phone.goto(f"{h.BASE}/resources"); h.ready(phone)
    phone.get_by_role("heading", name="Courts & rooms").wait_for(timeout=30000)
    check(phone, "grid-en-dark-phone")
    print("5. English, dark, phone: ok")

    print("issues:", issues or "none")
    assert not issues
