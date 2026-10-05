"""Sales: a month of receipts with totals by payment method, month navigation, and the CSV
export for the accountant. Usage: python e2e/sales.py <owner email with demo data>"""

import csv
import io
import pathlib
import sys

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = sys.argv[1]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    h.login(page, email)
    page.get_by_role("navigation", name="ניווט ראשי").get_by_role("link", name="מכירות").click()
    page.wait_for_url("**/sales"); h.ready(page)
    expect(page.get_by_role("heading", level=1)).to_have_text("מכירות")
    rows = page.get_by_role("region", name="קבלות").locator("tbody tr")
    count = rows.count()
    assert count > 0, "the demo business has sales this month"
    expect(page.get_by_text(f"{count} קבלות" if count > 1 else "קבלה אחת")).to_be_visible()
    found = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    page.screenshot(path=f"{h.OUT}/sales.png", full_page=True)

    with page.expect_download() as download:
        page.get_by_role("link", name="ייצוא לרואה החשבון (CSV)").click()
    text = pathlib.Path(download.value.path()).read_text(encoding="utf-8-sig")
    table = list(csv.reader(io.StringIO(text)))
    assert table[0][:3] == ["קבלה", "תאריך", "לקוח"], table[0]
    assert len(table) == count + 1, (len(table), count)

    page.get_by_role("link", name="החודש הקודם").click(); page.wait_for_url("**/sales?month=**"); h.ready(page)
    print(f"sales page ({count} receipts), CSV export, month navigation: ok | a11y:", found or "ok")
    assert not found
