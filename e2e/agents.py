"""Round 5 end to end: the networks demo (branch groups, AI team, scheduled tasks, content studio)
for a new owner, the chat with an agent, and the MyBiz console's broadcast center and AI board.

    uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/agents.py [platform admin email]

Needs the API with the scripted model (fake_ai_api), like dod.py.
"""

import pathlib
import subprocess
import sys
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"agents{time.time_ns()}@example.com"
admin_email = sys.argv[1] if len(sys.argv) > 1 else None
database = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
axe = Axe()
issues: list[str] = []


def check(page, label: str) -> None:
    found = [v for v in axe.run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    issues.extend(f"{label}: {v['id']} {[n['target'] for n in v['nodes']]}" for v in found)


def seed(*args: str) -> None:
    subprocess.run(
        ["uv", "run", "--quiet", "python", "-m", "app.seed", *args, "--months", "1",
         "--database-url", database],
        cwd="apps/api", check=True, capture_output=True,
    )  # fmt: skip


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(owner_email)
    page.get_by_label("סיסמה", exact=True).fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(owner_email)); h.to_onboarding(page)
    seed("--owner-email", owner_email, "--demo", "networks")
    print("1. networks demo seeded")

    # The AI team: the built-in agents, the custom one, and the scheduled tasks board.
    page.goto(f"{h.BASE}/ai"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("צוות ה-AI")
    expect(page.get_by_text("דנה").first).to_be_visible()  # the custom front-desk agent
    expect(page.get_by_role("heading", name="משימות מתוזמנות")).to_be_visible()
    expect(page.get_by_text("סיכום שבועי של מכירות").first).to_be_visible()
    check(page, "ai team")
    page.screenshot(path=f"{h.OUT}/agents-team.png", full_page=True)
    print("2. AI team page, custom agent and the scheduled task: ok")

    # A conversation with one agent (the scripted model answers with real metrics).
    page.goto(f"{h.BASE}/ai?agent=sales"); h.ready(page)
    page.locator("#ai-question").fill("כמה הכנסנו החודש?")
    page.locator("#ai-question").press("Enter")
    expect(page.get_by_text("ב-30 הימים האחרונים").first).to_be_visible(timeout=30000)
    print("3. chat with an agent: ok")

    # The content studio on demo accounts.
    page.goto(f"{h.BASE}/content"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("תוכן וקריאייטיב")
    expect(page.get_by_text("אלה נתוני דמו").first).to_be_visible()
    check(page, "content studio")
    page.screenshot(path=f"{h.OUT}/agents-content.png", full_page=True)
    print("4. content studio dashboard on demo data: ok")

    # Branch groups on the branches page.
    page.goto(f"{h.BASE}/locations"); h.ready(page)
    expect(page.get_by_text("מרכז").first).to_be_visible()
    expect(page.get_by_text("צפון").first).to_be_visible()
    check(page, "branches")
    print("5. branch groups: ok")

    # The MyBiz console: broadcasts and the AI board, for a platform admin.
    if admin_email:
        seed("--owner-email", admin_email, "--demo", "platform")
        admin = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
        h.login(admin, admin_email)
        admin.goto(f"{h.BASE}/platform/broadcasts"); h.ready(admin)
        expect(admin.get_by_role("heading", level=1)).to_have_text("מרכז הפצה")
        expect(admin.get_by_text("צוות ה-AI שלכם הגיע").first).to_be_visible()
        check(admin, "broadcasts")
        admin.goto(f"{h.BASE}/platform/ai"); h.ready(admin)
        expect(admin.locator("main")).to_be_visible()
        check(admin, "platform ai")
        print("6. console broadcasts and AI board: ok")
    b.close()

if issues:
    print("a11y:", *issues, sep="\n  ")
    raise SystemExit(1)
print("agents: ok")
