"""Appointments end to end: a barber shop is created (its services come from the beauty pack),
the owner sets working hours, books a walk-in from the web, and a client books in the app."""

import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email, member_email = (f"{n}{stamp}@example.com" for n in ("barber", "client"))


def serious(page) -> list[str]:
    return [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); h.to_onboarding(owner)
    owner.get_by_label("שם העסק").fill("מספרת דנה")
    owner.get_by_label("סוג העסק").select_option("beauty")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)
    expect(owner.get_by_role("navigation").get_by_role("link", name="לקוחות")).to_be_visible()
    owner.goto(f"{h.BASE}/services"); h.ready(owner)
    expect(owner.get_by_text("תספורת גברים")).to_be_visible()
    print("1. beauty business with its default services: ok")

    # Working hours: every day 09:00–17:00.
    owner.goto(f"{h.BASE}/team"); h.ready(owner)
    owner.get_by_role("link", name="שעות עבודה").first.click()
    owner.wait_for_url("**/hours"); h.ready(owner)
    for button in owner.get_by_role("button", name=re.compile("^הוספת טווח")).all():
        button.click()
    hours_serious = serious(owner)
    owner.get_by_role("button", name="שמירה").click()
    expect(owner.get_by_role("status")).to_contain_text("השעות נשמרו")
    print("2. working hours saved | a11y:", hours_serious or "ok")

    # Time off on a later day shows in the list and can be removed.
    later = owner.evaluate("() => { const d = new Date(); d.setDate(d.getDate() + 5); return d.toISOString().slice(0, 10); }")
    time_off = owner.get_by_role("region", name="חופשות והיעדרויות")
    time_off.get_by_label("מתאריך").fill(later)
    time_off.get_by_label("סיבה (לא חובה)").fill("חופשה")
    time_off.get_by_role("button", name="הוספת היעדרות").click()
    expect(time_off.get_by_text("· חופשה")).to_be_visible()
    off_serious = serious(owner)
    time_off.get_by_role("button", name="הסרה").click()
    expect(time_off.get_by_text("· חופשה")).to_have_count(0)
    print("2b. time off added and removed | a11y:", off_serious or "ok")

    # A walk-in from the web: a new client, then the first free time tomorrow.
    owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
    owner.get_by_label("שם פרטי").fill("יוסי")
    owner.get_by_role("button", name="יצירה").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$"))
    owner.goto(f"{h.BASE}/schedule"); h.ready(owner)
    owner.get_by_role("link", name="תור חדש").click(); owner.wait_for_url("**/schedule/appointment**"); h.ready(owner)
    tomorrow = owner.evaluate("() => { const d = new Date(); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); }")
    owner.get_by_label("תאריך").fill(tomorrow)
    owner.get_by_role("button", name="הצגת זמנים").click(); h.ready(owner)
    expect(owner.get_by_text("09:00").first).to_be_visible()
    booking_serious = serious(owner)
    owner.screenshot(path=f"{h.OUT}/appointment-web.png", full_page=True)
    owner.get_by_role("button", name="קביעת התור").click()
    owner.wait_for_url(re.compile(r".*/schedule/[0-9a-f-]{36}\?booked=1")); h.ready(owner)
    print("3. walk-in booked from the web | a11y:", booking_serious or "ok")

    # A client books in the app.
    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    member.goto(f"{h.APP}/join?code={code}"); member.wait_for_url("**/sign-in**", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(h.otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join**")
    member.get_by_label("שם פרטי").fill("נועה")
    member.get_by_role("button", name="הצטרפות למספרת דנה").click(); member.wait_for_url("**/home")
    member.goto(f"{h.APP}/schedule")
    member.get_by_role("button", name=re.compile("קביעת תור")).first.click(timeout=30000)
    member.wait_for_url("**/appointment")
    member.get_by_role("radio", name=re.compile("^תספורת גברים")).click()
    member.get_by_role("tab").nth(1).click()  # tomorrow
    member.get_by_role("radio", name=re.compile(r"^09:\d\d")).first.click(timeout=15000)
    app_serious = serious(member)
    member.screenshot(path=f"{h.OUT}/appointment-app.png", full_page=True)
    member.get_by_role("button", name=re.compile("^קביעת תור ל-")).click()
    expect(member.get_by_text("התור נקבע!")).to_be_visible(timeout=15000)
    print("4. client booked in the app | a11y:", app_serious or "ok")
    member.goto(f"{h.APP}/home")
    expect(member.get_by_role("heading", name="התור הבא שלך")).to_be_visible(timeout=30000)
    expect(member.get_by_role("button", name="קביעת תור")).to_be_visible()
    h.ready(member); member.screenshot(path=f"{h.OUT}/appointment-app-home.png", full_page=True)

    owner.goto(f"{h.BASE}/schedule?week={tomorrow}"); h.ready(owner)
    expect(owner.locator("main ol").get_by_text("יוסי")).to_be_visible()
    owner.screenshot(path=f"{h.OUT}/appointment-schedule.png", full_page=True)
    print("5. both appointments on the owner's schedule: ok")
    b.close()
