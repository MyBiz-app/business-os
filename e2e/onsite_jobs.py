"""On-site jobs (#42) in the business web app, on the air-conditioning demo
(`python -m app.seed --owner-email <owner> --demo jobs`): a client's card lists their addresses and
a new one is added; a job is booked at that address; the job's page shows the address with
navigation links and moves on the way → in progress → done, which checks the client in.
Hebrew/light on a wide screen, then the job in English/dark on a phone.

Usage: python e2e/onsite_jobs.py <owner email of the demo> (its password is helpers.PASSWORD)"""

import pathlib
import sys
import time
from datetime import timedelta

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
STREET = f"המלאכה {time.time_ns() % 100 + 1}"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, client_id, first = conn.execute("""
        SELECT t.id, c.id, c.first_name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id
        JOIN app.clients c ON c.tenant_id = t.id AND c.status = 'active'
        WHERE u.email = %s AND t.vertical = 'ac_technicians'
        ORDER BY t.created_at DESC, c.created_at LIMIT 1
    """, (OWNER,)).fetchone()
    service_id = conn.execute("""
        SELECT id FROM app.services WHERE tenant_id = %s AND on_site
        ORDER BY duration_minutes, name LIMIT 1
    """, (tenant_id,)).fetchone()[0]
DAY = (h.local_today() + timedelta(days=21)).isoformat()  # past the demo's booked weeks


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        issues.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/jobs-{label}.png", full_page=True)


def as_company(context) -> None:
    context.add_cookies([{"name": "TENANT_ID", "value": str(tenant_id), "url": h.BASE}])


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    context = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    h.login(page, OWNER)
    as_company(context)

    # 1. The client's addresses; a new one is added.
    page.goto(f"{h.BASE}/clients/{client_id}"); h.ready(page)
    section = page.locator("section[aria-labelledby=addresses-heading]")
    expect(section.get_by_role("heading", name="כתובות")).to_be_visible()
    section.get_by_text("הוספת כתובת").first.click()
    form = section.locator("details").last.locator("form")
    form.get_by_label("רחוב ומספר").fill(STREET)
    form.get_by_label("עיר").fill("חולון")
    form.get_by_label("קומה, דירה").fill("קומה 2")
    form.get_by_label("איך נכנסים").fill("קוד בשער 4321")
    form.get_by_role("button", name="הוספת כתובת").click()
    expect(section.get_by_text(f"{STREET}, קומה 2, חולון")).to_be_visible()
    check(page, "client-addresses")
    print("1. client card: addresses listed, a new one added: ok")

    # 2. A job at that address.
    page.goto(f"{h.BASE}/schedule/appointment?service={service_id}&date={DAY}&q={first}"); h.ready(page)
    expect(page.get_by_text("עבודה בשטח: בוחרים לקוח וכתובת.")).to_be_visible()
    page.locator("label", has_text=STREET).locator("input[type=radio]").check()
    check(page, "book-job")
    page.get_by_role("button", name="קביעת התור").click()
    page.wait_for_url("**/schedule/**booked=1"); h.ready(page)
    panel = page.locator("section[aria-labelledby=job-heading]")
    expect(panel.get_by_text(f"{STREET}, קומה 2, חולון")).to_be_visible()
    expect(panel.get_by_text("קוד בשער 4321")).to_be_visible()
    assert "waze.com" in panel.get_by_role("link", name="Waze").get_attribute("href")
    check(page, "job")
    print("2. job booked at the address, navigation links shown: ok")

    # 3. On the way → in progress → done (the client is checked in).
    for action, status in (("יצאתי לדרך", "בדרך"), ("התחלת עבודה", "בעבודה"), ("העבודה הושלמה", "הושלם")):
        panel.get_by_role("button", name=action).click()
        expect(panel.locator("li[aria-current=step]")).to_have_text(status)
    expect(page.locator("section[aria-labelledby=roster-heading]").get_by_text("הגיע", exact=True).first).to_be_visible()
    job_url = page.url.split("?")[0]
    check(page, "job-done")
    print("3. on the way, in progress, done; the client is checked in: ok")

    # 4. English/dark on a phone.
    phone = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844})
    page = phone.new_page()
    h.login(page, OWNER)
    as_company(phone)
    phone.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    page.goto(job_url); h.ready(page)
    expect(page.locator("section[aria-labelledby=job-heading]").get_by_text("Done").first).to_be_visible()
    check(page, "job-en-dark")
    print("4. the job on a phone (English, dark): ok")
    b.close()

if issues:
    print("ISSUES:", *issues, sep="\n  ")
    sys.exit(1)
print("onsite_jobs: all steps passed, no accessibility issues")
