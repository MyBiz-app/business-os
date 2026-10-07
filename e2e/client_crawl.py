"""Client app review (#39): a client of a busy demo business visits every screen on a phone —
Hebrew light and English dark — and the crawl reports accessibility issues, horizontal
overflow and console errors, with a screenshot of each screen.

    uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" \\
        python e2e/client_crawl.py OWNER_EMAIL_OF_A_SEEDED_BUSINESS
"""

import pathlib
import sys
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = sys.argv[1]
client_email = f"crawl{time.time_ns()}@example.com"
SCREENS = ["home", "schedule", "bookings", "updates", "profile", "receipts", "quotes", "documents"]
axe = Axe()
problems: list[str] = []

with psycopg.connect(h.DATABASE_URL) as conn:
    code, name = conn.execute("""
        SELECT t.join_code, t.name FROM app.tenants t
        JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
        JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        ORDER BY t.created_at DESC LIMIT 1
    """, (owner_email,)).fetchone()


def scan(page, label: str) -> None:
    h.app_ready(page)
    for v in axe.run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            problems.append(f"{label}: {v['id']} {[(n['target'], n['any'][0]['message'][:120] if n.get('any') else '') for n in v['nodes']][:3]}")
    width = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    if width > 1:
        problems.append(f"{label}: horizontal overflow {width}px")
    page.screenshot(path=f"{h.OUT}/client-{label}.png", full_page=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(h.APP); page.wait_for_url("**/sign-in", timeout=60000)
    scan(page, "sign-in")
    page.get_by_label("אימייל").fill(client_email)
    page.get_by_role("button", name="שליחת קוד").click()
    page.get_by_label("קוד בן 6 ספרות").fill(h.otp(client_email))
    page.get_by_role("button", name="כניסה").click(); page.wait_for_url("**/join")
    scan(page, "join")
    page.get_by_label("קוד הצטרפות").fill(code)
    page.get_by_role("button", name="המשך").click()
    page.get_by_label("שם פרטי").fill("דנה")
    page.get_by_label("שם משפחה").fill("כהן")
    scan(page, "join-confirm")
    page.get_by_role("button", name=f"הצטרפות ל{name}").click(); page.wait_for_url("**/home")
    h.app_ready(page)
    assert page.get_by_text("היי דנה").is_visible(), "the greeting uses the name given at join"
    print(f"1. joined {name}: ok")

    for theme, locale in (("light", "he"), ("dark", "en")):
        page.emulate_media(color_scheme=theme)
        if locale == "en":
            page.goto(f"{h.APP}/profile"); h.app_ready(page)
            page.get_by_role("radio", name="English").click()
            page.wait_for_timeout(800)
        for screen in SCREENS:
            page.goto(f"{h.APP}/{screen}")
            scan(page, f"{screen}-{locale}-{theme}")
        print(f"2. screens in {locale}/{theme}: done")

    noisy = [e for e in errors if "favicon" not in e and "DevTools" not in e]
    if noisy:
        problems.append(f"console errors: {noisy[:5]}")
    print("problems:", problems or "none")
    assert not problems
