"""Messaging end to end (simulated): a business turns on WhatsApp & SMS, broadcasts to its
active clients from a suggested template, and sees the message on a client's page."""

import pathlib
import re
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"messages{time.time_ns()}@example.com"
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
    owner.get_by_label("שם העסק").fill("סטודיו הודעות")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("checkbox", name=re.compile("^וואטסאפ")).check()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)

    for first, phone in (("דנה", "050-1234567"), ("נועה", "052-7654321")):
        owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
        owner.get_by_label("שם פרטי").fill(first)
        owner.get_by_label("טלפון").fill(phone)
        owner.get_by_role("button", name="יצירה").click()
        owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$"))
    client_url = owner.url
    print("1. messaging on, two clients: ok")

    owner.get_by_role("navigation", name="ניווט ראשי").get_by_role("link", name="הודעות").click()
    owner.wait_for_url("**/messages"); h.ready(owner)
    owner.get_by_label("להתחיל מתבנית").select_option(label="מתגעגעים")
    expect(owner.get_by_role("figure", name="תצוגה מקדימה")).to_contain_text("היי דנה, מזמן לא ראינו אותך בסטודיו הודעות")
    check(owner, "composer")
    owner.screenshot(path=f"{h.OUT}/messages.png", full_page=True)
    owner.get_by_role("button", name="שליחה ל-2 נמענים").click()
    expect(owner.get_by_role("status").filter(has_text="נשלח ל-2 נמענים")).to_be_visible()
    expect(owner.get_by_role("region", name="תפוצות שנשלחו")).to_contain_text("כל הלקוחות הפעילים")
    print("2. broadcast sent (simulated): ok")

    owner.goto(client_url); h.ready(owner)
    messages = owner.get_by_role("region", name="הודעות")
    expect(messages).to_contain_text("היי נועה, מזמן לא ראינו אותך")
    expect(messages.get_by_role("link", name="פתיחה בוואטסאפ")).to_have_attribute("href", "https://wa.me/972527654321")
    check(owner, "client messages")
    owner.emulate_media(color_scheme="dark")
    owner.goto(f"{h.BASE}/messages"); check(owner, "composer (dark)")
    print("3. message on the client's page, WhatsApp link: ok")
    b.close()

print("4. accessibility:", "; ".join(a11y) if a11y else "no serious issues")
