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
    owner.get_by_label("לקוחות יכולים לרכוש מנויים באפליקציה").check()
    with owner.expect_response(lambda r: r.request.method == "POST" and "/settings" in r.url):
        owner.get_by_role("button", name="שמירה").first.click()
    print("1. online sales on: ok")

    # A promo code: 10% off every plan.
    owner.goto(f"{h.BASE}/plans"); h.ready(owner)
    promo = owner.get_by_role("region", name="קודי הנחה")
    promo.get_by_label("קוד").fill("welcome10")
    promo.get_by_label("אחוז הנחה").fill("10")
    promo.get_by_role("button", name="יצירת קוד").click()
    expect(promo.get_by_text("WELCOME10")).to_be_visible()
    print("1b. promo code created: ok")

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
    member.get_by_role("button", name="הצטרפות לסטודיו מכירות").click(); member.wait_for_url("**/home")
    member.get_by_role("tab", name="ההרשמות שלי").click()
    try:
        expect(member.get_by_text("עדיין אין לך מנוי בתוקף")).to_be_visible(timeout=30000)
    except AssertionError:
        member.screenshot(path=f"{h.OUT}/purchase-failed.png", full_page=True)
        raise
    buy = member.get_by_role("button", name=re.compile("^רכישה – כרטיסייה"))
    expect(buy).to_be_visible()
    h.app_ready(member)
    serious = [v["id"] for v in Axe().run(member).response["violations"] if v["impact"] in ("serious", "critical")]
    buy.click()
    # The (simulated) payment page: a test card, the total, and the pay button.
    member.wait_for_url("**/pay/**")
    expect(member.get_by_text(re.compile("^מצב בדיקה"))).to_be_visible(timeout=15000)
    member.get_by_label("קוד הנחה").fill("welcome10")
    member.get_by_role("button", name="החלה").click()
    expect(member.get_by_text("הקוד WELCOME10 הוחל")).to_be_visible(timeout=15000)
    h.app_ready(member)
    pay_serious = [v["id"] for v in Axe().run(member).response["violations"] if v["impact"] in ("serious", "critical")]
    member.screenshot(path=f"{h.OUT}/payment.png", full_page=True)
    member.get_by_role("button", name=re.compile("^תשלום ")).click()
    expect(member.get_by_text("התשלום התקבל!")).to_be_visible(timeout=15000)
    expect(member.get_by_text(re.compile(r"^קבלה מס׳ \d+"))).to_be_visible()
    member.screenshot(path=f"{h.OUT}/purchase.png", full_page=True)
    member.get_by_role("button", name="צפייה בקבלה").click()
    member.wait_for_url("**/receipt/**")
    expect(member.get_by_text(re.compile("^מסמך לדוגמה"))).to_be_visible(timeout=15000)
    member.screenshot(path=f"{h.OUT}/receipt-app.png", full_page=True)
    print("2. member paid on the test payment page and sees the receipt: ok | a11y:", (serious + pay_serious) or "ok")
    member.goto(f"{h.APP}/bookings")

    member.get_by_role("tab", name="פרופיל").click()
    member.get_by_label("שם פרטי").fill("נועה")
    member.get_by_label("טלפון").fill("050-7654321")
    member.get_by_role("button", name="שמירת הפרטים").click()
    expect(member.get_by_text("נשמר.")).to_be_visible(timeout=15000)
    print("2b. member edited their details: ok")

    owner.goto(f"{h.BASE}/clients"); h.ready(owner)
    owner.locator("main table a, main ul a").filter(has_text="נועה").first.click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    plans = owner.get_by_role("region", name="מנויים וכרטיסיות")
    expect(plans.locator("li").filter(has_text="כרטיסייה 10 כניסות").first).to_be_visible()
    plans.get_by_role("link", name=re.compile(r"^קבלה \d+")).first.click()
    owner.wait_for_url("**/receipts/**"); h.ready(owner)
    expect(owner.get_by_role("heading", level=1)).to_contain_text("קבלה מס׳")
    owner.screenshot(path=f"{h.OUT}/receipt-web.png", full_page=True)
    owner.go_back(); h.ready(owner)
    expect(owner.get_by_label("טלפון")).to_have_value("050-7654321")
    print("3. owner sees the plan and the new phone on the member's profile: ok")
    b.close()
