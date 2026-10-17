"""Round 6 end to end on the curated demo: the time clock with approved hours, the month's payroll
run with a payslip PDF, the "Move to MyBiz" hub with an Excel export (check, import, undo), and an
issued document with its PDF.

    uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/round6.py

Seeds the curated demo for a new owner, so the API needs the same local stack as dod.py.
Nothing is sent to anyone: the move only creates records, and the payslip is a download.
"""

import pathlib
import re
import subprocess
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"round6{time.time_ns()}@example.com"
database = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
axe = Axe()
issues: list[str] = []


def check(page, label: str) -> None:
    found = [v for v in axe.run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    issues.extend(f"{label}: {v['id']} {[n['target'] for n in v['nodes']]}" for v in found)


def seed(*args: str) -> None:
    subprocess.run(
        ["uv", "run", "--quiet", "python", "-m", "app.seed", *args, "--months", "1",
         "--database-url", database],
        cwd="apps/api", check=True, capture_output=True,
    )  # fmt: skip


def pdf(page, url: str, label: str) -> None:
    """The download behind a link is a real PDF."""
    response = page.request.get(url)
    assert response.status == 200, f"{label}: status {response.status}"
    assert "application/pdf" in response.headers.get("content-type", ""), label
    assert response.body()[:4] == b"%PDF", f"{label}: not a PDF"


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(owner_email)
    page.get_by_label("סיסמה", exact=True).fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(owner_email)); h.to_onboarding(page)
    seed("--owner-email", owner_email, "--demo", "curated")
    print("1. curated demo seeded")

    # Work in the gym: the three demo businesses were created together, so pick it by name.
    page.goto(f"{h.BASE}/dashboard"); h.ready(page)
    if "Adir fitness" not in page.get_by_role("heading", level=1).inner_text():
        page.locator("button[aria-expanded][aria-controls]").first.click()
        page.get_by_role("dialog").get_by_role("button", name=re.compile("Adir fitness")).click()
        page.wait_for_url("**/dashboard"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_contain_text("Adir fitness")

    # The time clock: the demo team's month of hours is there and approved.
    page.goto(f"{h.BASE}/team/time-clock"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("שעון נוכחות")
    expect(page.get_by_text("אושר", exact=True).first).to_be_visible()
    check(page, "time clock")
    page.screenshot(path=f"{h.OUT}/round6-time-clock.png", full_page=True)
    print("2. time clock: the team's month is approved")

    # The payroll run: worked out from the pay terms and the approved hours, never approved yet.
    page.goto(f"{h.BASE}/team/payroll"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("הרצת שכר")
    expect(page.get_by_text("לוודא שהשעות של כולם מאושרות").first).to_be_visible()
    people = page.locator("#people-title").locator("xpath=ancestor::section[1]").locator("ul > li")
    assert people.count() >= 2, "the run has a line for each person with pay terms"
    check(page, "payroll run")
    page.screenshot(path=f"{h.OUT}/round6-payroll.png", full_page=True)
    # Acknowledge what the demo leaves open (no bank account or Form 101 yet), then walk the
    # stages; the owner approves, and only then are payslips offered.
    for index in range(people.count()):
        people.nth(index).get_by_role("button").click()
        sheet = page.get_by_role("dialog")
        acknowledge = sheet.get_by_role("button", name="אישור האזהרה")
        while acknowledge.count():
            before = acknowledge.count()
            acknowledge.first.click()
            expect(acknowledge).to_have_count(before - 1, timeout=15000)
        sheet.get_by_role("button", name="סגירה").click()
    for step, hint in (
        ("נעילת השעות והמשך", "להוסיף בונוסים"),
        ("המשך לבדיקה", "לתקן כל שגיאה"),
        ("אישור ההרצה", "ההרצה אושרה ונעלה"),
    ):
        page.get_by_role("button", name=step).click()
        expect(page.get_by_text(re.compile(hint)).first).to_be_visible(timeout=30000)
    people.first.get_by_role("button").click()
    link = page.get_by_role("link", name="תלוש שכר (PDF)")
    expect(link).to_be_visible()
    pdf(page, f"{h.BASE}{link.get_attribute('href')}", "payslip")
    month = re.search(r"month=(\d{4}-\d{2})", link.get_attribute("href")).group(1)
    export = page.request.get(f"{h.BASE}/team/payroll/export?month={month}&format=csv")
    assert export.status == 200 and len(export.body()) > 50, "the run exports"
    print("3. payroll run: hours locked, reviewed, approved; payslip PDF and export download")

    # Move to MyBiz: the demo's Excel export waits as a draft; check it, import it, undo it.
    page.goto(f"{h.BASE}/migration"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("עוברים ל-MyBiz")
    expect(page.get_by_text("previous-system-clients.xlsx").first).to_be_visible()
    check(page, "migration")
    page.get_by_role("button", name="בדיקת מה ייווצר").click()
    expect(page.get_by_text(re.compile("האימייל אינו תקין")).first).to_be_visible(timeout=30000)
    expect(page.get_by_text(re.compile("כפילות|כפילויות")).first).to_be_visible()
    page.screenshot(path=f"{h.OUT}/round6-migration-check.png", full_page=True)
    page.get_by_role("button", name=re.compile("^ייבוא ")).click()
    expect(page.get_by_role("heading", name=re.compile("^הועברו ל-MyBiz"))).to_be_visible(timeout=30000)
    print("4. move from Excel: check shows a duplicate and a bad email, import creates the clients")
    page.goto(f"{h.BASE}/migration"); h.ready(page)
    page.get_by_role("button", name="ביטול הייבוא").first.click()
    expect(page.get_by_text(re.compile("תוסר|יוסרו")).first).to_be_visible(timeout=30000)
    page.get_by_role("button", name="הסרה", exact=True).click()
    expect(page.get_by_role("heading", name="ייבואים שאפשר לבטל")).to_have_count(0, timeout=30000)
    print("5. the import is undone: ok")

    # An issued document: a quote with one line, and its PDF.
    page.goto(f"{h.BASE}/invoices/new?kind=quote"); h.ready(page)
    page.get_by_label("שם במסמך").fill("לקוח לדוגמה")
    page.get_by_label("פריט 1", exact=True).fill("חבילת אימונים")
    page.get_by_label("כמות", exact=True).fill("2")
    page.get_by_label(re.compile("^מחיר ליחידה")).fill("150")
    page.get_by_role("button", name="הפקת המסמך").click()
    page.wait_for_url(re.compile(r".*/invoices/[0-9a-f-]{36}$"))
    h.ready(page)
    expect(page.get_by_text("הצעת מחיר").first).to_be_visible()
    pdf(page, f"{page.url}/pdf", "quote")
    page.goto(f"{h.BASE}/invoices"); h.ready(page)
    expect(page.get_by_text("לקוח לדוגמה").first).to_be_visible()
    check(page, "documents")
    print("6. issued a quote and downloaded its PDF: ok")
    b.close()

if issues:  # reported, not failing: dod.py treats the same findings on other pages the same way
    print("a11y findings to fix later:", *issues, sep="\n  ")
print("round6: ok")
