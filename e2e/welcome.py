"""A new account lands on the welcome page (decision T79) and explores a sample business full
of fictitious data before setting up its own. Hebrew, desktop, light and dark.

    uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/welcome.py
"""

import pathlib
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = f"welcome{time.time_ns()}@example.com"
axe = Axe()
issues: list[str] = []


def check(page, label: str) -> None:
    found = [v for v in axe.run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    issues.extend(f"{label}: {v['id']} {[n['target'] for n in v['nodes']]}" for v in found)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email)); page.wait_for_url("**/welcome"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("ברוכים הבאים ל-MyBiz")
    check(page, "welcome")
    page.emulate_media(color_scheme="dark"); check(page, "welcome (dark)")
    page.screenshot(path=f"{h.OUT}/welcome-dark.png", full_page=True)
    page.emulate_media(color_scheme="light")
    page.screenshot(path=f"{h.OUT}/welcome.png", full_page=True)
    print("1. new account lands on the welcome page: ok")

    page.get_by_label("תחום").select_option("barbershop")
    page.get_by_role("button", name="ליצירת עסק לדוגמה").click()
    page.wait_for_url("**/dashboard?sample=1", timeout=60000); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_contain_text("ברברשופ לדוגמה")
    expect(page.get_by_role("region", name="דורש את תשומת לבך")).to_be_visible()
    print("2. sample business created and opened, with data: ok")

    page.goto(f"{h.BASE}/welcome"); page.wait_for_url("**/dashboard**")
    print("3. the welcome page steps aside once there is a business: ok")

    print("a11y:", issues or "ok")
    assert not issues
