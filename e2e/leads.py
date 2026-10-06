"""CRM end to end: a business turns on the CRM module, someone leaves their details on its
public inquiry form, and the owner works the lead through the pipeline into a client."""

import pathlib
import re
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email = f"crm{stamp}@example.com"
a11y: list[str] = []


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']} x{len(v['nodes'])}: {v['nodes'][0]['target']}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); h.to_onboarding(owner)
    owner.get_by_label("שם העסק").fill("סטודיו לידים")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("checkbox", name=re.compile("CRM ולידים")).check()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)
    owner.get_by_role("navigation", name="ניווט ראשי").get_by_role("link", name="לידים").click()
    owner.wait_for_url("**/leads"); check(owner, "board (empty)")
    link = owner.locator("a[href*='/inquiry/']").get_attribute("href")
    print("1. CRM on, empty pipeline: ok")

    # Someone interested fills the public form.
    visitor = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}).new_page()
    visitor.goto(link); h.ready(visitor)
    expect(visitor.get_by_role("heading", level=1)).to_have_text("סטודיו לידים")
    check(visitor, "inquiry form")
    visitor.get_by_label("שם פרטי").fill("רוני")
    visitor.get_by_label("שם משפחה").fill("אלון")
    visitor.get_by_label("טלפון").fill("052-7654321")
    visitor.get_by_label("במה אתם מתעניינים?").fill("שיעורי בוקר")
    visitor.get_by_role("button", name="שליחה").click()
    expect(visitor.get_by_role("status")).to_contain_text("תודה")
    visitor.screenshot(path=f"{h.OUT}/inquiry.png", full_page=True)
    print("2. inquiry sent from the public form: ok")

    # The owner sees a new lead and works it.
    owner.reload(); h.ready(owner)
    new_column = owner.get_by_role("region", name="חדש")
    expect(new_column.get_by_role("link", name=re.compile("רוני אלון"))).to_be_visible()
    check(owner, "board")
    owner.screenshot(path=f"{h.OUT}/leads-board.png", full_page=True)
    new_column.get_by_role("link", name=re.compile("רוני אלון")).click()
    owner.wait_for_url(re.compile(r".*/leads/[0-9a-f-]{36}$")); h.ready(owner)
    owner.get_by_role("button", name=re.compile("נוצר קשר")).click()
    expect(owner.get_by_role("button", name=re.compile("נוצר קשר"))).to_have_attribute("aria-current", "step")
    owner.get_by_label("מה קרה?").fill("קבענו שיעור ניסיון ליום ראשון")
    owner.get_by_role("button", name="הוספה").click()
    expect(owner.get_by_text("קבענו שיעור ניסיון ליום ראשון")).to_be_visible()
    expect(owner.get_by_text("הועבר לשלב: נוצר קשר")).to_be_visible()
    check(owner, "lead detail")
    owner.emulate_media(color_scheme="dark"); check(owner, "lead detail (dark)")
    owner.screenshot(path=f"{h.OUT}/lead-detail-dark.png", full_page=True)
    owner.emulate_media(color_scheme="light")
    print("3. stage changed and call logged: ok")

    owner.get_by_role("button", name="הפיכה ללקוח").click()
    expect(owner.get_by_role("status").filter(has_text="הליד הפך ללקוח")).to_be_visible()
    owner.get_by_role("link", name="לכרטיס הלקוח").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    expect(owner.get_by_role("heading", level=1)).to_contain_text("רוני אלון")
    owner.goto(f"{h.BASE}/leads"); h.ready(owner)
    expect(owner.get_by_role("region", name="הצלחה").get_by_role("link", name=re.compile("רוני"))).to_be_visible()
    print("4. converted into a client: ok")
    b.close()

print("5. accessibility:", "; ".join(a11y) if a11y else "no serious issues")
