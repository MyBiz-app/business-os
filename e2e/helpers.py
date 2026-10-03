"""Shared helpers for the end-to-end scripts (local stack only)."""

import glob
import json
import re
import time
import urllib.request

BASE = "http://localhost:3000"  # web
APP = "http://localhost:8081"  # mobile app on Expo web
MAILBOX = "http://127.0.0.1:54324/api/v1"  # Mailpit from `supabase start`
DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
PASSWORD = "Str0ng!Passw0rd"
OUT = "e2e/screenshots"


def chromium() -> str | None:
    """The sandbox's pre-installed Chromium, if any (otherwise Playwright's own)."""
    found = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    return found[0] if found else None


def ready(page) -> None:
    page.wait_for_load_state("networkidle")


def _message(email: str) -> dict:
    for _ in range(40):
        messages = json.load(urllib.request.urlopen(f"{MAILBOX}/messages"))["messages"]
        mine = [m for m in messages if any(t["Address"] == email for t in m["To"])]
        if mine:
            return json.load(urllib.request.urlopen(f"{MAILBOX}/message/{mine[0]['ID']}"))
        time.sleep(0.5)
    raise SystemExit(f"no email for {email}")


def confirm_link(email: str) -> str:
    html = _message(email)["HTML"]
    link = re.search(r'href="([^"]+(?:/auth/confirm|/verify)[^"]+)"', html)
    return link.group(1).replace("&amp;", "&")


def otp(email: str) -> str:
    return re.search(r"\b(\d{6})\b", _message(email)["Text"]).group(1)


def login(page, email: str) -> None:
    page.goto(f"{BASE}/login")
    ready(page)
    page.locator("input[type=email]").fill(email)
    page.locator("input[type=password]").fill(PASSWORD)
    page.locator("form button[type=submit]").click()
    page.wait_for_url("**/dashboard**")
