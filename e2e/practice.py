"""Documents, time and monthly bills (#45) on the accounting demo
(`python -m app.seed --owner-email <owner> --demo office`): on a client's card the accountant
logs time, sets the retainer, uploads a contract shared with the client and asking to sign it,
bills the month, and the bill opens by its private link to pay; "My time" shows the hours;
then "Billing the month" bills every client at once.
Hebrew/light on a wide screen, the bill's link in English/dark on a phone.

Usage: python e2e/practice.py <owner email of the demo> (its password is helpers.PASSWORD)"""

import pathlib
import re
import sys

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []
PDF = pathlib.Path(h.OUT) / "engagement.pdf"
PDF.write_bytes(b"%PDF-1.4\n%%EOF\n")

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, client_id = conn.execute("""
        SELECT t.id, c.id FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id
        JOIN app.clients c ON c.tenant_id = t.id AND c.status = 'active'
        WHERE u.email = %s AND t.vertical = 'accountants'
        ORDER BY t.created_at DESC, c.created_at LIMIT 1
    """, (OWNER,)).fetchone()


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        issues.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/practice-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    context = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    h.login(page, OWNER)
    context.add_cookies([{"name": "TENANT_ID", "value": str(tenant_id), "url": h.BASE}])
    page.goto(f"{h.BASE}/clients/{client_id}"); h.ready(page)

    # 1. Log time.
    time_section = page.locator("section[aria-labelledby=time-heading]")
    expect(time_section.get_by_role("heading", name="שעות וחיוב")).to_be_visible()
    time_section.get_by_label("שעות", exact=True).fill("1.5")
    time_section.get_by_label("מה נעשה").fill("הכנת דוח מע״מ")
    time_section.get_by_role("button", name="רישום שעות").click()
    expect(time_section.get_by_text("הכנת דוח מע״מ").first).to_be_visible()
    print("1. logged an hour and a half on the client's card: ok")

    # 2. The retainer.
    time_section.get_by_text("ריטיינר ותעריף שעתי").click()
    time_section.get_by_label(re.compile("^תשלום חודשי")).fill("2000")
    time_section.get_by_label("שעות כלולות").fill("1")
    time_section.get_by_label(re.compile("^תעריף לשעה")).fill("400")
    time_section.get_by_role("button", name="שמירה").click()
    expect(time_section.get_by_text(re.compile("ריטיינר .*2,000"))).to_be_visible()
    print("2. retainer: 2,000 a month with an hour included, 400 an hour beyond: ok")

    # 3. A contract shared with the client, asking to sign.
    documents = page.locator("section[aria-labelledby=documents-heading]")
    documents.get_by_text("העלאת מסמך").first.click()
    documents.locator("input[type=file]").set_input_files(str(PDF))
    documents.get_by_label("שם (לא חובה)").fill("הסכם התקשרות 2026")
    documents.locator("select[name=kind]").select_option("contract")
    documents.get_by_label("לבקש מהלקוח לחתום").check()
    documents.get_by_role("button", name="העלאה").click()
    expect(documents.get_by_role("link", name="הסכם התקשרות 2026").first).to_be_visible()
    expect(documents.get_by_text("ממתין לחתימה").first).to_be_visible()
    check(page, "client-card")
    print("3. contract uploaded, shared and waiting for the client's signature: ok")

    # 4. Bill the month: the bill opens; its link asks to pay.
    time_section.get_by_role("button", name="חיוב החודש").click()
    page.wait_for_url("**/quotes/*"); h.ready(page)
    expect(page.get_by_text(re.compile("ריטיינר")).first).to_be_visible()
    check(page, "bill")
    with psycopg.connect(h.DATABASE_URL) as conn:
        token = conn.execute(
            "SELECT token FROM app.quotes WHERE tenant_id = %s AND kind = 'bill' ORDER BY created_at DESC LIMIT 1",
            (tenant_id,),
        ).fetchone()[0]
    phone = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844}).new_page()
    phone.context.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    phone.goto(f"{h.BASE}/q/{token}"); h.ready(phone)
    expect(phone.get_by_role("button", name=re.compile("^Pay · "))).to_be_visible()
    check(phone, "bill-link-en-dark")
    print("4. billed the month; the bill's link asks to pay (English, dark, phone): ok")

    # 5. My time.
    page.goto(f"{h.BASE}/time"); h.ready(page)
    expect(page.get_by_text("הכנת דוח מע״מ").first).to_be_visible()
    check(page, "my-time")
    print("5. My time shows the logged work: ok")

    # 6. Billing the month for every client at once (this month: its time isn't billed yet).
    with psycopg.connect(h.DATABASE_URL) as conn:
        month = conn.execute(
            "SELECT to_char(now() AT TIME ZONE time_zone, 'YYYY-MM') FROM app.tenants WHERE id = %s",
            (tenant_id,),
        ).fetchone()[0]
    page.goto(f"{h.BASE}/bills?month={month}"); h.ready(page)
    expect(page.get_by_role("heading", name="חיוב חודשי", level=1)).to_be_visible()
    rows = page.get_by_role("table").get_by_role("checkbox", checked=True)
    chosen = rows.count()
    assert chosen > 1, f"expected several clients to bill, got {chosen}"
    check(page, "billing-run")
    page.get_by_role("button", name=re.compile(f"^חיוב {chosen} לקוחות")).click()
    expect(page.get_by_role("heading", name=re.compile(f"נוצרו {chosen} חשבונות"))).to_be_visible(timeout=30000)
    check(page, "billing-run-done")
    page.goto(f"{h.BASE}/bills?month={month}"); h.ready(page)
    expect(page.get_by_role("table").get_by_role("checkbox", checked=True)).to_have_count(0)
    print(f"6. billed {chosen} clients at once for {month}; a second look shows them billed: ok")
    b.close()

if issues:
    print("ISSUES:", *issues, sep="\n  ")
    sys.exit(1)
print("practice: all steps passed, no accessibility issues")
