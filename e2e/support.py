"""Support access: the owner allows support, a platform admin opens the business read-only
(with a banner), and the owner sees what was opened. Pass a platform admin's email."""

import pathlib
import re
import sys
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

ADMIN = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"owner{time.time_ns()}@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); h.to_onboarding(owner)
    owner.get_by_label("שם העסק").fill("סטודיו תמיכה")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard")
    owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
    owner.get_by_label("שם פרטי").fill("דנה")
    owner.get_by_role("button", name="יצירה").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$"))
    owner.goto(f"{h.BASE}/settings"); h.ready(owner)
    owner.get_by_role("button", name="אישור גישת תמיכה ל-24 שעות").click()
    expect(owner.get_by_text(re.compile("^התמיכה יכולה לצפות עד"))).to_be_visible()
    print("1. owner allowed support: ok")

    admin = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    h.login(admin, ADMIN)
    admin.goto(f"{h.BASE}/platform/businesses"); h.ready(admin)
    admin.get_by_role("link", name="סטודיו תמיכה").first.click(); h.ready(admin)
    admin.get_by_role("button", name="כניסה כתמיכה (צפייה בלבד)").click()
    admin.wait_for_url("**/dashboard"); h.ready(admin)
    expect(admin.get_by_role("status").filter(has_text="מצב תמיכה: צפייה בלבד")).to_be_visible()
    expect(admin.get_by_role("heading", level=1)).to_contain_text("סטודיו תמיכה")
    nav = admin.get_by_role("navigation").first
    expect(nav.get_by_role("link", name="הגדרות")).to_have_count(0)
    admin.goto(f"{h.BASE}/clients"); h.ready(admin)
    expect(admin.get_by_role("link", name="דנה")).to_be_visible()
    expect(admin.get_by_role("link", name="ייבוא מקובץ")).to_have_count(0)  # no write actions
    serious = [v["id"] for v in Axe().run(admin).response["violations"] if v["impact"] in ("serious", "critical")]
    admin.screenshot(path=f"{h.OUT}/support-mode.png", full_page=True)
    admin.get_by_role("button", name="יציאה ממצב תמיכה").click(); admin.wait_for_url("**/platform")
    h.ready(admin)
    print("2. admin opened the business read-only and left: ok | a11y:", serious or "ok")

    owner.goto(f"{h.BASE}/settings"); h.ready(owner)
    owner.get_by_text(re.compile("דפים שהתמיכה פתחה")).click()
    expect(owner.get_by_text("/clients", exact=False).first).to_be_visible()
    owner.get_by_role("button", name="סיום גישת התמיכה עכשיו").click()
    expect(owner.get_by_role("button", name="אישור גישת תמיכה ל-24 שעות")).to_be_visible()
    print("3. owner saw the visits and ended access: ok")
    b.close()
