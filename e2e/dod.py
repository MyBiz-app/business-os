"""Spec v1 §23 Definition of Done, end to end, plus axe accessibility checks."""
import datetime as dt
import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h
from helpers import APP, login, otp

ADMIN = sys.argv[1]  # a platform admin's email (see README)
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email, coach_email, member_email = (f"{n}{stamp}@example.com" for n in ("owner", "coach", "member"))
tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
axe = Axe()
a11y: list[str] = []

def check_a11y(page, label):
    h.ready(page)  # client-side navigations can still be fading in
    results = axe.run(page)
    serious = [v for v in results.response["violations"] if v["impact"] in ("serious", "critical")]
    for v in serious:
        a11y.append(f"{label}: {v['id']} ({v['impact']}) x{len(v['nodes'])}: {v['nodes'][0]['target']}")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    # Register → verify → create business (questionnaire → plan).
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill("Str0ng!Passw0rd")
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו DoD")
    owner.get_by_label("אני רוצה עוזר AI שיכול גם לבצע פעולות (רישומים)").check()
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)
    print("1. registered, verified, created business: ok")

    # Logo and colors.
    owner.goto(f"{h.BASE}/settings"); h.ready(owner)
    owner.get_by_label("שימוש בצבע ברירת המחדל").uncheck()
    owner.get_by_label("צבע המותג").fill("#0f766e")
    with owner.expect_response(lambda r: r.request.method == "POST" and "/settings" in r.url):
        owner.get_by_role("button", name="שמירה").nth(1).click()
    owner.get_by_label("לוגו", exact=True).set_input_files("e2e/logo.png")
    owner.get_by_role("button", name="העלאת לוגו").click()
    expect(owner.get_by_role("img", name="תצוגה מקדימה")).to_be_visible()
    owner.goto(f"{h.BASE}/dashboard"); h.ready(owner)
    expect(owner.get_by_role("heading", level=1)).to_contain_text("סטודיו DoD")
    print("2. logo + colors, dashboard: ok")

    # Employee with permissions (invite as front desk).
    owner.goto(f"{h.BASE}/team"); h.ready(owner)
    owner.get_by_label("אימייל", exact=True).fill(coach_email)
    owner.get_by_label("תפקיד", exact=True).select_option("front_desk")
    owner.get_by_role("button", name="יצירת קישור הזמנה").click()
    link = owner.get_by_role("textbox", name="העתקת הקישור").input_value()
    coach = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    coach.goto(link); h.ready(coach)
    coach.get_by_role("link", name="יצירת חשבון").click(); coach.wait_for_url("**/signup?next=**"); h.ready(coach)
    coach.get_by_label("אימייל").fill(coach_email)
    coach.get_by_label("סיסמה").fill("Str0ng!Passw0rd")
    coach.get_by_role("button", name="יצירת חשבון").click(); coach.wait_for_url("**/check-email**")
    coach.goto(h.confirm_link(coach_email)); coach.wait_for_url("**/invite/**"); h.ready(coach)
    coach.get_by_role("button", name=re.compile("הצטרפות ל")).click(); coach.wait_for_url("**/dashboard")
    expect(coach.get_by_role("navigation", name="ניווט ראשי").get_by_role("link", name="צוות")).to_have_count(0)
    print("3. employee joined with front-desk permissions: ok")

    # Service/class, session tomorrow, member with a plan.
    owner.goto(f"{h.BASE}/services/new"); h.ready(owner)
    owner.get_by_label("שם").fill("פילאטיס")
    owner.get_by_label("משך (בדקות)").fill("55")
    owner.get_by_label("משתתפים בכל מפגש").fill("8")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/services")
    owner.goto(f"{h.BASE}/schedule/new"); h.ready(owner)
    owner.get_by_label("תאריך", exact=True).fill(tomorrow)
    owner.get_by_label("שעת התחלה").fill("18:00")
    owner.get_by_role("button", name="יצירה").click(); owner.wait_for_url("**/schedule?week=*")
    for first, email in (("דנה", None), ("נועה", member_email)):
        owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
        owner.get_by_label("שם פרטי").fill(first)
        owner.get_by_label("שם משפחה").fill("כהן")
        if email:
            owner.get_by_label("אימייל").fill(email)
        owner.get_by_role("button", name="יצירה").click()
        owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    plans = owner.get_by_role("region", name="מנויים וכרטיסיות")
    plans.get_by_role("button", name="מכירה").click()
    expect(plans.get_by_text("המסלול נמכר.")).to_be_visible()
    print("4. class, session, member with a membership: ok")

    # Member: branded mobile app (Expo web) → join → book.
    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    member.goto(APP); member.wait_for_url("**/sign-in", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join")
    member.get_by_label("קוד הצטרפות").fill(code)
    member.get_by_role("button", name="המשך").click()
    member.get_by_role("button", name="הצטרפות לסטודיו DoD").click(); member.wait_for_url("**/home")
    hero = member.get_by_role("heading", name="סטודיו DoD").locator("..")
    expect(hero).to_have_css("background-color", "rgb(15, 118, 110)")
    expect(member.get_by_text("היי נועה")).to_be_visible()  # claimed the client record by email
    member.get_by_role("button", name="מילוי הצהרת בריאות").click(); member.wait_for_url("**/health")
    h.sign_health(member)
    expect(member.get_by_text("הצהרת בריאות בתוקף")).to_be_visible()
    member.goto(f"{APP}/schedule")
    member.get_by_role("tab", name=re.compile(str(int(tomorrow[-2:])))).first.click()
    member.get_by_role("button", name=re.compile("^הרשמה – פילאטיס")).click()
    expect(member.get_by_text("נרשמת")).to_be_visible()
    member.screenshot(path=f"{h.OUT}/dod-member.png")
    print("5. member sees branded app and books: ok")

    # Owner sees the booking.
    owner.goto(f"{h.BASE}/schedule?week={tomorrow}"); h.ready(owner)
    owner.locator("main ol li li a").first.click(); h.ready(owner)
    expect(owner.get_by_role("region", name="רשימת משתתפים").get_by_text("נועה כהן")).to_be_visible()
    print("6. owner sees the booking: ok")

    # AI: question, then an action that needs confirmation.
    owner.goto(f"{h.BASE}/assistant"); h.ready(owner)
    owner.get_by_role("button", name="התחלת שיחה").click(); owner.wait_for_url("**/assistant?c=*"); h.ready(owner)
    owner.get_by_role("button", name="איך היה החודש שעבר?").click()
    expect(owner.get_by_text("ב-30 הימים האחרונים")).to_be_visible(timeout=20000)
    owner.get_by_label("השאלה שלך").fill("תרשום את כהן לשיעור מחר")
    owner.get_by_role("button", name="שליחה").click()
    expect(owner.get_by_text("דורש את אישורך")).to_be_visible(timeout=20000)
    owner.get_by_role("button", name="אישור").click()
    expect(owner.get_by_role("status").filter(has_text="בוצע")).to_be_visible()
    owner.goto(f"{h.BASE}/schedule?week={tomorrow}"); h.ready(owner)
    owner.locator("main ol li li a").first.click(); h.ready(owner)
    expect(owner.get_by_role("region", name="רשימת משתתפים").get_by_text("דנה כהן")).to_be_visible()
    print("7. AI answered, proposed an action, confirmed, executed: ok")
    check_a11y(owner, "he-light session roster")
    owner.get_by_role("region", name="רשימת משתתפים").get_by_role("link", name="נועה כהן").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    check_a11y(owner, "he-light client profile")

    # Platform admin sees the new business and its usage.
    admin = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    login(admin, ADMIN)
    admin.goto(f"{h.BASE}/platform/businesses"); h.ready(admin)
    row = admin.get_by_role("row").filter(has_text=owner_email)
    expect(row).to_contain_text(owner_email)
    credits = row.locator("td").nth(6).inner_text()
    assert float(credits) > 0, credits
    print("8. platform admin sees the business and AI usage:", credits)

    # Accessibility (axe) in Hebrew/light and English/dark.
    pages = ["/dashboard", "/schedule", "/clients", "/plans", "/assistant", "/settings", "/settings/modules"]
    for path in pages:
        owner.goto(f"{h.BASE}{path}"); h.ready(owner); check_a11y(owner, f"he-light {path}")
    en = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 1280, "height": 900})
    en.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    en_page = en.new_page(); login(en_page, owner_email)
    for path in pages:
        en_page.goto(f"{h.BASE}{path}"); h.ready(en_page); check_a11y(en_page, f"en-dark {path}")
    check_a11y(member, "app he-light /schedule")
    for path in ("/home", "/bookings", "/profile"):
        member.goto(f"{APP}{path}"); member.wait_for_timeout(1500); check_a11y(member, f"app he-light {path}")
    print("9. accessibility:", "no serious issues" if not a11y else f"{len(a11y)} serious issues")
    for line in a11y:
        print("   ", line)
    b.close()
