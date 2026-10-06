"""Weekly series: create one without an end date, then stop it from a session."""

import datetime as dt
import re
import time

from playwright.sync_api import expect, sync_playwright

import helpers as h

email = f"owner{time.time_ns()}@example.com"
tomorrow = (h.local_today() + dt.timedelta(days=1)).isoformat()
next_week = (h.local_today() + dt.timedelta(days=7)).isoformat()

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
    page.get_by_label("סוג העסק").select_option("pilates")  # a class studio
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

    # Change the time of this and all later sessions in the series.
    session_url = page.url
    page.get_by_label("שעת התחלה").fill("20:15")
    page.get_by_label("להחיל על השיעור הזה ועל כל השיעורים הבאים בסדרה").check()
    page.get_by_role("button", name="שמירה").click()
    expect(page.locator("main p").filter(has_text="20:15").first).to_be_visible()
    page.goto(f"{h.BASE}/schedule?week={next_week}"); h.ready(page)
    expect(page.locator("main ol").get_by_text("20:15").first).to_be_visible()
    print("series time changed from this session on: ok")
    page.goto(session_url); h.ready(page)

    page.get_by_role("button", name="הפסקת החזרה אחרי השיעור הזה").click()
    page.wait_for_url("**?ended=*")
    expect(page.get_by_role("status")).to_contain_text("החזרה הופסקה")
    expect(page.get_by_role("button", name="הפסקת החזרה אחרי השיעור הזה")).to_have_count(0)
    page.screenshot(path=f"{h.OUT}/s1-ended.png", full_page=True)
    print("stop repeating: ok")

    # Copy a week's one-off class to the following week.
    page.goto(f"{h.BASE}/schedule/new?date={tomorrow}"); h.ready(page)
    page.get_by_label("שעת התחלה").fill("07:45")
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/schedule?week=*"); h.ready(page)
    page.get_by_role("button", name="העתקת השבוע לשבוע הבא").click()
    expect(page.get_by_role("status").filter(has_text="הועתק שיעור אחד")).to_be_visible()
    page.get_by_role("status").get_by_role("link", name="השבוע הבא").click(); h.ready(page)
    expect(page.locator("main ol").get_by_text("07:45")).to_be_visible()
    print("copy week: ok")

    # An instructor sees their own classes for today first on the dashboard.
    today = h.local_today().isoformat()
    page.goto(f"{h.BASE}/schedule/new?date={today}"); h.ready(page)
    page.get_by_label("שעת התחלה").fill("23:30")
    page.get_by_label("מדריך/ה").select_option(label=email)
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/schedule?week=*")
    page.goto(f"{h.BASE}/dashboard"); h.ready(page)
    mine = page.get_by_role("region", name=re.compile("שלך היום"))  # the industry's word for a session
    expect(mine.get_by_text("23:30")).to_be_visible()
    print("instructor's classes today on the dashboard: ok")

    # Close a day (a holiday): its classes are cancelled and the schedule shows it closed.
    page.goto(f"{h.BASE}/schedule/closed"); h.ready(page)
    page.get_by_label("תאריך").fill(tomorrow)
    page.get_by_label("סיבה (לא חובה)").fill("חג")
    page.get_by_role("button", name="סגירת יום").click()
    expect(page.get_by_role("status").filter(has_text="היום נסגר")).to_be_visible()
    page.screenshot(path=f"{h.OUT}/s1-closed-days.png", full_page=True)
    page.goto(f"{h.BASE}/schedule?week={tomorrow}"); h.ready(page)
    expect(page.locator("main").get_by_text("סגור · חג")).to_be_visible()
    print("close a day: ok")
    page.goto(f"{h.BASE}/schedule/closed"); h.ready(page)
    page.get_by_role("button", name="פתיחה מחדש").click()
    expect(page.get_by_text("אין ימים סגורים קרובים.")).to_be_visible()
    print("reopen a day: ok")
    b.close()
