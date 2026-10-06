"""Reports: a demo studio's breakdowns by class, instructor and hour, and members at risk."""

import pathlib
import subprocess
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = f"owner{time.time_ns()}@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email)); h.to_onboarding(page)
    subprocess.run(
        ["uv", "run", "--quiet", "python", "-m", "app.seed", "--owner-email", email,
         "--database-url", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"],
        cwd="apps/api", check=True, capture_output=True,
    )  # fmt: skip
    page.goto(f"{h.BASE}/dashboard"); h.ready(page)
    page.get_by_role("link", name="דוחות").click(); page.wait_for_url("**/reports"); h.ready(page)

    expect(page.get_by_role("heading", level=1)).to_have_text("דוחות")
    by_class = page.get_by_role("region", name="לפי שירות")
    expect(by_class.get_by_role("row")).to_have_count(6)  # header + 5 classes
    busy = page.get_by_role("region", name="השעות העמוסות")  # day × hour heatmap
    expect(busy.get_by_role("rowheader")).to_have_count(7)
    expect(busy).to_contain_text(__import__("re").compile(r"הכי עמוס: יום \S+ \d\d:00"))
    at_risk = page.get_by_role("region", name=__import__("re").compile("שכדאי לפנות"))
    expect(at_risk.get_by_role("link").first).to_be_visible()
    expect(at_risk.locator("ul").first.get_by_role("listitem")).to_have_count(10)
    serious = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    page.screenshot(path=f"{h.OUT}/reports.png", full_page=True)
    page.get_by_role("link", name="90 הימים האחרונים").click(); page.wait_for_url("**period=90"); h.ready(page)
    expect(page.get_by_role("link", name="90 הימים האחרונים")).to_have_attribute("aria-current", "page")
    print("reports: ok | a11y:", serious or "ok")

    page.goto(f"{h.BASE}/clients"); h.ready(page)
    page.locator("select[name=plan]").select_option("none")
    page.locator("select[name=absent]").select_option("30")
    page.get_by_role("button", name="חיפוש", exact=True).click()
    page.wait_for_url("**plan=none**"); h.ready(page)
    expect(page.locator("select[name=plan]")).to_have_value("none")
    expect(page.locator("main table tbody tr").first).to_be_visible()
    print("client filters (no valid plan, absent 30 days): ok")
    b.close()
