"""Pets under their owners (#43) in the business web app, on the pet grooming demo
(`python -m app.seed --owner-email <owner> --demo pets`): an owner's card lists their pets and
a new pet is added with its details; booking an appointment picks which pet comes, and the
session's roster shows "pet · owner". Hebrew/light on a wide screen, then the owner's card in
English/dark on a phone.

Usage: python e2e/pets.py <owner email of the demo> (its password is helpers.PASSWORD)"""

import pathlib
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
PET = f"פיצי {time.time_ns() % 1000}"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, client_id, first, last = conn.execute("""
        SELECT t.id, c.id, c.first_name, coalesce(c.last_name, '') FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id
        JOIN app.clients c ON c.tenant_id = t.id AND c.status = 'active'
        WHERE u.email = %s AND t.vertical = 'pet_grooming'
          AND EXISTS (SELECT 1 FROM app.dependents d WHERE d.client_id = c.id)
        ORDER BY t.created_at DESC, c.created_at LIMIT 1
    """, (OWNER,)).fetchone()
    pets = [row[0] for row in conn.execute(
        "SELECT name FROM app.dependents WHERE client_id = %s AND active ORDER BY name", (client_id,))]
OWNER_NAME = f"{first} {last}".strip()


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        issues.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/pets-{label}.png", full_page=True)


def as_salon(context) -> None:
    context.add_cookies([{"name": "TENANT_ID", "value": str(tenant_id), "url": h.BASE}])


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    context = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    h.login(page, OWNER)
    as_salon(context)

    # 1. The owner's card lists their pets; a new one is added with its details.
    page.goto(f"{h.BASE}/clients/{client_id}"); h.ready(page)
    section = page.locator("section[aria-labelledby=dependents-heading]")
    expect(section.get_by_role("heading", name="חיות מחמד")).to_be_visible()
    for name in pets:
        expect(section.get_by_text(name, exact=True)).to_be_visible()
    section.get_by_text("הוספת חיית מחמד").first.click()
    form = section.locator("details").last.locator("form")
    form.get_by_label("שם").fill(PET)
    form.locator("select[name='field.species']").select_option("dog")
    form.get_by_label("גזע").fill("פודל")
    form.get_by_label("משקל (ק\"ג)").fill("7")
    form.get_by_role("button", name="הוספת חיית מחמד").click()
    expect(section.get_by_text(PET, exact=True)).to_be_visible()
    expect(section.get_by_text("גזע: פודל").first).to_be_visible()
    check(page, "owner-card")
    print(f"1. owner card: {len(pets)} pets listed, {PET} added: ok")

    # 2. An appointment is booked for the new pet; the roster shows "pet · owner".
    page.goto(f"{h.BASE}/schedule/appointment?q={first}"); h.ready(page)
    choice = page.get_by_label(f"{PET} · {OWNER_NAME}")
    choice.check()
    check(page, "book-appointment")
    page.get_by_role("button", name="קביעת התור").click()
    page.wait_for_url("**/schedule/**booked=1"); h.ready(page)
    roster = page.locator("section[aria-labelledby=roster-heading]")
    expect(roster.get_by_text(PET, exact=True)).to_be_visible()
    expect(roster.get_by_role("link", name=OWNER_NAME)).to_be_visible()
    check(page, "roster")
    print("2. appointment booked for the pet, roster shows pet and owner: ok")

    # 3. English/dark on a phone: the owner's card.
    phone = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844})
    page = phone.new_page()
    h.login(page, OWNER)
    as_salon(phone)
    page.context.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    page.goto(f"{h.BASE}/clients/{client_id}"); h.ready(page)
    expect(page.locator("section[aria-labelledby=dependents-heading]").get_by_text(PET, exact=True)).to_be_visible()
    check(page, "owner-card-en-dark")
    print("3. owner card on a phone (dark): ok")
    b.close()

if issues:
    print("ISSUES:", *issues, sep="\n  ")
    sys.exit(1)
print("pets: all steps passed, no accessibility issues")
