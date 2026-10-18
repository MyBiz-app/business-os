"""Content-Security-Policy check in a real browser: the marketing pages, the sign-in pages and the
CRM (after creating a business) must load with the nonce-based policy and report no violations.
Usage: python e2e/csp.py [--public-only] (default: public pages, then a fresh owner through the CRM).
Against a production build set --public-only if no Supabase is running."""

import re
import sys
import time

from playwright.sync_api import sync_playwright

import helpers as h

PUBLIC = [
    "/", "/features", "/ai-team", "/pricing", "/websites", "/industries", "/industries/pilates", "/about", "/contact",
    "/start", "/getting-started", "/legal/privacy", "/legal/terms", "/login", "/signup", "/forgot-password",
]
CRM = [
    "/dashboard", "/schedule", "/clients", "/leads", "/catalog", "/catalog?tab=plans", "/team", "/reports",
    "/messages", "/content", "/settings", "/ai", "/quotes", "/receipts", "/documents", "/time",
]
# Every violation is also logged to the console. The checks below avoid page.evaluate on purpose:
# it runs through eval, which the strict policy refuses on a production build (dev servers allow it).
WATCH = """
document.addEventListener('securitypolicyviolation', e =>
  console.log(`CSPV ${e.effectiveDirective} blocked=${e.blockedURI} source=${e.sourceFile}:${e.lineNumber}`));
"""
problems: list[str] = []


def new_page(browser, **kw):
    context = browser.new_context(locale=kw.pop("locale", "he-IL"), viewport={"width": 1280, "height": 900}, **kw)
    context.add_init_script(WATCH)
    page = context.new_page()
    page.on("console", lambda m: ("Content Security Policy" in m.text or m.text.startswith("CSPV "))
            and problems.append(f"{page.url}: {m.text[:200]}"))
    return page


def visit(page, path: str, expect_policy: bool = True) -> None:
    response = page.goto(f"{h.BASE}{path}")
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)  # late-loading chunks and the hydration scripts
    policy = (response.headers.get("content-security-policy") or "") if response else ""
    if expect_policy and not re.search(r"script-src 'self' 'nonce-[^']+' 'strict-dynamic'", policy):
        problems.append(f"{path}: no enforced nonce policy ({policy[:80]!r})")
    if "unsafe-inline" in re.sub(r"style-src[^;]*", "", policy):
        problems.append(f"{path}: unsafe-inline outside style-src")
    print(f"ok {path}" if not problems else f"checked {path}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    for locale, scheme in (("he-IL", "light"), ("en-US", "dark")):
        page = new_page(b, locale=locale, color_scheme=scheme)
        for path in PUBLIC:
            visit(page, path)
        # The inline theme and palette scripts ran (they carry the nonce): html is already classed.
        assert re.search(r"\b(light|dark)\b", page.locator("html").get_attribute("class") or ""), "theme script did not run"
    # The report endpoint accepts a violation and the page stays unaffected.
    assert page.request.post(f"{h.BASE}/api/csp-report", data="{}").status == 204

    if "--public-only" not in sys.argv:
        owner = new_page(b)
        email = f"csp-{int(time.time())}@example.com"
        owner.goto(f"{h.BASE}/signup"); h.ready(owner)
        owner.get_by_label("אימייל").fill(email)
        owner.get_by_label("סיסמה", exact=True).fill(h.PASSWORD)
        owner.get_by_role("button", name="יצירת חשבון").click()
        owner.wait_for_url("**/check-email**")
        owner.goto(h.confirm_link(email)); h.to_onboarding(owner)
        owner.get_by_label("שם העסק").fill("סטודיו CSP")
        owner.get_by_label("סוג העסק").select_option("pilates")
        owner.get_by_role("button", name="המשך").click()
        owner.get_by_role("button", name="יצירת העסק").click()
        owner.wait_for_url("**/dashboard")
        for path in CRM:
            visit(owner, path)
    b.close()

if problems:
    print("CSP problems:")
    print("\n".join(sorted(set(problems))))
    sys.exit(1)
print("CSP check: ok")
