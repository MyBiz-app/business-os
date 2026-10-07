"""The client app's account round: a new client of the accounting-firm demo finds what waits for
them on the home screen (a bill to pay, a quote to answer, a contract to sign), sees the same in
"In my account" on the profile, signs the contract, and the home screen no longer asks for it.
On a phone, Hebrew/light, then the profile in dark mode, with axe on every screen.

Needs the client app (`pnpm dev:app`) and the accounting-firm demo
(`python -m app.seed --owner-email <owner> --demo office`).

Usage: python e2e/client_account.py <owner email of the demo>"""

import pathlib
import re
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

OWNER = sys.argv[1]
CLIENT = f"account{time.time_ns()}@example.com"
CONTRACT = "חוזה התקשרות 2027"
pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
issues: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant_id, code, name = conn.execute("""
        SELECT t.id, t.join_code, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s AND t.vertical = 'accountants'
        ORDER BY t.created_at DESC LIMIT 1
    """, (OWNER,)).fetchone()
    conn.execute("UPDATE app.tenants SET requires_health_declaration = false WHERE id = %s", (tenant_id,))


def plant(client_id) -> tuple[int, int]:
    """What the firm prepared for the new client: a contract to sign, a bill and a quote."""
    with psycopg.connect(h.DATABASE_URL) as conn:
        conn.execute("""
            INSERT INTO app.client_documents
                (tenant_id, client_id, name, kind, content_type, size, content, shared, sign_requested)
            VALUES (%s, %s, %s, 'contract', 'application/pdf', 20, %s, true, true)
        """, (tenant_id, client_id, CONTRACT, b"%PDF-1.4 e2e contract"))
        numbers = []
        for kind, status, title, price in (
            ("bill", "accepted", "חשבון ספטמבר", 180000),
            ("quote", "sent", "דוח שנתי 2026", 350000),
        ):
            number = conn.execute(
                "SELECT coalesce(max(number), 1000) + 1 FROM app.quotes WHERE tenant_id = %s", (tenant_id,)
            ).fetchone()[0]
            quote_id = conn.execute("""
                INSERT INTO app.quotes (tenant_id, client_id, number, kind, title, status, currency,
                                        deposit_percent, sent_at, accepted_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'ILS', %s, now(),
                        CASE WHEN %s = 'accepted' THEN now() END)
                RETURNING id
            """, (tenant_id, client_id, number, kind, title, status, 100 if kind == "bill" else 30, status)).fetchone()[0]
            conn.execute("""
                INSERT INTO app.quote_lines (tenant_id, quote_id, position, description, quantity, unit_price)
                VALUES (%s, %s, 0, %s, 1, %s)
            """, (tenant_id, quote_id, title, price))
            numbers.append(number)
        return numbers[0], numbers[1]


def check(page, label: str) -> None:
    h.app_ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            issues.append(f"{label}: {v['id']} {[n['target'] for n in v['nodes']][:3]}")
    if page.evaluate("document.documentElement.scrollWidth - window.innerWidth") > 1:
        issues.append(f"{label}: horizontal overflow")
    page.screenshot(path=f"{h.OUT}/account-app-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    page.goto(h.APP); page.wait_for_url("**/sign-in", timeout=60000)
    page.get_by_label("אימייל").fill(CLIENT)
    page.get_by_role("button", name="שליחת קוד").click()
    page.get_by_label("קוד בן 6 ספרות").fill(h.otp(CLIENT))
    page.get_by_role("button", name="כניסה").click(); page.wait_for_url("**/join")
    page.get_by_label("קוד הצטרפות").fill(code)
    page.get_by_role("button", name="המשך").click()
    page.get_by_label("שם פרטי").fill("מיכל")
    page.get_by_role("button", name=f"הצטרפות ל{name}").click(); page.wait_for_url("**/home")
    with psycopg.connect(h.DATABASE_URL) as conn:
        client_id = conn.execute("""
            SELECT c.id FROM app.clients c JOIN app.users u ON u.id = c.user_id
            WHERE u.email = %s AND c.tenant_id = %s
        """, (CLIENT, tenant_id)).fetchone()[0]
    bill, quote = plant(client_id)
    print(f"1. joined {name}; the firm prepared bill {bill}, quote {quote} and a contract: ok")

    # 2. Home: what waits for me.
    page.reload(); h.app_ready(page)
    page.get_by_role("heading", name="מחכה לך").wait_for(timeout=30000)
    expect(page.get_by_role("button", name=re.compile(f"לתשלום: חשבון {bill}"))).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(f"לאשר הצעת מחיר {quote}"))).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(f"לחתום על „{CONTRACT}”"))).to_be_visible()
    check(page, "home")
    print("2. home shows a bill to pay, a quote to answer and a contract to sign: ok")

    # 3. Profile: in my account.
    page.get_by_role("tab", name=re.compile("פרופיל")).click()
    page.get_by_role("heading", name="בחשבון שלי").wait_for(timeout=30000)
    expect(page.get_by_role("button", name=re.compile("המסמכים שלי"))).to_be_visible()
    expect(page.get_by_text("אחד לחתימה")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile("הצעות מחיר וחשבונות"))).to_be_visible()
    check(page, "profile")
    page.get_by_role("button", name=re.compile("הצעות מחיר וחשבונות")).click(); page.wait_for_url("**/quotes")
    expect(page.get_by_text(f"חשבון {bill} · חשבון ספטמבר")).to_be_visible(timeout=30000)
    expect(page.get_by_text(re.compile("נותרו .*1,800.* לתשלום"))).to_be_visible()
    check(page, "quotes")
    print("3. profile lists documents (one to sign) and quotes and bills; the bill shows what's left: ok")

    # 4. Sign the contract from the home screen.
    page.goto(f"{h.APP}/home"); h.app_ready(page)
    page.get_by_role("button", name=re.compile(f"לחתום על „{CONTRACT}”")).click()
    page.wait_for_url("**/documents")
    page.get_by_role("button", name=f"חתימה – {CONTRACT}").click()
    page.get_by_label("השם המלא שלך").fill("מיכל כהן")
    page.get_by_role("button", name="חתימה", exact=True).click()
    expect(page.get_by_text(re.compile("מיכל כהן"))).to_be_visible(timeout=30000)
    check(page, "documents")
    page.goto(f"{h.APP}/home"); h.app_ready(page)
    page.get_by_role("heading", name="מחכה לך").wait_for(timeout=30000)
    expect(page.get_by_role("button", name=re.compile("לחתום על"))).to_have_count(0)
    print("4. signed the contract; home no longer asks for it: ok")

    # 5. Dark mode.
    page.emulate_media(color_scheme="dark")
    page.get_by_role("tab", name=re.compile("פרופיל")).click()
    page.get_by_role("heading", name="בחשבון שלי").wait_for(timeout=30000)
    check(page, "profile-dark")
    print("5. profile in dark mode: ok")
    b.close()

if issues:
    print("\n".join(issues))
    sys.exit(1)
print("client account: all steps passed, no accessibility issues")
