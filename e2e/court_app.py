"""Booking a court in the client app (#41): a new client joins a business that rents courts by
the hour, opens "Book a court" from home, picks how long, a day and a time, pays (a simulated
payment) and sees the receipt. On a phone, Hebrew/light, with axe on every screen.

Needs the client app (`pnpm dev:app`) and a business with a court for rent and a service by the
hour (run e2e/resources.py first). The business is set to not ask for a health declaration.

Usage: python e2e/court_app.py <owner email of that business>"""

import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
CLIENT = f"court{time.time_ns()}@example.com"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    code, name = conn.execute("""
        SELECT t.join_code, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        ORDER BY t.created_at DESC LIMIT 1
    """, (OWNER,)).fetchone()
    conn.execute("UPDATE app.tenants SET requires_health_declaration = false WHERE join_code = %s", (code,))


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    if page.evaluate("document.documentElement.scrollWidth - window.innerWidth") > 1:
        issues.append(f"{label}: horizontal overflow")
    page.screenshot(path=f"{h.OUT}/court-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    page.goto(h.APP); page.wait_for_url("**/sign-in", timeout=60000)
    page.get_by_label("אימייל").fill(CLIENT)
    page.get_by_role("button", name="שליחת קוד").click()
    page.get_by_label("קוד בן 6 ספרות").fill(h.otp(CLIENT))
    page.get_by_role("button", name="כניסה").click(); page.wait_for_url("**/join")
    page.get_by_label("קוד הצטרפות").fill(code)
    page.get_by_role("button", name="המשך").click()
    page.get_by_label("שם פרטי").fill("נועם")
    page.get_by_role("button", name=f"הצטרפות ל{name}").click(); page.wait_for_url("**/home")
    print(f"1. joined {name}: ok")

    page.get_by_role("button", name="הזמנת מגרש").first.click()
    page.wait_for_url("**/court")
    page.get_by_role("heading", name="הזמנת מגרש").wait_for(timeout=30000)
    what = page.get_by_role("radiogroup", name="מה")
    if what.count():
        what.get_by_role("radio").first.click()
    page.get_by_role("radiogroup", name="לכמה זמן").get_by_role("radio").nth(1).click()  # 90 minutes
    page.get_by_role("tablist", name="מתי?").get_by_role("tab").nth(2).click()
    times = page.get_by_role("radiogroup", name="באיזו שעה?")
    times.get_by_role("radio").first.wait_for(timeout=30000)
    times.get_by_role("radio").first.click()
    check(page, "choose")
    page.get_by_role("button", name=re.compile("^תשלום .* והזמנה$")).click()
    expect(page.get_by_role("heading", name="הוזמן!")).to_be_visible(timeout=30000)
    expect(page.get_by_text(re.compile("^שולם "))).to_be_visible()
    check(page, "booked")
    print("2. picked a length, a day and a time, paid and booked: ok")

    page.get_by_role("button", name="הקבלה").click()
    page.wait_for_url("**/receipt/**")
    expect(page.get_by_text(re.compile("מגרש פאדל")).last).to_be_visible(timeout=30000)
    check(page, "receipt")
    print("3. the receipt says what was paid: ok")

    print("issues:", issues or "none")
    assert not issues
