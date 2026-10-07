"""The sign-up journey survives the confirmation email being opened in another browser (a mail
app's own browser): the plan waits on the account, so signing in anywhere returns the owner to
the payment step instead of offering to set up a business again."""

import base64
import json
import time

from playwright.sync_api import expect, sync_playwright

import helpers as h

plan = {"vertical": "barbershop", "name": "Resume Cuts", "clients": 100, "staff": 2, "locations": 1, "currency": "ILS", "modules": {"client_app": 1}}
encoded = base64.urlsafe_b64encode(json.dumps(plan).encode()).decode().rstrip("=")
finish = f"/start/finish?p={encoded}"
email = f"resume{time.time_ns()}@example.com"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())

    first = b.new_context(locale="en-US").new_page()
    first.goto(f"{h.BASE}/signup?next={finish.replace('?', '%3F').replace('=', '%3D')}")
    h.ready(first)
    first.locator("input[type=email]").fill(email)
    first.locator("input[type=password]").fill(h.PASSWORD)
    first.locator("form button[type=submit]").last.click()
    first.wait_for_url("**/check-email**")

    # The link opened elsewhere: no cookie from the first browser.
    other = b.new_context(locale="en-US").new_page()
    other.goto(h.confirm_link(email))
    other.wait_for_url("**/start/finish?p=**")
    print("confirmed in another browser: back at the payment step")

    # Signing in later, from a third browser, also resumes.
    third = b.new_context(locale="en-US").new_page()
    h.login(third, email)
    third.wait_for_url("**/start/finish?p=**")
    expect(third.get_by_text("Resume Cuts", exact=False).first).to_be_visible()
    print("signed in from a third browser: back at the payment step")

    # "Not now" still leads to the welcome page (sample business).
    third.get_by_role("link", name="Not now – explore a sample business first").click()
    third.wait_for_url("**/welcome?fresh=1")
    expect(third.get_by_role("heading", level=1)).to_be_visible()

    # Once the business exists there is nothing to resume.
    third.goto(h.BASE + finish)
    third.get_by_label("Name on card").fill("Resume Owner")
    third.get_by_role("button", name="Start my free trial").click()
    third.wait_for_url("**/dashboard?welcome=1")
    third.goto(h.BASE + "/welcome")
    third.wait_for_url("**/dashboard")
    print("business created: the resume path is cleared: ok")
    b.close()
