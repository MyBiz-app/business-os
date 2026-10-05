"""One owner, two businesses, several branches, end to end (decision T76/T77): the business menu
switches between businesses, "My businesses" shows both with their branches, the branch picker
chooses the current branch, and a new client is filed under it. Hebrew, desktop, light and dark.

    uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/branches.py
"""

import pathlib
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
owner_email = f"branches{time.time_ns()}@example.com"
axe = Axe()
issues: list[str] = []


def check(page, label: str) -> None:
    found = [v for v in axe.run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    issues.extend(f"{label}: {v['id']} {[n['target'] for n in v['nodes']]}" for v in found)


def new_business(page, name: str, vertical: str) -> None:
    page.goto(f"{h.BASE}/onboarding"); h.ready(page)
    page.get_by_label("שם העסק").fill(name)
    page.get_by_label("סוג העסק").select_option(vertical)
    page.get_by_role("button", name="המשך").click()
    page.get_by_role("button", name="יצירת העסק").click()
    page.wait_for_url("**/dashboard"); h.ready(page)


def add_branch(page, name: str) -> None:
    page.goto(f"{h.BASE}/locations/new"); h.ready(page)
    page.get_by_label("שם", exact=True).fill(name)
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/locations**"); h.ready(page)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(owner_email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(owner_email)); page.wait_for_url("**/onboarding"); h.ready(page)

    # A pizza-like chain (here: a pilates chain) with three branches, and a barbershop with one.
    new_business(page, "פילאטיס פלוס", "pilates")
    add_branch(page, "רמת גן")
    add_branch(page, "חיפה")
    new_business(page, "בלייד ברברס", "barbershop")
    print("1. two businesses, 3 + 1 branches: ok")

    # The business menu lists both; switch back to the chain.
    page.locator("aside summary").first.click()
    menu = page.locator("aside details[open]")
    expect(menu.get_by_role("button", name="פילאטיס פלוס")).to_be_visible()
    check(page, "business menu")
    page.screenshot(path=f"{h.OUT}/branches-menu.png")
    menu.get_by_role("button", name="פילאטיס פלוס").click()
    page.wait_for_url("**/dashboard"); h.ready(page)
    print("2. business menu switches businesses: ok")

    # The branch picker: choose Haifa; the side menu shows it.
    picker = page.get_by_label("סניף", exact=True)
    expect(picker).to_have_value("")
    picker.select_option(label="חיפה")
    expect(page.locator("aside summary").first).to_contain_text("חיפה")
    check(page, "dashboard in a branch")
    page.screenshot(path=f"{h.OUT}/branches-dashboard.png")
    print("3. branch picker: ok")

    # A new client defaults to the current branch.
    page.goto(f"{h.BASE}/clients/new"); h.ready(page)
    expect(page.get_by_label("סניף הבית")).to_have_value(page.get_by_label("סניף", exact=True).input_value())
    page.get_by_label("שם פרטי").fill("נועה")
    page.get_by_role("button", name="יצירה").click()
    page.wait_for_url("**/clients/*"); h.ready(page)
    print("4. new client filed under the current branch: ok")

    # My businesses: both, with their branches.
    page.goto(f"{h.BASE}/businesses"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("העסקים שלי")
    cards = page.get_by_role("article")
    expect(cards).to_have_count(2)
    expect(cards.filter(has_text="פילאטיס פלוס")).to_contain_text("3 סניפים")
    expect(cards.filter(has_text="בלייד ברברס")).to_contain_text("סניף אחד")
    check(page, "my businesses")
    page.screenshot(path=f"{h.OUT}/branches-businesses.png", full_page=True)
    page.emulate_media(color_scheme="dark")
    check(page, "my businesses (dark)")
    page.screenshot(path=f"{h.OUT}/branches-businesses-dark.png", full_page=True)
    print("5. my businesses: ok")

    print("a11y:", issues or "ok")
    assert not issues
