"""Privacy requests: the owner downloads a client's data, then erases their personal details."""

import json
import pathlib
import re
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = f"owner{time.time_ns()}@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}, accept_downloads=True).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email)); page.wait_for_url("**/onboarding"); h.ready(page)
    page.get_by_label("שם העסק").fill("סטודיו פרטיות")
    page.get_by_role("button", name="המשך").click()
    page.get_by_role("button", name="יצירת העסק").click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{h.BASE}/clients/new"); h.ready(page)
    page.get_by_label("שם פרטי").fill("דנה")
    page.get_by_label("שם משפחה").fill("לוי")
    page.get_by_label("אימייל").fill(f"dana{time.time_ns()}@example.com")
    page.get_by_label("טלפון").fill("050-1234567")
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(page)

    privacy = page.get_by_role("region", name="פרטיות")
    with page.expect_download() as download:
        privacy.get_by_role("link", name="הורדת המידע על הלקוח/ה (JSON)").click()
    document = json.loads(pathlib.Path(download.value.path()).read_text(encoding="utf-8"))
    assert document["client"]["phone"] == "050-1234567", document
    print("1. data export downloaded: ok")

    privacy.get_by_text("מחיקת פרטים אישיים", exact=True).click()
    privacy.get_by_role("button", name="מחיקת הפרטים האישיים").click()
    expect(privacy.get_by_role("alert")).to_have_text("יש לסמן את התיבה כדי לאשר.")
    serious = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    privacy.get_by_label("ברור לי שהפרטים האישיים של דנה לוי יימחקו לצמיתות").check()
    privacy.get_by_role("button", name="מחיקת הפרטים האישיים").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("לקוח/ה שנמחק/ה")
    expect(page.get_by_role("status").filter(has_text="הפרטים האישיים של הלקוח/ה נמחקו")).to_be_visible()
    expect(page.get_by_label("טלפון")).to_have_value("")
    expect(page.get_by_role("region", name="פרטיות")).to_have_count(0)
    page.screenshot(path=f"{h.OUT}/privacy-erased.png", full_page=True)
    print("2. erased: ok | a11y:", serious or "ok")
    b.close()
