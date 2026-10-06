"""Pets in the client app (#43): a new owner joins the pet grooming demo, adds their dog under
"My pets" (with its details), then books a grooming appointment, where the dog is who comes.
On a phone, Hebrew/light, with axe on every screen.

Needs the client app (`pnpm dev:app`) and the pet grooming demo
(`python -m app.seed --owner-email <owner> --demo pets`).

Usage: python e2e/pets_app.py <owner email of the demo>"""

import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
CLIENT = f"pets{time.time_ns()}@example.com"
PET = "בוני"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    code, name = conn.execute("""
        SELECT t.join_code, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s AND t.vertical = 'pet_grooming'
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
    page.screenshot(path=f"{h.OUT}/pets-app-{label}.png", full_page=True)


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
    page.get_by_label("שם פרטי").fill("גלית")
    page.get_by_role("button", name=f"הצטרפות ל{name}").click(); page.wait_for_url("**/home")
    print(f"1. joined {name}: ok")

    # 2. My pets: add the dog with its details.
    page.get_by_role("tab", name=re.compile("פרופיל")).click()
    page.get_by_role("button", name="חיות המחמד שלי").last.click()
    page.wait_for_url("**/dependents")
    page.get_by_role("heading", name="חיות המחמד שלי").wait_for(timeout=30000)
    page.get_by_label("שם", exact=True).fill(PET)
    page.get_by_role("tablist", name="סוג").get_by_role("tab", name="כלב").click()
    page.get_by_label("גזע").fill("מלטז")
    page.get_by_role("tablist", name="גודל").get_by_role("tab", name="קטן").click()
    page.get_by_role("button", name="הוספת חיית מחמד").click()
    expect(page.get_by_text(PET, exact=True)).to_be_visible(timeout=30000)
    check(page, "my-pets")
    print(f"2. added {PET} under my pets: ok")

    # 3. A grooming appointment, for the dog.
    page.goto(f"{h.APP}/home"); h.app_ready(page)
    page.get_by_role("button", name="קביעת תור").first.click()
    page.wait_for_url("**/appointment")
    page.get_by_role("radiogroup", name="מה תרצו?").get_by_role("radio").first.click()
    page.get_by_role("tablist", name="מתי?").get_by_role("tab").nth(1).click()
    times = page.get_by_role("radiogroup", name="באיזו שעה?")
    times.get_by_role("radio").first.wait_for(timeout=30000)
    times.get_by_role("radio").first.click()
    who = page.get_by_role("radiogroup", name="מי מגיע?")
    expect(who.get_by_role("radio", name=PET)).to_have_attribute("aria-checked", "true")
    expect(who.get_by_role("radio", name="אני")).to_have_count(0)  # a groomer needs the pet
    check(page, "book")
    page.get_by_role("button", name=re.compile("^קביעת תור ל")).click()
    expect(page.get_by_role("heading", name="התור נקבע!")).to_be_visible(timeout=30000)
    check(page, "booked")
    with psycopg.connect(h.DATABASE_URL) as conn:
        booked_for = conn.execute("""
            SELECT d.name FROM app.bookings b JOIN app.clients c ON c.id = b.client_id
            JOIN app.dependents d ON d.id = b.dependent_id WHERE c.email = %s
        """, (CLIENT,)).fetchone()
    assert booked_for == (PET,), booked_for
    print(f"3. booked a grooming appointment for {PET}: ok")

    print("issues:", issues or "none")
    assert not issues
