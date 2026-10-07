"""The sign-up journey on a phone, in Hebrew: industry, business, base plan, one add-on per
screen with a live cart, summary, account, email confirmation, (simulated) payment, and the
dashboard with the welcome and the first-steps checklist. Then the English pages on a wide
screen in dark mode."""

import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: dict[str, list[str]] = {}


def check(page, name: str, shot: bool = True) -> None:
    h.ready(page)
    found = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    if found:
        issues[name] = found
    if shot:
        page.screenshot(path=f"{h.OUT}/start-{name}.png", full_page=True)


def cart_total(page) -> str:
    text = page.locator("div.fixed button[aria-controls=cart-sheet] bdi").inner_text()
    return re.sub(r"[\u200e\u200f\s]", "", text)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page()

    page.goto(h.BASE + "/start")
    check(page, "1-industry")
    page.get_by_role("button", name=re.compile("יופי וספא")).click()
    # the category's kinds of business, then the business itself
    expect(page.get_by_role("heading", level=1)).to_have_text("איזה סוג עסק בתחום יופי וספא?")
    check(page, "1b-kind")
    page.get_by_role("button", name=re.compile("^ברברשופ")).click()

    expect(page.get_by_role("heading", level=1)).to_have_text("ספרו לנו על הברברשופ")
    page.get_by_role("button", name="המשך").click()  # the name is required
    expect(page.get_by_role("heading", level=1)).to_have_text("ספרו לנו על הברברשופ")
    page.get_by_label("שם העסק").fill("המספרה של שירה")
    page.get_by_text("101–300").click()
    page.get_by_role("button", name="יותר סניפים").click()
    check(page, "2-business")
    page.get_by_role("button", name="המשך").click()

    # The size cards: the business's own size is chosen, the others are a tap away.
    expect(page.get_by_role("button", name=re.compile("101–300"))).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_role("button", name=re.compile("לקוחות פעילים"))).to_have_count(4)
    expect(page.get_by_text("סניף נוסף אחד", exact=False)).to_be_visible()
    assert cart_total(page) == "178₪", cart_total(page)
    check(page, "3-base")
    page.get_by_role("button", name="המשך").click()

    def choose(index: int) -> None:
        page.locator("main ul li button[aria-pressed]").nth(index).click()

    expect(page.get_by_role("heading", level=1)).to_have_text("לתת ללקוחות אפליקציה משלך?")
    expect(page.get_by_role("button", name="לבחור")).to_have_count(2)  # basic and pro
    check(page, "4-app")
    choose(0)  # basic app
    expect(page.get_by_role("heading", level=1)).to_have_text("רוצה עוזר שעונה תוך שניות?")
    assert cart_total(page) == "227₪", cart_total(page)
    check(page, "5-ai")
    choose(1)  # AI Pro
    expect(page.get_by_role("heading", level=1)).to_have_text("להפוך יותר פניות ללקוחות?")
    check(page, "6-crm")
    page.get_by_role("button", name=re.compile("^לא תודה")).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("להזכיר ללקוחות בוואטסאפ אוטומטית?")
    choose(0)  # WhatsApp basic
    # The extras: space and messages (basic is included), support, and setup (one-time).
    expect(page.get_by_role("heading", level=1)).to_have_text("כמה מקום והודעות העסק צריך?")
    expect(page.get_by_role("button", name=re.compile("לבחור|נבחר"))).to_have_count(3)
    check(page, "7-pack")
    choose(0)
    expect(page.get_by_role("heading", level=1)).to_have_text("כמה קרוב תרצה שנהיה?")
    choose(1)  # priority support
    expect(page.get_by_role("heading", level=1)).to_have_text("מי מקים את העסק במערכת?")
    check(page, "8-setup")
    choose(1)  # guided setup, one-time

    expect(page.get_by_role("heading", level=1)).to_have_text("החבילה שלך מוכנה")
    assert cart_total(page) == "414₪", cart_total(page)  # the one-time setup is not monthly
    page.get_by_role("button", name="להציג את החבילה").click()
    expect(page.locator("#cart-sheet li")).to_have_count(7)
    check(page, "9-summary")
    page.get_by_role("button", name="להסתיר את החבילה").click()
    page.get_by_role("button", name="להסיר מהחבילה: וואטסאפ").click()
    assert cart_total(page) == "385₪", cart_total(page)
    page.get_by_role("button", name="ליצור את החשבון שלי").click()
    expect(page.locator("#terms-error")).to_have_text("כדי להמשיך יש לאשר את התנאים.")
    page.get_by_role("checkbox").check()
    page.get_by_role("button", name="ליצור את החשבון שלי").click()

    page.wait_for_url("**/signup?next=**")
    email = f"journey{time.time_ns()}@example.com"
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email))
    page.wait_for_url("**/start/finish?p=**")

    expect(page.get_by_role("heading", level=1)).to_have_text("שלב אחרון: פרטי תשלום")
    expect(page.get_by_text(re.compile("המספרה של שירה. · ברברשופ"))).to_be_visible()
    check(page, "10-payment")
    page.get_by_label("שם בעל הכרטיס").fill("שירה לוי")
    page.get_by_role("button", name="להתחיל את תקופת הניסיון").click()

    page.wait_for_url("**/dashboard?welcome=1")
    expect(page.get_by_role("heading", name=re.compile("ברוכים הבאים ל-MyBiz, .המספרה של שירה.! 🎉"))).to_be_visible()
    expect(page.get_by_role("progressbar")).to_be_visible()
    check(page, "11-dashboard")

    with psycopg.connect(h.DATABASE_URL) as conn:
        tenant = conn.execute(
            """SELECT t.vertical, t.currency, t.welcome_sent_at IS NOT NULL, b.card_last4,
                      (SELECT array_agg(module_key || ':' || quantity ORDER BY module_key)
                       FROM app.tenant_modules m WHERE m.tenant_id = t.id)
               FROM app.tenants t JOIN app.billing_accounts b ON b.tenant_id = t.id
               WHERE t.name = 'המספרה של שירה' ORDER BY t.created_at DESC LIMIT 1"""
        ).fetchone()
    assert tenant == ("barbershop", "ILS", True, "4242", ["ai_pro:1", "client_app:1", "extra_location:1", "setup_guided:1", "support_priority:1"]), tenant
    print("phone journey (he): wizard, cart, account, payment, business created: ok")

    page.goto(h.BASE + "/getting-started")
    expect(page.get_by_role("heading", level=1)).to_have_text("היום הראשון שלך עם MyBiz")
    check(page, "guide")

    # English, dark, wide screen: the plan preselected from the pricing page.
    wide = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 1280, "height": 900}).new_page()
    wide.goto(h.BASE); h.ready(wide)
    wide.locator("header select").first.select_option("en"); wide.wait_for_timeout(1500)
    wide.goto(h.BASE + "/pricing?currency=USD"); h.ready(wide)
    wide.locator("a[href*=\"preset=growing\"]").click()
    wide.wait_for_url("**/start?preset=growing&currency=USD")
    check(wide, "en-industry")
    wide.get_by_role("button", name=re.compile("Fitness & Training")).click()
    wide.get_by_role("button", name=re.compile("^Another Fitness & Training business")).click()
    wide.get_by_label("Business name").fill("Flow Studio")
    wide.get_by_role("button", name="Continue").click()
    cart = wide.get_by_role("complementary", name="Your plan")
    expect(cart.get_by_text("Client app")).to_be_visible()
    expect(cart.get_by_text("AI Basic")).to_be_visible()
    check(wide, "en-base")
    wide.get_by_role("button", name="Continue").click()
    check(wide, "en-app")
    print("wide journey (en, dark) with a preset: ok")

    print("a11y:", issues or "ok")
    assert not issues
