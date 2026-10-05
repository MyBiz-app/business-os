"""Visits every page of the business app as the demo owner, on a phone and a wide screen, in
Hebrew (light) and English (dark): screenshots, serious accessibility issues, console errors
and horizontal overflow. Usage: python e2e/crawl.py <owner email>"""

import json
import pathlib
import sys

import psycopg
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

import helpers as h

OUT = pathlib.Path(h.OUT) / "crawl"
OUT.mkdir(parents=True, exist_ok=True)
email = sys.argv[1]

with psycopg.connect(h.DATABASE_URL) as conn:
    tenant = conn.execute(
        """SELECT m.tenant_id, m.user_id FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
           WHERE u.email = %s AND m.role = 'owner' LIMIT 1""",
        (email,),
    ).fetchone()
    tid = tenant[0]

    def first(sql: str) -> str | None:
        row = conn.execute(sql, {"t": tid}).fetchone()
        return str(row[0]) if row else None

    ids = {
        "client": first("SELECT id FROM app.clients WHERE tenant_id = %(t)s ORDER BY created_at LIMIT 1"),
        "lead": first("SELECT id FROM app.leads WHERE tenant_id = %(t)s LIMIT 1"),
        "location": first("SELECT id FROM app.locations WHERE tenant_id = %(t)s LIMIT 1"),
        "plan": first("SELECT id FROM app.plans WHERE tenant_id = %(t)s LIMIT 1"),
        "receipt": first("SELECT id FROM app.receipts WHERE tenant_id = %(t)s LIMIT 1"),
        "session": first("SELECT id FROM app.sessions WHERE tenant_id = %(t)s AND starts_at > now() ORDER BY starts_at LIMIT 1"),
        "service": first("SELECT id FROM app.services WHERE tenant_id = %(t)s LIMIT 1"),
        "invoice": first("SELECT id FROM app.platform_invoices WHERE tenant_id = %(t)s LIMIT 1"),
        "member": first("SELECT user_id FROM app.tenant_members WHERE tenant_id = %(t)s AND role <> 'owner' LIMIT 1"),
    }

pages = [
    "/dashboard", "/reports", "/assistant", "/schedule", "/schedule/new", "/schedule/appointment",
    "/schedule/closed", "/clients", "/clients/new", "/clients/import", "/clients/join", "/leads",
    "/leads/new", "/messages", "/services", "/services/new", "/plans", "/plans/new", "/locations",
    "/locations/new", "/team", "/team/roles", "/settings", "/settings/modules", "/settings/billing",
]  # fmt: skip
detail = {
    "client": "/clients/{}", "lead": "/leads/{}", "location": "/locations/{}", "plan": "/plans/{}",
    "receipt": "/receipts/{}", "session": "/schedule/{}", "service": "/services/{}",
    "invoice": "/settings/billing/invoices/{}", "member": "/team/{}/hours",
}  # fmt: skip
pages += [path.format(ids[key]) for key, path in detail.items() if ids[key]]

report: dict[str, dict] = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    for name, locale, scheme, viewport in (
        ("he-desktop", "he-IL", "light", {"width": 1280, "height": 900}),
        ("he-phone", "he-IL", "light", {"width": 390, "height": 844}),
        ("en-desktop", "en-US", "dark", {"width": 1280, "height": 900}),
        ("en-phone", "en-US", "dark", {"width": 390, "height": 844}),
    ):
        page = b.new_context(locale=locale, color_scheme=scheme, viewport=viewport).new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        h.login(page, email)
        if locale == "en-US":
            page.locator("header select").first.select_option("en"); page.wait_for_timeout(1500)
        for path in pages:
            errors.clear()
            response = page.goto(h.BASE + path)
            h.ready(page)
            slug = path.strip("/").replace("/", "_")[:60] or "home"
            page.screenshot(path=str(OUT / f"{name}-{slug}.png"), full_page=True)
            issues = [
                f"{v['id']}({len(v['nodes'])}): {v['nodes'][0]['target']}"
                for v in Axe().run(page).response["violations"]
                if v["impact"] in ("serious", "critical")
            ]
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            found = {
                "status": response.status if response else None,
                "url": page.url.replace(h.BASE, ""),
                "a11y": issues,
                "errors": errors[:3],
                "overflow": overflow,
            }
            if issues or errors or overflow or (response and response.status >= 400) or found["url"] != path:
                report[f"{name} {path}"] = found
        print(name, "done")

print(json.dumps(report, ensure_ascii=False, indent=1))
