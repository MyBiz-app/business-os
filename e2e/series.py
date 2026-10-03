"""Weekly series: create one without an end date, then stop it from a session."""

import re
import time

from playwright.sync_api import expect, sync_playwright

import helpers as h

email = f"owner{time.time_ns()}@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup")
    h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email))
    page.wait_for_url("**/onboarding")
    h.ready(page)
    page.get_by_label("שם העסק").fill("סטודיו סדרות")
    page.get_by_role("button", name="המשך").click()
    page.get_by_role("button", name="יצירת העסק").click()
    page.wait_for_url("**/dashboard")
    page.goto(f"{h.BASE}/services/new")
    h.ready(page)
    page.get_by_label("שם").fill("יוגה")
    page.get_by_label("משך (בדקות)").fill("60")
    page.get_by_label("משתתפים בכל מפגש").fill("10")
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/services")

    page.goto(f"{h.BASE}/schedule/new")
    h.ready(page)
    page.get_by_label("שעת התחלה").fill("19:00")
    page.get_by_label("חזרה שבועית").check()
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/schedule?week=*")
    h.ready(page)
    page.locator("main ol li li a").first.click()
    page.wait_for_url(re.compile(r".*/schedule/[0-9a-f-]{36}$"))
    h.ready(page)
    expect(page.get_by_text("הסדרה ממשיכה")).to_be_visible()
    print("open-ended series: ok")

    page.get_by_role("button", name="הפסקת החזרה אחרי השיעור הזה").click()
    page.wait_for_url("**?ended=*")
    expect(page.get_by_role("status")).to_contain_text("החזרה הופסקה")
    expect(page.get_by_role("button", name="הפסקת החזרה אחרי השיעור הזה")).to_have_count(0)
    page.screenshot(path=f"{h.OUT}/s1-ended.png", full_page=True)
    print("stop repeating: ok")
    b.close()
