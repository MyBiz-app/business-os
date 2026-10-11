"""On-site jobs in the business app (#42): the owner of the air-conditioning demo opens the team's
jobs of the day from Today: each job with its time, client, address, navigation and call, and
moves one on its way. On a phone, Hebrew/light, with axe.

Needs the business app (`pnpm dev:business`) and the demo (`--demo jobs`).

Usage: python e2e/jobs_app.py <owner email of the demo>"""

import pathlib
import re
import sys

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

APP = "http://localhost:8082"
OWNER = sys.argv[1]
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
    page.screenshot(path=f"{h.OUT}/jobs-bizapp-{label}.png", full_page=True)


def sign_in(page, email_label: str, send: str, code_label: str, enter: str) -> None:
    page.goto(APP)
    page.get_by_label(email_label).wait_for(timeout=60000)
    page.get_by_label(email_label).fill(OWNER)
    page.get_by_role("button", name=send).click()
    page.get_by_label(code_label).wait_for(timeout=30000)
    page.wait_for_timeout(2000)  # let the new code's email arrive (older ones are still there)
    page.get_by_label(code_label).fill(h.otp(OWNER))
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


with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, name = conn.execute("""
        SELECT t.id, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s AND t.vertical = 'ac_technicians'
        ORDER BY t.created_at DESC LIMIT 1
    """, (OWNER,)).fetchone()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, "אימייל", "שליחת קוד", "קוד בן 6 ספרות", "כניסה")
    page.wait_for_timeout(3000)
    page.evaluate("id => localStorage.setItem('business.tenant', id)", str(tenant_id))
    page.goto(APP)
    page.get_by_role("heading", name=name).wait_for(timeout=60000)
    print(f"1. signed in to {name}: ok")

    page.get_by_role("button", name="העבודות שלי היום").click()
    page.get_by_role("heading", name="העבודות שלי").wait_for(timeout=30000)
    page.get_by_role("tablist", name="של מי").get_by_role("tab", name="כולם").click()
    page.get_by_role("heading", name="העבודות של הצוות").wait_for(timeout=30000)
    expect(page.get_by_role("button", name="Waze").first).to_be_visible(timeout=30000)
    jobs = page.get_by_role("button", name="פרטי העבודה").count()
    check(page, "team-day")
    print(f"2. the team's jobs today: {jobs} jobs with navigation: ok")

    go = page.get_by_role("button", name=re.compile("^יצאתי לדרך"))
    if go.count():
        before = page.get_by_text("בדרך", exact=True).count()
        go.first.click()
        expect(page.get_by_text("בדרך", exact=True)).to_have_count(before + 1, timeout=20000)
        print("3. a job moved on its way: ok")
    print("errors:", errors or "none", "| a11y:", a11y or "none")
    assert not errors and not a11y
