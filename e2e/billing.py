"""MyBiz billing end to end (simulated): a new business sees its trial, gets a dashboard
reminder near the end, adds a test card, and its invoices are issued and paid."""

import pathlib
import re
import subprocess
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email = f"billing{stamp}@example.com"
a11y: list[str] = []


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']} x{len(v['nodes'])}: {v['nodes'][0]['target']}")


def set_trial(sql_interval: str) -> None:
    with psycopg.connect(h.DATABASE_URL) as conn:
        conn.execute(
            f"""UPDATE app.tenants SET trial_ends_at = now() + interval '{sql_interval}'
                WHERE id = (SELECT m.tenant_id FROM app.tenant_members m
                            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s)""",
            (owner_email,),
        )


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו חיוב")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)
    expect(owner.get_by_text("לתקופת הניסיון")).to_have_count(0)  # 14 days left: no reminder

    set_trial("3 days")
    owner.reload(); h.ready(owner)
    owner.get_by_role("link", name=re.compile("נשארו 3 ימים לתקופת הניסיון")).click()
    owner.wait_for_url("**/settings/billing"); h.ready(owner)
    expect(owner.get_by_role("heading", name=re.compile("נשארו 3 ימים"))).to_be_visible()
    check(owner, "billing (trial)")
    print("1. trial with a dashboard reminder: ok")

    owner.get_by_role("button", name="הוספת כרטיס בדיקה").click()
    expect(owner.get_by_text("•••• •••• •••• 4242")).to_be_visible()
    owner.get_by_label("שם לחשבונית").fill("סטודיו חיוב בע״מ")
    owner.get_by_role("button", name="שמירת הפרטים").click()
    expect(owner.get_by_role("status")).to_be_visible()
    print("2. test card and invoice details saved: ok")

    # Two months after the trial: the job issues and charges two invoices.
    set_trial("-62 days")
    subprocess.run(
        ["uv", "run", "python", "-m", "app.jobs", "bill-businesses", "--database-url",
         h.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")],
        cwd="apps/api", check=True, capture_output=True,
    )
    owner.reload(); h.ready(owner)
    expect(owner.get_by_role("heading", name="המנוי פעיל")).to_be_visible()
    rows = owner.get_by_role("table").get_by_role("row")
    expect(rows).to_have_count(3)  # header + 2 invoices
    expect(owner.get_by_role("table").get_by_text("שולמה")).to_have_count(2)
    check(owner, "billing (invoices)")
    owner.screenshot(path=f"{h.OUT}/billing.png", full_page=True)
    owner.get_by_role("link", name=re.compile("^צפייה בחשבונית")).first.click()
    owner.wait_for_url(re.compile(r".*/settings/billing/invoices/[0-9a-f-]{36}$")); h.ready(owner)
    expect(owner.get_by_text("סטודיו חיוב בע״מ")).to_be_visible()
    expect(owner.get_by_text(re.compile("שולם בכרטיס שמסתיים ב-4242"))).to_be_visible()
    check(owner, "invoice")
    owner.emulate_media(color_scheme="dark"); check(owner, "invoice (dark)")
    owner.screenshot(path=f"{h.OUT}/platform-invoice-dark.png", full_page=True)
    print("3. invoices issued, charged and printable: ok")
    b.close()

print("4. accessibility:", "; ".join(a11y) if a11y else "no serious issues")
