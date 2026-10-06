"""Industry client details end to end: a garage records a customer's car and its service
history (the vertical pack decides the fields and the words)."""

import pathlib
import re
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"garage{time.time_ns()}@example.com"
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
    owner.get_by_label("שם העסק").fill("מוסך מוטי")
    owner.get_by_label("סוג העסק").select_option("garage")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)

    owner.goto(f"{h.BASE}/clients/new"); h.ready(owner)
    owner.get_by_label("שם פרטי").fill("אבי")
    owner.get_by_role("button", name="יצירה").click()
    owner.wait_for_url(re.compile(r".*/clients/[0-9a-f-]{36}$")); h.ready(owner)
    vehicle = owner.get_by_role("region", name="פרטי הרכב")
    vehicle.get_by_label("מספר רישוי").fill("12-345-67")
    vehicle.get_by_label("יצרן").fill("טויוטה")
    vehicle.get_by_label("דגם").fill("קורולה")
    vehicle.get_by_label("שנת ייצור").fill("2019")
    vehicle.get_by_label("קילומטראז׳").fill("84000")
    vehicle.get_by_role("button", name="שמירה").click()
    expect(vehicle.get_by_role("status")).to_be_visible()
    owner.reload(); h.ready(owner)
    expect(owner.get_by_role("region", name="פרטי הרכב").get_by_label("דגם")).to_have_value("קורולה")
    print("1. vehicle details saved: ok")

    history = owner.get_by_role("region", name="היסטוריית שירות")
    history.get_by_label("מה נעשה / מה חשוב לזכור?").fill("הוחלפו רפידות בלם קדמיות")
    history.get_by_role("button", name="הוספת רשומה").click()
    expect(history.get_by_text("הוחלפו רפידות בלם קדמיות")).to_be_visible()
    check(owner, "client page (garage)")
    owner.emulate_media(color_scheme="dark"); check(owner, "client page (garage, dark)")
    owner.screenshot(path=f"{h.OUT}/garage-client.png", full_page=True)
    print("2. service history note added: ok")
    b.close()

print("3. accessibility:", "; ".join(a11y) if a11y else "no serious issues")
