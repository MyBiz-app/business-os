"""Quotes, deposits and events (#44) on the photography demo
(`python -m app.seed --owner-email <owner> --demo events`): the business writes a quote with
lines and an event date and sends it; the client opens the private link without signing in,
accepts it with their name and pays the deposit; the business sees it paid and the event listed.
Hebrew/light on a wide screen; the client's page in English/dark on a phone.

Usage: python e2e/quotes.py <owner email of the demo> (its password is helpers.PASSWORD)"""

import pathlib
import sys
import time
from datetime import timedelta

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
TITLE = f"צילום חתונה {time.time_ns() % 10000}"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, client_id, client_name = conn.execute("""
        SELECT t.id, c.id, trim(c.first_name || ' ' || coalesce(c.last_name, '')) FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id
        JOIN app.clients c ON c.tenant_id = t.id AND c.status = 'active'
        WHERE u.email = %s AND t.vertical = 'photographers'
        ORDER BY t.created_at DESC, c.created_at LIMIT 1
    """, (OWNER,)).fetchone()
EVENT = (h.local_today() + timedelta(days=40)).isoformat()


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth")
    if width > page.viewport_size["width"] + 1:
        issues.append(f"{label}: wider than the screen ({width}px)")
    page.screenshot(path=f"{h.OUT}/quotes-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    context = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900})
    page = context.new_page()
    h.login(page, OWNER)
    context.add_cookies([{"name": "TENANT_ID", "value": str(tenant_id), "url": h.BASE}])

    # 1. The quotes list (the demo's quotes), then a new quote from the client's card.
    page.goto(f"{h.BASE}/quotes"); h.ready(page)
    expect(page.get_by_role("heading", name="הצעות מחיר", exact=True)).to_be_visible()
    check(page, "list")
    page.goto(f"{h.BASE}/quotes/new?client={client_id}"); h.ready(page)
    page.get_by_label("כותרת", exact=True).fill(TITLE)
    page.get_by_label("פריט 1", exact=True).fill("חבילת יום מלא")
    page.locator("input[name='line.0.price']").fill("8500")
    page.get_by_role("button", name="הוספת פריט").click()
    page.get_by_label("פריט 2", exact=True).fill("שעה נוספת")
    page.locator("input[name='line.1.quantity']").fill("2")
    page.locator("input[name='line.1.price']").fill("600")
    page.get_by_label("תאריך האירוע").fill(EVENT)
    page.get_by_label("שעת התחלה").fill("17:30")
    page.get_by_label("מקום").fill("גן אירועים, הרצליה")
    check(page, "new")
    page.get_by_role("button", name="שמירת טיוטה").click()
    page.wait_for_url("**/quotes/*"); h.ready(page)
    expect(page.get_by_text("טיוטה", exact=True)).to_be_visible()
    expect(page.get_by_text("9,700").first).to_be_visible()
    print("1. new quote with two lines and an event, saved as a draft (total 9,700): ok")

    # 2. Sent: its private link.
    page.get_by_role("button", name="שליחה ללקוח").click()
    expect(page.get_by_text("נשלחה", exact=True)).to_be_visible()
    quote_url = page.url
    check(page, "sent")
    with psycopg.connect(h.DATABASE_URL) as conn:
        token = conn.execute("SELECT token FROM app.quotes WHERE title = %s", (TITLE,)).fetchone()[0]
    print("2. sent; the link is ready to share: ok")

    # 3. The client: no sign-in, accept with a name, pay the deposit (30% of 9,700 = 2,910).
    client_page = b.new_context(locale="en-US", color_scheme="dark", viewport={"width": 390, "height": 844}).new_page()
    client_page.context.add_cookies([{"name": "NEXT_LOCALE", "value": "en", "url": h.BASE}])
    client_page.goto(f"{h.BASE}/q/{token}"); h.ready(client_page)
    expect(client_page.get_by_role("heading", name=TITLE)).to_be_visible()
    check(client_page, "public-en-dark")
    client_page.get_by_label("Your full name").fill(client_name)
    client_page.get_by_role("button", name="Accept the quote").click()
    expect(client_page.get_by_role("heading", name=f"Accepted by {client_name}. Thank you!")).to_be_visible()
    client_page.get_by_role("button", name="Pay the deposit").click()
    expect(client_page.get_by_text("The deposit is paid. See you soon!")).to_be_visible()
    check(client_page, "public-paid")
    print("3. the client accepted by the link and paid the deposit: ok")

    # 4. The business sees it paid and the event listed.
    page.goto(quote_url); h.ready(page)
    expect(page.get_by_text("אושרה", exact=True)).to_be_visible()
    expect(page.get_by_text("2,910").first).to_be_visible()
    page.goto(f"{h.BASE}/events"); h.ready(page)
    expect(page.get_by_text(TITLE, exact=False).first).to_be_visible()
    check(page, "events")
    print("4. the business sees the deposit and the event: ok")
    b.close()

if issues:
    print("ISSUES:", *issues, sep="\n  ")
    sys.exit(1)
print("quotes: all steps passed, no accessibility issues")
