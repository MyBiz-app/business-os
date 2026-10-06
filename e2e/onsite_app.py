"""On-site jobs in the client app (#42): a new client joins the air-conditioning demo, adds their
home under "My addresses", then books an AC service there; the booking shows the address.
On a phone, Hebrew/light, with axe on every screen.

Needs the client app (`pnpm dev:app`) and the air-conditioning demo
(`python -m app.seed --owner-email <owner> --demo jobs`).

Usage: python e2e/onsite_app.py <owner email of the demo>"""

import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
CLIENT = f"jobs{time.time_ns()}@example.com"
STREET = f"הגפן {time.time_ns() % 90 + 1}"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    code, name = conn.execute("""
        SELECT t.join_code, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s AND t.vertical = 'ac_technicians'
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
    page.screenshot(path=f"{h.OUT}/jobs-app-{label}.png", full_page=True)


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
    page.get_by_label("שם פרטי").fill("אורי")
    page.get_by_role("button", name=f"הצטרפות ל{name}").click(); page.wait_for_url("**/home")
    print(f"1. joined {name}: ok")

    # 2. My addresses: add home.
    page.get_by_role("tab", name=re.compile("פרופיל")).click()
    page.get_by_role("button", name="הכתובות שלי").last.click()
    page.wait_for_url("**/addresses")
    page.get_by_role("heading", name="הכתובות שלי").wait_for(timeout=30000)
    page.get_by_label("רחוב ומספר").fill(STREET)
    page.get_by_label("עיר", exact=True).fill("רעננה")
    page.get_by_label("איך נכנסים").fill("קומה 1, דלת ימין")
    page.get_by_role("button", name="הוספת כתובת").click()
    expect(page.get_by_text(f"{STREET}, רעננה")).to_be_visible(timeout=30000)
    check(page, "addresses")
    print("2. added a home address: ok")

    # 3. An AC service at home.
    page.goto(f"{h.APP}/home"); h.app_ready(page)
    page.get_by_role("button", name="קביעת תור").first.click()
    page.wait_for_url("**/appointment")
    page.get_by_role("radiogroup", name="מה תרצו?").get_by_role("radio", name=re.compile("ניקוי ושירות מזגן")).click()
    days = page.get_by_role("tablist", name="מתי?").get_by_role("tab")
    times = page.get_by_role("radiogroup", name="באיזו שעה?")
    for i in range(days.count() - 1, 0, -1):  # the demo's calendar is full near today
        days.nth(i).click()
        page.wait_for_timeout(800)
        if times.get_by_role("radio").count():
            break
    times.get_by_role("radio").first.click()
    where = page.get_by_role("radiogroup", name="איפה?")
    expect(where.get_by_role("radio", name=f"{STREET}, רעננה")).to_have_attribute("aria-checked", "true")
    check(page, "book")
    page.get_by_role("button", name=re.compile("^קביעת תור ל")).click()
    expect(page.get_by_role("heading", name="התור נקבע!")).to_be_visible(timeout=30000)
    with psycopg.connect(h.DATABASE_URL) as conn:
        booked = conn.execute("""
            SELECT s.address, s.job_status FROM app.bookings b JOIN app.clients c ON c.id = b.client_id
            JOIN app.sessions s ON s.id = b.session_id WHERE c.email = %s
        """, (CLIENT,)).fetchone()
    assert booked == (f"{STREET}, רעננה", "scheduled"), booked
    print("3. booked an AC service at home: ok")

    print("issues:", issues or "none")
    assert not issues
