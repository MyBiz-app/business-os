"""The business app (Expo web), on a phone. A staff member signs in with an email code and runs
the day: today with what needs attention and the week's days, a session's roster (check-in,
booking someone in, a visit note), clients (filters, a new client, selling a plan, a note, a
message), leads (moving a stage, logging a call, turning one into a client, a new lead), the
messages sent, the numbers (a period, the trend, breakdowns, clients to reach out to) and their
own settings. Then the main screens again in English with dark mode. Accessibility (axe, serious
and critical) is checked on every screen.

Usage: python e2e/business_app.py <owner email of a business with data (app.seed)>"""

import pathlib
import re
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

APP = "http://localhost:8082"
OWNER = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
a11y: list[str] = []
errors: list[str] = []


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']}: {v['nodes'][0]['target']}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        a11y.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/bizapp-{label}.png", full_page=True)


def sign_in(page, email_label: str, send: str, code_label: str, enter: str) -> None:
    page.goto(APP)
    page.get_by_label(email_label).wait_for(timeout=60000)
    page.get_by_label(email_label).fill(OWNER)
    page.get_by_role("button", name=send).click()
    page.get_by_label(code_label).wait_for(timeout=30000)
    page.wait_for_timeout(2000)  # let the new code's email arrive (older ones are still there)
    page.get_by_label(code_label).fill(h.otp(OWNER))
    page.get_by_role("button", name=enter).click()


def tab(page, name: str) -> None:
    """Opens a tab, first going back from pushed screens (they cover the tab bar)."""
    target = page.get_by_role("tab", name=name).last
    for _ in range(4):
        if target.is_visible():
            break
        page.go_back()
        page.wait_for_timeout(800)
    target.click()


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, is_mobile=True).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(page, "אימייל", "שליחת קוד", "קוד בן 6 ספרות", "כניסה")
    page.get_by_role("heading", name="סטודיו פלואו (דמו)").wait_for(timeout=60000)

    # Today: what needs attention opens up, and another day of the week shows its sessions.
    expect(page.get_by_text("דורש את תשומת לבך")).to_be_visible(timeout=30000)
    page.get_by_role("button", name="מנויים שמסתיימים בלי חידוש").click()
    check(page, "today")
    days = page.get_by_role("tablist", name="ימי השבוע").get_by_role("tab")
    expect(days).to_have_count(7)
    days.nth(1).click()
    expect(days.nth(1)).to_have_attribute("aria-selected", "true")
    days.nth(0).click()
    print("1. signed in; today, its attention lists and the week: ok")

    # A session: check someone in, book someone in, write a visit note.
    page.get_by_text("07:00").first.click()
    page.get_by_role("heading", name="מי מגיע").wait_for(timeout=30000)
    check(page, "session")
    check_in = page.get_by_role("button", name="סימון הגעה:").first
    if check_in.count():
        check_in.click()
        expect(page.get_by_role("button", name="ביטול הגעה:").first).to_be_visible(timeout=20000)
        print("2a. checked a client in: ok")
    page.get_by_role("button", name="רישום לשיעור").click()
    page.get_by_label("חיפוש לקוח לרישום").fill("ש")
    page.get_by_role("button", name="חיפוש", exact=True).click()
    page.get_by_role("button", name="רישום:").first.click()
    expect(page.get_by_text("נרשם/ה.").or_(page.get_by_text("ברשימת ההמתנה"))).to_be_visible(timeout=20000)
    page.get_by_role("button", name="הערה על הביקור של").first.click()
    page.get_by_role("textbox", name="הערה על הביקור של").fill("עבד/ה מצוין על הטכניקה, להעלות משקל בשבוע הבא")
    page.get_by_role("button", name="הוספת רשומה").click()
    expect(page.get_by_text("ההערה נשמרה בכרטיס")).to_be_visible(timeout=20000)
    print("2b. booked someone in and wrote a visit note: ok")

    # A court by the hour (when the business rents any): reserve it, then take the payment.
    tab(page, "היום")
    reserve = page.get_by_role("button", name="הזמנת מגרש")
    if reserve.count():
        reserve.first.click()
        page.get_by_role("heading", name="הזמנה חדשה").wait_for(timeout=30000)
        page.get_by_role("tablist", name="יום").get_by_role("tab").nth(2).click()
        page.get_by_role("tablist", name=re.compile("מגרש")).first.get_by_role("tab").first.click()
        page.get_by_label("חיפוש לקוח לרישום").fill("א")
        page.get_by_role("button", name="חיפוש", exact=True).click()
        page.get_by_role("button", name="הזמנה עבור").first.click()
        page.get_by_role("heading", name="מי מגיע").wait_for(timeout=30000)
        expect(page.get_by_text("עוד לא שולם")).to_be_visible()
        page.get_by_role("button", name="רישום התשלום").click()
        expect(page.get_by_text("שולם", exact=True)).to_be_visible(timeout=20000)
        check(page, "reservation")
        print("2c. reserved a court for a client and took the payment: ok")
        tab(page, "היום")

    # Clients: a filter, a new client, then selling a plan and a note on the card.
    tab(page, "מתאמנים")
    page.get_by_role("heading", name="מתאמנים").wait_for(timeout=30000)
    page.get_by_role("tab", name="עם מנוי בתוקף").click()
    page.wait_for_timeout(1500)
    check(page, "clients")
    page.get_by_role("button", name="הוספת מתאמן/ת").click()
    page.get_by_role("heading", name="מתאמן/ת חדש/ה").wait_for(timeout=30000)
    page.get_by_label("שם פרטי").fill("טליה")
    page.get_by_label("שם משפחה").fill("בדיקה")
    page.get_by_label("טלפון").fill("050-555-1234")
    page.get_by_role("tab", name="אינסטגרם").click()
    check(page, "client-new")
    page.get_by_role("button", name="יצירה").click()
    expect(page.get_by_text("נשמר. זה הכרטיס החדש.")).to_be_visible(timeout=30000)
    page.get_by_role("heading", name="טליה בדיקה").wait_for()
    page.get_by_role("button", name="מכירת מסלול").click()
    page.get_by_role("tab", name="מזומן").click()
    page.get_by_role("button", name="מכירה ·").click()
    expect(page.get_by_text("נמכר:")).to_be_visible(timeout=30000)
    expect(page.get_by_text("פעיל", exact=True).first).to_be_visible()
    page.get_by_role("button", name="הוספת רשומה").first.click()
    page.get_by_label("מה נעשה / מה חשוב לזכור?").fill("הגיעה דרך אינסטגרם, מעדיפה שיעורי בוקר")
    page.get_by_role("button", name="הוספת רשומה").last.click()
    expect(page.get_by_text("ההערה נשמרה.")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="הודעה", exact=True).click()
    page.get_by_label("אל טליה בדיקה").fill("היי טליה, ברוכה הבאה! נתראה בשיעור הראשון 🙂")
    page.get_by_role("button", name="שליחה", exact=True).click()
    expect(page.get_by_text("ההודעה נשלחה (מדומה).")).to_be_visible(timeout=20000)
    check(page, "client")
    print("3. a new client, a plan sold, a note and a message: ok")

    # Leads: move one along, log a call, make them a client; then a new lead.
    tab(page, "לידים")
    page.get_by_role("heading", name="לידים").wait_for(timeout=30000)
    check(page, "leads")
    page.locator("[role=button]:visible").filter(has_text="אינסטגרם").first.click()  # an open lead
    stages = page.get_by_role("tablist", name="העברה לשלב")
    stages.wait_for(timeout=30000)
    current = stages.locator("[aria-selected=true]").inner_text()
    target = "הצעה" if current == "ניסיון" else "ניסיון"
    stages.get_by_role("tab", name=target).click()
    expect(page.get_by_text(f"הועבר לשלב: {target}.")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="תיעוד שיחה או הערה").click()
    page.get_by_label("מה קרה?").fill("קבענו שיעור ניסיון ליום חמישי")
    page.get_by_role("button", name="הוספה", exact=True).click()
    expect(page.get_by_text("נוסף לפעילות.")).to_be_visible(timeout=20000)
    check(page, "lead")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="הפיכה ללקוח").click()
    expect(page.get_by_text("הפך/ה ללקוח/ה.")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="לכרטיס הלקוח").click()
    page.get_by_role("heading", name="ביקורים אחרונים").wait_for(timeout=30000)
    print("4. a lead moved, a call logged, turned into a client: ok")

    tab(page, "לידים")
    page.get_by_role("button", name="ליד חדש").click()
    page.get_by_label("שם פרטי").fill("אורי")
    page.get_by_label("טלפון").fill("052-555-9876")
    page.get_by_label("במה מתעניינים").fill("אימון אישי")
    page.get_by_role("button", name="שמירת הליד").click()
    expect(page.get_by_text("הליד נשמר.")).to_be_visible(timeout=30000)
    tab(page, "לידים")
    page.get_by_role("tab", name="הודעות").click()
    expect(page.get_by_text("היי טליה, ברוכה הבאה!").first).to_be_visible(timeout=30000)
    check(page, "messages")
    print("5. a new lead, and the messages sent: ok")

    tab(page, "מספרים")
    page.get_by_role("heading", name="מספרים מרכזיים").wait_for(timeout=30000)
    expect(page.get_by_text("הכנסות").first).to_be_visible()
    expect(page.get_by_role("heading", name="מגמה")).to_be_visible()
    expect(page.get_by_role("heading", name="לפי שירות")).to_be_visible()
    expect(page.get_by_role("heading", name=re.compile("שכדאי לפנות"))).to_be_visible()
    page.get_by_role("tab", name="90 ימים").click()
    expect(page.get_by_text("90 הימים האחרונים", exact=False)).to_be_visible(timeout=30000)
    check(page, "numbers")
    tab(page, "אני")
    page.get_by_role("heading", name="אני").wait_for(timeout=30000)
    check(page, "me")
    print("6. numbers and settings: ok")

    # English with dark mode: the main screens read and pass the same checks.
    dark = b.new_context(
        locale="en-US", viewport={"width": 390, "height": 844}, is_mobile=True, color_scheme="dark"
    ).new_page()
    dark.on("pageerror", lambda e: errors.append(str(e)))
    sign_in(dark, "Email", "Send code", "6-digit code", "Sign in")
    dark.get_by_role("tablist", name="Days of the week").wait_for(timeout=60000)
    check(dark, "today-en-dark")
    tab(dark, "Members")
    dark.get_by_role("heading", name="Members").wait_for(timeout=30000)
    check(dark, "clients-en-dark")
    dark.locator("[role=button]").filter(has_text=re.compile("days ago|Yesterday|Hasn")).first.click()
    dark.get_by_role("heading", name="Recent visits").wait_for(timeout=30000)
    check(dark, "client-en-dark")
    tab(dark, "Leads")
    dark.get_by_role("heading", name="Leads").wait_for(timeout=30000)
    check(dark, "leads-en-dark")
    print("7. English and dark mode: ok")

    print("page errors:", errors or "none")
    print("a11y:", a11y or "ok")
    assert not a11y and not errors
