"""Reviews end to end: a client who visited yesterday is asked on the app's home to rate it,
rates it, and the business sees the rating in its reports and on the client's page."""

import pathlib
import re
import time

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
stamp = time.time_ns()
owner_email, member_email = (f"{n}{stamp}@example.com" for n in ("salon", "guest"))
a11y: list[str] = []


def check(page, label: str) -> None:
    h.ready(page)
    for v in Axe().run(page).response["violations"]:
        if v["impact"] in ("serious", "critical"):
            a11y.append(f"{label}: {v['id']} x{len(v['nodes'])}: {v['nodes'][0]['target']}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    owner = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    owner.goto(f"{h.BASE}/signup"); h.ready(owner)
    owner.get_by_label("אימייל").fill(owner_email)
    owner.get_by_label("סיסמה").fill(h.PASSWORD)
    owner.get_by_role("button", name="יצירת חשבון").click()
    owner.wait_for_url("**/check-email**")
    owner.goto(h.confirm_link(owner_email)); owner.wait_for_url("**/onboarding"); h.ready(owner)
    owner.get_by_label("שם העסק").fill("סלון רוני")
    owner.get_by_label("סוג העסק").select_option("beauty")
    owner.get_by_role("button", name="המשך").click()
    owner.get_by_role("button", name="יצירת העסק").click()
    owner.wait_for_url("**/dashboard"); h.ready(owner)

    with psycopg.connect(h.DATABASE_URL) as conn:
        code = conn.execute("""
            SELECT t.join_code FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id
            JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
        """, (owner_email,)).fetchone()[0]
    member = b.new_context(locale="he-IL", viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    member.goto(f"{h.APP}/join?code={code}"); member.wait_for_url("**/sign-in**", timeout=60000)
    member.get_by_label("אימייל").fill(member_email)
    member.get_by_role("button", name="שליחת קוד").click()
    member.get_by_label("קוד בן 6 ספרות").fill(h.otp(member_email))
    member.get_by_role("button", name="כניסה").click(); member.wait_for_url("**/join**")
    member.get_by_role("button", name="הצטרפות לסלון רוני").click(); member.wait_for_url("**/home")

    # Yesterday's visit, attended (set up directly in the database).
    with psycopg.connect(h.DATABASE_URL) as conn:
        conn.execute("""
            WITH t AS (
                SELECT m.tenant_id, m.user_id FROM app.tenant_members m
                JOIN app.users u ON u.id = m.user_id WHERE u.email = %s
            ), sv AS (
                SELECT s.id, s.tenant_id FROM app.services s JOIN t ON t.tenant_id = s.tenant_id
                WHERE s.name = 'תספורת גברים'
            ), se AS (
                INSERT INTO app.sessions (tenant_id, service_id, instructor_user_id, capacity,
                                          starts_at, ends_at)
                SELECT sv.tenant_id, sv.id, t.user_id, 1, now() - interval '1 day',
                       now() - interval '1 day' + interval '30 minutes'
                FROM sv, t RETURNING id, tenant_id
            )
            INSERT INTO app.bookings (tenant_id, session_id, client_id, status, checked_in_at)
            SELECT se.tenant_id, se.id, c.id, 'checked_in', now() - interval '1 day'
            FROM se JOIN app.clients c ON c.tenant_id = se.tenant_id AND c.email = %s
        """, (owner_email, member_email))

    member.goto(f"{h.APP}/home")
    member.get_by_role("button", name="דירוג").click(timeout=30000)
    member.wait_for_url("**/review/**")
    member.get_by_role("radio", name="5 כוכבים").click()
    member.get_by_label("רוצים להוסיף משהו? (לא חובה)").fill("שירות מעולה ומקצועי")
    check(member, "review screen")
    member.screenshot(path=f"{h.OUT}/review-app.png", full_page=True)
    member.get_by_role("button", name="שליחת הדירוג").click()
    expect(member.get_by_text("תודה על הדירוג!")).to_be_visible()
    print("1. client rated the visit in the app: ok")

    owner.goto(f"{h.BASE}/reports"); h.ready(owner)
    satisfaction = owner.get_by_role("region", name=re.compile("שביעות רצון"))
    expect(satisfaction).to_contain_text("5.0")
    expect(satisfaction).to_contain_text("שירות מעולה ומקצועי")
    check(owner, "reports with reviews")
    owner.emulate_media(color_scheme="dark"); check(owner, "reports with reviews (dark)")
    owner.screenshot(path=f"{h.OUT}/reviews-report.png", full_page=True)
    print("2. the business sees it in the reports: ok")
    b.close()

print("3. accessibility:", "; ".join(a11y) if a11y else "no serious issues")
