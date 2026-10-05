"""The MyBiz console: an owner builds the team (owner, manager, employee), each level sees
only what it may, the primary owner is protected, and every change is in the audit log.
Pass a console owner's email."""

import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
PRIMARY = "adire7399@gmail.com"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
manager_email = f"manager{stamp}@example.com"
employee_email = f"employee{stamp}@example.com"
a11y: list[str] = []


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']}: {v['nodes'][0]['target']}")


def sign_up(browser, email: str):
    page = browser.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email))
    return page


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    h.login(owner, OWNER)
    owner.goto(f"{h.BASE}/platform"); h.ready(owner)
    nav = owner.get_by_role("navigation", name="ניווט בקונסולה")
    for item in ("סקירה", "עסקים", "תיבת פניות", "חיוב", "צוות MyBiz", "יומן פעולות"):
        expect(nav.get_by_role("link", name=item)).to_be_visible()
    check(owner, "overview")
    owner.screenshot(path=f"{h.OUT}/console-overview.png", full_page=True)

    nav.get_by_role("link", name="צוות MyBiz").click(); owner.wait_for_url("**/platform/team")
    h.ready(owner)
    team = owner.get_by_role("main")
    expect(team.get_by_text(PRIMARY)).to_be_visible()
    expect(team.get_by_text("מוגן")).to_be_visible()

    # A manager who may manage employees and the inbox.
    form = owner.get_by_role("region", name="הוספת איש צוות")
    form.get_by_label("אימייל").fill(manager_email)
    form.get_by_role("radio", name="מנהל/ת").check()
    form.get_by_role("checkbox", name=re.compile(r"ניהול עובדים")).check()
    form.get_by_role("checkbox", name=re.compile("תיבת פניות")).check()
    form.get_by_role("button", name="שמירה").click()
    expect(owner.get_by_role("main").get_by_text(manager_email)).to_be_visible()
    check(owner, "team")
    owner.screenshot(path=f"{h.OUT}/console-team.png", full_page=True)
    print("1. owner added a manager: ok")

    # The manager signs up, sees only their parts, and adds an employee.
    manager = sign_up(b, manager_email)
    manager.goto(f"{h.BASE}/platform"); h.ready(manager)
    mnav = manager.get_by_role("navigation", name="ניווט בקונסולה")
    expect(mnav.get_by_role("link", name="צוות MyBiz")).to_be_visible()
    expect(mnav.get_by_role("link", name="תיבת פניות")).to_be_visible()
    expect(mnav.get_by_role("link", name="עסקים")).to_have_count(0)
    expect(mnav.get_by_role("link", name="יומן פעולות")).to_have_count(0)
    assert manager.goto(f"{h.BASE}/platform/audit").status == 404
    assert manager.goto(f"{h.BASE}/platform/businesses").status == 404

    manager.goto(f"{h.BASE}/platform/team"); h.ready(manager)
    mform = manager.get_by_role("region", name="הוספת איש צוות")
    expect(mform.get_by_role("radio", name="בעלים")).to_have_count(0)  # not theirs to give
    mform.get_by_label("אימייל").fill(employee_email)
    mform.get_by_role("checkbox", name=re.compile("תיבת פניות")).check()
    mform.get_by_role("button", name="שמירה").click()
    expect(manager.get_by_role("main").get_by_text(employee_email)).to_be_visible()
    print("2. manager sees only their parts and added an employee: ok")

    # The employee sees only the inbox.
    employee = sign_up(b, employee_email)
    employee.goto(f"{h.BASE}/platform"); h.ready(employee)
    enav = employee.get_by_role("navigation", name="ניווט בקונסולה")
    expect(enav.get_by_role("link", name="תיבת פניות")).to_be_visible()
    expect(enav.get_by_role("link", name="צוות MyBiz")).to_have_count(0)
    employee.goto(f"{h.BASE}/platform/inbox"); check(employee, "inbox")
    assert employee.goto(f"{h.BASE}/platform/team").status == 404
    print("3. employee sees only the inbox: ok")

    # An owner can enter a business and fix something; the business's owner sees it.
    owner.goto(f"{h.BASE}/platform/businesses"); h.ready(owner)
    # A business this person doesn't own, so they get in as MyBiz staff.
    row = owner.locator("tbody tr").filter(has_not_text=OWNER).first
    row.get_by_role("link").first.click()
    owner.wait_for_url("**/platform/businesses/**"); h.ready(owner)
    business_name = owner.get_by_role("heading", level=1).inner_text()
    check(owner, "business")
    owner.screenshot(path=f"{h.OUT}/console-business.png", full_page=True)
    owner.get_by_role("button", name="כניסה לעסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)
    expect(owner.get_by_role("status").filter(has_text="כצוות MyBiz")).to_be_visible()
    owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
    owner.get_by_label("שם פרטי").fill("לקוח מתמיכה")
    owner.get_by_role("button", name="יצירה").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$"))
    owner.get_by_role("button", name="יציאה מהעסק").click(); owner.wait_for_url("**/platform")
    h.ready(owner)
    print(f"5. owner entered {business_name} and added a client (audited): ok")

    # The audit log (owners only) has every change.
    owner.goto(f"{h.BASE}/platform/audit"); h.ready(owner)
    rows = owner.get_by_role("region", name="יומן פעולות").locator("tbody tr")
    assert rows.count() >= 3
    expect(rows.filter(has_text="ביצע/ה שינוי בעסק").first).to_be_visible()
    expect(rows.filter(has_text="הוסיף/ה איש צוות").first).to_be_visible()
    check(owner, "audit")
    owner.screenshot(path=f"{h.OUT}/console-audit.png", full_page=True)

    with psycopg.connect(h.DATABASE_URL) as conn:
        levels = dict(
            conn.execute(
                "SELECT email, level FROM app.platform_staff WHERE email = ANY(%s)",
                ([manager_email, employee_email, PRIMARY],),
            ).fetchall()
        )
    assert levels == {manager_email: "manager", employee_email: "employee", PRIMARY: "primary_owner"}, levels
    print("6. audit log and levels: ok")

    print("a11y:", a11y or "ok")
    assert not a11y
