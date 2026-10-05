"""Locked modules: a business without CRM and WhatsApp still sees them in the menu, locked;
the preview shows what they do and what changes on the invoice, and "add to plan" turns the
module on and opens it."""

import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"upgrade{time.time_ns()}@example.com"
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
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו שדרוג")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)

    nav = owner.get_by_role("navigation", name="ניווט ראשי")
    expect(nav.get_by_role("link", name="לידים — לא בחבילה שלך")).to_be_visible()
    expect(nav.get_by_role("link", name="הודעות — לא בחבילה שלך")).to_be_visible()
    expect(nav.get_by_role("link", name="אפליקציה ללקוחות", exact=True)).to_be_visible()

    owner.goto(f"{h.BASE}/leads"); owner.wait_for_url("**/upgrade/crm")
    expect(owner.get_by_role("heading", level=1)).to_have_text("להפוך יותר פניות ללקוחות?")
    expect(owner.get_by_text("עוד לא בחבילה שלך")).to_be_visible()
    expect(owner.get_by_role("region", name="מה משתנה בחשבונית")).to_contain_text("39")
    check(owner, "upgrade-crm")
    owner.screenshot(path=f"{h.OUT}/upgrade-crm.png", full_page=True)
    owner.get_by_role("button", name=re.compile(r"להוסיף לחבילה · \+\W*39")).click()
    owner.wait_for_url("**/leads"); h.ready(owner)
    expect(nav.get_by_role("link", name="לידים", exact=True)).to_have_attribute("aria-current", "page")
    with psycopg.connect(h.DATABASE_URL) as conn:
        modules = conn.execute(
            """SELECT array_agg(module_key ORDER BY module_key) FROM app.tenant_modules m
               JOIN app.tenant_members tm ON tm.tenant_id = m.tenant_id
               JOIN app.users u ON u.id = tm.user_id WHERE u.email = %s""",
            (owner_email,),
        ).fetchone()[0]
    assert modules == ["ai_basic", "client_app", "crm"], modules
    print("locked CRM: preview, invoice change, add to plan: ok")

    # Phone, English, dark: the WhatsApp preview.
    phone = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844}, is_mobile=True)
    phone.add_cookies(owner.context.cookies())
    page = phone.new_page()
    page.goto(h.BASE + "/upgrade/whatsapp"); h.ready(page)
    page.locator("header select").first.select_option("en"); page.wait_for_timeout(1500)
    page.goto(h.BASE + "/upgrade/whatsapp")
    expect(page.get_by_role("heading", level=1)).to_have_text("Remind clients on WhatsApp automatically?")
    check(page, "upgrade-whatsapp-phone")
    page.screenshot(path=f"{h.OUT}/upgrade-whatsapp-phone.png", full_page=True)
    print("phone preview (en, dark): ok")

    print("a11y:", a11y or "ok")
    assert not a11y
