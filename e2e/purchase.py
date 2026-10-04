"""Online sales: the owner turns them on, a member buys a plan in the app (test payment) and
the owner sees it on the member's profile."""

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

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו מכירות")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard")
    owner.goto(f"{h.BASE}/settings"); h.ready(owner)
    owner.get_by_label("מתאמנים יכולים לרכוש מנויים באפליקציה").check()
    with owner.expect_response(lambda r: r.request.method == "POST" and "/settings" in r.url):
        owner.get_by_role("button", name="שמירה").first.click()
    print("1. online sales on: ok")

    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    member.on("dialog", lambda dialog: dialog.accept())  # the purchase confirmation
    member.goto(h.APP); member.wait_for_url("**/sign-in", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(h.otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join")
    member.get_by_label("קוד הצטרפות").fill(code)
    member.get_by_role("button", name="המשך").click()
    member.get_by_role("button", name="הצטרפות לסטודיו מכירות").click(); member.wait_for_url("**/home")
    member.get_by_role("tab", name="ההרשמות שלי").click()
    try:
        expect(member.get_by_text("עדיין אין לך מנוי בתוקף")).to_be_visible(timeout=30000)
    except AssertionError:
        member.screenshot(path=f"{h.OUT}/purchase-failed.png", full_page=True)
        raise
    buy = member.get_by_role("button", name=re.compile("^רכישה – כרטיסייה"))
    expect(buy).to_be_visible()
    serious = [v["id"] for v in Axe().run(member).response["violations"] if v["impact"] in ("serious", "critical")]
    buy.click()
    expect(member.get_by_text(re.compile("^בוצע!"))).to_be_visible(timeout=15000)
    member.screenshot(path=f"{h.OUT}/purchase.png", full_page=True)
    print("2. member bought a plan (test payment): ok | a11y:", serious or "ok")

    owner.goto(f"{h.BASE}/clients"); h.ready(owner)
    owner.locator("main table a, main ul a").filter(has_text=re.compile("member")).first.click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    plans = owner.get_by_role("region", name="מנויים וכרטיסיות")
    expect(plans.locator("li").filter(has_text="כרטיסייה 10 כניסות").first).to_be_visible()
    print("3. owner sees the plan on the member's profile: ok")
    b.close()
