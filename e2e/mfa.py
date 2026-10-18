"""Two-step sign-in: the owner turns on an authenticator app on the account page, signs out, and
signs in again with the password and a code (go-live GL1). Run it like `privacy.py`."""

import base64
import hashlib
import hmac
import pathlib
import struct
import time

from playwright.sync_api import expect, sync_playwright

import helpers as h

pathlib.Path(h.OUT).mkdir(parents=True, exist_ok=True)
email = f"owner{time.time_ns()}@example.com"


def totp(secret: str, at: float | None = None) -> str:
    """The 6-digit code an authenticator app shows (RFC 6238: SHA-1, 30 seconds)."""
    key = base64.b32decode(secret.replace(" ", "").upper() + "=" * (-len(secret.replace(" ", "")) % 8))
    counter = struct.pack(">Q", int((time.time() if at is None else at) // 30))
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def next_window() -> None:
    """A code is good once; wait for the next 30-second window before using a fresh one."""
    time.sleep(30 - time.time() % 30 + 1)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    page = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    page.goto(f"{h.BASE}/signup"); h.ready(page)
    page.get_by_label("אימייל").fill(email)
    page.get_by_label("סיסמה", exact=True).fill(h.PASSWORD)
    page.get_by_role("button", name="יצירת חשבון").click()
    page.wait_for_url("**/check-email**")
    page.goto(h.confirm_link(email)); h.to_onboarding(page)
    page.get_by_label("שם העסק").fill("סטודיו אימות")
    page.get_by_role("button", name="המשך").click()
    page.get_by_role("button", name="יצירת העסק").click()
    page.wait_for_url("**/dashboard")

    page.goto(f"{h.BASE}/account"); h.ready(page)
    page.get_by_role("button", name="הפעלה", exact=True).click()
    secret = page.locator("code").first.inner_text().strip()
    assert len(secret) >= 16, secret
    page.get_by_label("קוד בן 6 ספרות").fill(totp(secret))
    page.get_by_role("button", name="אישור והפעלה").click()
    expect(page.get_by_text("האימות הדו-שלבי פעיל.")).to_be_visible()
    print("1. authenticator enrolled with a generated code: ok")

    # A new browser: the password alone no longer opens the app, a wrong code is refused.
    other = b.new_context(locale="he-IL", viewport={"width": 1280, "height": 900}).new_page()
    other.goto(f"{h.BASE}/login"); h.ready(other)
    other.locator("input[type=email]").fill(email)
    other.locator("input[type=password]").fill(h.PASSWORD)
    other.locator("form button[type=submit]").click()
    other.wait_for_url("**/login/mfa**"); h.ready(other)
    other.get_by_label("קוד בן 6 ספרות").fill("000000")
    other.get_by_role("button", name="אימות").click()
    expect(other.get_by_role("alert")).to_be_visible()
    next_window()
    other.get_by_label("קוד בן 6 ספרות").fill(totp(secret))
    other.get_by_role("button", name="אימות").click()
    other.wait_for_url("**/dashboard**")
    print("2. password then code signs in, a wrong code is refused: ok")
    b.close()
