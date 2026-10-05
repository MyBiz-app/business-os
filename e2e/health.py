"""Health declaration: a member answers "yes", can't book until the studio approves, then books.
Also checks the health screen and the client profile for accessibility."""

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
tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
axe = Axe()
problems: list[str] = []


def check_a11y(page, label):
    results = axe.run(page)
    for v in results.response["violations"]:
        if v["impact"] in ("serious", "critical"):
            problems.append(f"{label}: {v['id']} x{len(v['nodes'])}: {v['nodes'][0]['target']}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו בריאות")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard")

    owner.goto(f"{h.BASE}/settings"); h.ready(owner)
    expect(owner.get_by_label("לקוחות צריכים הצהרת בריאות כדי להירשם באפליקציה")).to_be_checked()

    owner.goto(f"{h.BASE}/services/new"); h.ready(owner)
    owner.get_by_label("שם").fill("פילאטיס")
    owner.get_by_label("משך (בדקות)").fill("55")
    owner.get_by_label("משתתפים בכל מפגש").fill("8")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/services")
    owner.goto(f"{h.BASE}/schedule/new"); h.ready(owner)
    owner.get_by_label("תאריך", exact=True).fill(tomorrow)
    owner.get_by_label("שעת התחלה").fill("18:00")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/schedule?week=*")
    owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
    owner.get_by_label("שם פרטי").fill("נועה")
    owner.get_by_label("שם משפחה").fill("כהן")
    owner.get_by_label("אימייל").fill(member_email)
    owner.get_by_role("button", name="יצירה").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    client_url = owner.url
    expect(owner.get_by_text("אין הצהרת בריאות")).to_be_visible()
    plans = owner.get_by_role("region", name="מנויים וכרטיסיות")
    plans.get_by_role("button", name="מכירה").click()
    expect(plans.get_by_text("המסלול נמכר.")).to_be_visible()
    print("1. studio requires declarations; member without one: ok")

    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    member.goto(h.APP); member.wait_for_url("**/sign-in", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(h.otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join")
    member.get_by_label("קוד הצטרפות").fill(code)
    member.get_by_role("button", name="המשך").click()
    member.get_by_label("שם פרטי").fill("נועה")
    member.get_by_role("button", name="הצטרפות לסטודיו בריאות").click(); member.wait_for_url("**/home")
    expect(member.get_by_text("לפני הביקור הראשון, יש למלא הצהרת בריאות קצרה.")).to_be_visible()

    member.goto(f"{h.APP}/schedule")
    member.get_by_role("tab", name=re.compile(str(int(tomorrow[-2:])))).first.click()
    member.get_by_role("button", name=re.compile("^הרשמה – פילאטיס")).click()
    expect(member.get_by_text("יש למלא הצהרת בריאות לפני ההרשמה.")).to_be_visible()
    print("2. booking blocked without a declaration: ok")

    member.goto(f"{h.APP}/health")
    member.get_by_role("radiogroup").first.wait_for(timeout=30000)
    member.get_by_role("button", name="חתימה על ההצהרה").click()
    expect(member.get_by_role("alert")).to_have_text("יש לענות על כל השאלות.")
    check_a11y(member, "health form")
    h.sign_health(member, yes=(5,))
    expect(member.get_by_text("הצהרת בריאות ממתינה לאישור")).to_be_visible()
    member.screenshot(path=f"{h.OUT}/health-pending.png", full_page=True)
    member.goto(f"{h.APP}/schedule")
    member.get_by_role("tab", name=re.compile(str(int(tomorrow[-2:])))).first.click()
    member.get_by_role("button", name=re.compile("^הרשמה – פילאטיס")).click()
    expect(member.get_by_text("העסק צריך לאשר את הצהרת הבריאות שלך")).to_be_visible()
    print("3. a \"yes\" waits for approval: ok")

    owner.goto(client_url); h.ready(owner)
    section = owner.get_by_role("region", name="הצהרת בריאות")
    expect(section.get_by_text("הצהרת בריאות ממתינה לאישור")).to_be_visible()
    expect(section.get_by_text("ענה/תה \"כן\" על:")).to_be_visible()
    check_a11y(owner, "client profile with pending declaration")
    section.get_by_label("הערה (לא חובה)").fill("אישור רופא התקבל")
    section.get_by_role("button", name="אישור").click()
    expect(section.get_by_text("הצהרת בריאות בתוקף")).to_be_visible()
    expect(section.get_by_text("הערת העסק: אישור רופא התקבל")).to_be_visible()
    owner.screenshot(path=f"{h.OUT}/health-approved.png", full_page=True)
    print("4. studio approves: ok")

    member.goto(f"{h.APP}/schedule")
    member.get_by_role("tab", name=re.compile(str(int(tomorrow[-2:])))).first.click()
    member.get_by_role("button", name=re.compile("^הרשמה – פילאטיס")).click()
    expect(member.get_by_text("נרשמת")).to_be_visible()
    print("5. member books after approval: ok")

    with psycopg.connect(h.DATABASE_URL) as conn:
        conn.execute("""
            UPDATE app.health_declarations d SET valid_until = current_date + 10
            FROM app.clients c WHERE c.id = d.client_id AND c.email = %s
        """, (member_email,))
    member.goto(f"{h.APP}/home")
    expect(member.get_by_text("הצהרת הבריאות שלך בתוקף עד")).to_be_visible(timeout=30000)
    member.get_by_role("button", name="חתימה על הצהרה חדשה").click(); member.wait_for_url("**/health")
    expect(member.get_by_text("התוקף מסתיים בקרוב")).to_be_visible()
    member.screenshot(path=f"{h.OUT}/health-expiring.png", full_page=True)
    print("6. expiring declaration: reminder on home, renew from there: ok")
    b.close()

print("accessibility:", "ok" if not problems else "\n  " + "\n  ".join(problems))
