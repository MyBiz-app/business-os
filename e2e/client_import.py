"""Client import: upload a Hebrew CSV, fix a column mapping, preview, import, see the clients."""

import pathlib
import time

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = f"owner{time.time_ns()}@example.com"
CSV = (
    "שם מלא,נייד,דוא\"ל,יום הולדת,הערות פנימיות\n"
    "דנה לוי,050-1234567,dana@example.com,14/03/1990,ברך כואבת\n"
    "יוסי כהן,0521112233,,01.07.1985,\n"
    "דנה לוי,050-1234567,dana@example.com,14/03/1990,\n"
    "נועה,0549998877,לא-אימייל,,\n"
).encode("cp1255")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email)); page.wait_for_url("**/onboarding"); h.ready(page)
    page.get_by_label("שם העסק").fill("סטודיו ייבוא")
    page.get_by_role("button", name="המשך").click()
    page.get_by_role("button", name="יצירת העסק").click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{h.BASE}/clients"); h.ready(page)
    page.get_by_role("link", name="ייבוא מקובץ").click(); page.wait_for_url("**/clients/import"); h.ready(page)
    page.get_by_label("קובץ CSV או Excel").set_input_files(
        files=[{"name": "clients.csv", "mimeType": "text/csv", "buffer": CSV}]
    )
    preview = page.get_by_role("region", name="תצוגה מקדימה")
    expect(preview.get_by_text("2 לקוחות חדשים")).to_be_visible(timeout=15000)
    expect(preview.get_by_text("אחד/ת כבר קיים/ת")).to_be_visible()
    expect(preview.get_by_text("שורה 5: כתובת האימייל לא תקינה")).to_be_visible()
    print("1. Hebrew Windows CSV recognized, preview with duplicate and invalid row: ok")

    notes = page.get_by_label("שדה לעמודה הערות פנימיות")
    expect(notes).to_have_value("")  # not a header we know
    notes.select_option("notes")
    expect(notes).to_have_value("notes", timeout=15000)
    serious = [v["id"] for v in Axe().run(page).response["violations"] if v["impact"] in ("serious", "critical")]
    page.screenshot(path=f"{h.OUT}/import-preview.png", full_page=True)
    print("2. mapping changed by hand: ok", "| a11y:", serious or "ok")

    page.get_by_label("מאיפה הגיעו הלקוחות (לא חובה)").select_option("website")
    page.get_by_role("button", name="ייבוא 2 לקוחות").click()
    expect(page.get_by_role("status").filter(has_text="יובאו 2 לקוחות.")).to_be_visible(timeout=15000)
    page.get_by_role("link", name="לרשימת הלקוחות").click(); page.wait_for_url("**/clients"); h.ready(page)
    page.get_by_role("link", name="דנה לוי").click(); h.ready(page)
    expect(page.get_by_role("textbox", name="הערות", exact=True)).to_have_value("ברך כואבת")
    expect(page.get_by_label("טלפון")).to_have_value("050-1234567")
    print("3. imported, notes and phone kept: ok")
    b.close()
