"""Client notifications: the studio books a member, then cancels the class; the member sees
both in the app's Updates tab (with an unread badge that clears once opened)."""

import datetime as dt
import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email, member_email = (f"{n}{stamp}@example.com" for n in ("owner", "member"))
tomorrow = (h.local_today() + dt.timedelta(days=2)).isoformat()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); h.to_onboarding(owner)
    owner.get_by_label("שם העסק").fill("סטודיו עדכונים")
    owner.get_by_label("סוג העסק").select_option("pilates")  # a class studio
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard")
    owner.goto(f"{h.BASE}/services/new"); h.ready(owner)
    owner.get_by_label("שם").fill("יוגה")
    owner.get_by_label("משך (בדקות)").fill("60")
    owner.get_by_label("משתתפים בכל מפגש").fill("8")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/services")
    owner.goto(f"{h.BASE}/schedule/new"); h.ready(owner)
    owner.get_by_label("תאריך", exact=True).fill(tomorrow)
    owner.get_by_label("שעת התחלה").fill("18:00")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/schedule?week=*")
    h.ready(owner)
    owner.locator("main ol li li a").first.click()
    owner.wait_for_url(re.compile(r".*/schedule/[0-9a-f-]{36}$")); h.ready(owner)
    session_url = owner.url

    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    # The member opens the studio's join link before signing in: sign-in first, then the
    # join screen already knows the code.
    member.goto(f"{h.APP}/join?code={code}"); member.wait_for_url("**/sign-in**", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(h.otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join**")
    member.get_by_label("שם פרטי").fill("נועה")
    member.get_by_role("button", name="הצטרפות לסטודיו עדכונים").click(); member.wait_for_url("**/home")
    member.goto(f"{h.APP}/updates")
    expect(member.get_by_text("אין עדכונים עדיין")).to_be_visible(timeout=30000)
    print("1. member joined; empty updates: ok")

    # The studio books the member from the roster, then cancels the class.
    owner.goto(session_url); h.ready(owner)
    roster = owner.get_by_role("region", name="רשימת משתתפים")
    roster.get_by_label("חיפוש לקוח לרישום").fill(member_email.split("@")[0])
    roster.get_by_role("button", name="חיפוש").click(); h.ready(owner)
    owner.get_by_role("region", name="רשימת משתתפים").get_by_role("button", name=re.compile("^רישום")).first.click()
    h.ready(owner)
    owner.get_by_role("button", name="ביטול השיעור").click(); h.ready(owner)
    print("2. studio booked the member and cancelled the class: ok")

    member.goto(f"{h.APP}/home")
    tab = member.get_by_role("tab", name="עדכונים, 2 חדשים")
    expect(tab).to_be_visible(timeout=30000)
    tab.click()
    expect(member.get_by_text(re.compile("^יוגה ב.* בוטל\\.$"))).to_be_visible(timeout=15000)
    expect(member.get_by_text(re.compile("^העסק רשם אותך ליוגה ביום"))).to_be_visible()
    serious = [v["id"] for v in Axe().run(member).response["violations"] if v["impact"] in ("serious", "critical")]
    member.screenshot(path=f"{h.OUT}/updates.png", full_page=True)
    member.goto(f"{h.APP}/home")
    expect(member.get_by_role("tab", name="עדכונים", exact=True)).to_be_visible(timeout=30000)
    print("3. updates shown, badge cleared after reading: ok | a11y:", serious or "ok")

    # The studio closes a day; the member's schedule marks it closed, with the reason.
    closed_day = (h.local_today() + dt.timedelta(days=3)).isoformat()
    owner.goto(f"{h.BASE}/schedule/closed"); h.ready(owner)
    owner.get_by_label("תאריך").fill(closed_day)
    owner.get_by_label("סיבה (לא חובה)").fill("חג")
    owner.get_by_role("button", name="סגירת יום").click()
    expect(owner.get_by_role("status").filter(has_text="היום נסגר")).to_be_visible()
    member.goto(f"{h.APP}/schedule")
    closed_tab = member.get_by_role("tab", name=re.compile(", סגור$"))
    expect(closed_tab).to_be_visible(timeout=30000)
    closed_tab.click()
    expect(member.get_by_text("סגורים ביום הזה (חג).")).to_be_visible()
    member.screenshot(path=f"{h.OUT}/closed-day-app.png", full_page=True)
    print("4. closed day shown in the app: ok")
    b.close()
