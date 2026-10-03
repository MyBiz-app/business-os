"""Custom roles through the UI: create a role, give it to a team member, see their access change."""

import re
import time

from playwright.sync_api import expect, sync_playwright

import helpers as h

stamp = time.time_ns()
owner_email, coach_email = f"owner{stamp}@example.com", f"coach{stamp}@example.com"


def signup(page, email):
    page.goto(f"{h.BASE}/signup")
    h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה").fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email))


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    signup(owner, owner_email)
    owner.wait_for_url("**/onboarding")
    h.ready(owner)
    owner.get_by_label("שם העסק").fill("סטודיו תפקידים")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard")

    owner.goto(f"{h.BASE}/team")
    h.ready(owner)
    owner.get_by_label("אימייל", exact=True).fill(coach_email)
    owner.get_by_label("תפקיד", exact=True).select_option("staff")
    owner.get_by_role("button", name="יצירת קישור הזמנה").click()
    link = owner.get_by_role("textbox", name="העתקת הקישור").input_value()
    coach = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    coach.goto(link)
    h.ready(coach)
    coach.get_by_role("link", name="יצירת חשבון").click()
    coach.wait_for_url("**/signup?next=**")
    h.ready(coach)
    coach.get_by_label("אימייל").fill(coach_email)
    coach.get_by_label("סיסמה").fill(h.PASSWORD)
    coach.get_by_role("button", name="יצירת חשבון").click()
    coach.wait_for_url("**/check-email**")
    coach.goto(h.confirm_link(coach_email))
    coach.wait_for_url("**/invite/**")
    h.ready(coach)
    coach.get_by_role("button", name=re.compile("הצטרפות ל")).click()
    coach.wait_for_url("**/dashboard")
    nav = coach.get_by_role("navigation", name="ניווט ראשי")
    expect(nav.get_by_role("link", name="הגדרות")).to_have_count(0)
    coach.goto(f"{h.BASE}/plans/new")
    h.ready(coach)
    expect(coach).to_have_url(re.compile(r".*/plans$"))  # staff cannot edit plans
    print("coach starts as read-only staff: ok")

    # Create a role "מנהל תוכניות" that may edit the catalog.
    owner.goto(f"{h.BASE}/team/roles")
    h.ready(owner)
    form = owner.get_by_role("region", name="תפקיד חדש")
    form.get_by_label("שם התפקיד").fill("מנהל מסלולים")
    form.get_by_label(re.compile("עריכת שירותים ומסלולים")).check()
    form.get_by_label(re.compile("צפייה בשירותים ובמסלולים")).check()
    form.get_by_role("button", name="יצירה").click()
    expect(owner.get_by_text("התפקיד נוצר.")).to_be_visible()
    owner.screenshot(path=f"{h.OUT}/r1-role.png", full_page=True)
    duplicate = owner.get_by_role("region", name="תפקיד חדש")
    duplicate.get_by_label("שם התפקיד").fill("מנהל מסלולים")
    duplicate.get_by_role("button", name="יצירה").click()
    expect(owner.get_by_text("כבר יש תפקיד בשם הזה.")).to_be_visible()
    print("role created, duplicate name rejected: ok")

    # Give it to the coach from the team page.
    owner.goto(f"{h.BASE}/team")
    h.ready(owner)
    select = owner.get_by_label(f"תפקיד: {coach_email}")
    with owner.expect_response(lambda r: r.request.method == "POST"):
        select.select_option(label="מנהל מסלולים")
    owner.reload()
    h.ready(owner)
    expect(owner.get_by_label(f"תפקיד: {coach_email}")).to_have_value(re.compile("custom:"))

    coach.goto(f"{h.BASE}/plans/new")
    h.ready(coach)
    expect(coach.get_by_role("heading", name="מסלול חדש")).to_be_visible()
    coach.goto(f"{h.BASE}/dashboard")
    h.ready(coach)
    nav = coach.get_by_role("navigation", name="ניווט ראשי")
    coach.screenshot(path=f"{h.OUT}/r2-coach.png")
    expect(nav.get_by_role("link", name="מנויים וכרטיסיות")).to_be_visible()
    expect(nav.get_by_role("link", name="לוח שיעורים")).to_have_count(0)  # only what the role gives
    print("custom role changes access: ok")

    # A role in use cannot be deleted.
    owner.goto(f"{h.BASE}/team/roles")
    h.ready(owner)
    owner.once("dialog", lambda d: d.accept())
    owner.get_by_role("button", name="מחיקת התפקיד").click()
    expect(owner.get_by_text("התפקיד הזה עדיין מוקצה")).to_be_visible()
    print("role in use is protected: ok")
    b.close()
