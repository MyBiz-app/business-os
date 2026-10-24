"""Scripted user sweep of a LIVE site (read-only): visits routes, follows internal links, and records
console errors, failed requests, 4xx/5xx, horizontal overflow, empty pages, untranslated text,
serious accessibility issues and broken links, with a screenshot per page and variant.

Usage (public pages, no login):
    python e2e/sweep_live.py --base https://business-os-alpha-drab.vercel.app --out out/web --kind web
    python e2e/sweep_live.py --base https://mybiz-client-app.vercel.app --out out/app --kind app
Logged-in screens: pass --state <playwright storage-state.json> (made by the person who owns the account;
the password never goes through this script) and --routes <file with one path per line>.
It never clicks anything that writes data: only links and non-submitting navigation."""

import argparse
import json
import pathlib
import re
import sys
from urllib.parse import urldefrag, urlparse

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

WEB_PUBLIC = [
    "/", "/features", "/ai-team", "/industries", "/pricing", "/about", "/contact", "/getting-started",
    "/websites", "/start", "/legal/terms", "/legal/privacy", "/legal/accessibility", "/login", "/signup",
    "/forgot-password", "/join", "/no-such-page-404",
]  # fmt: skip
APP_PUBLIC = ["/", "/sign-in", "/no-such-page-404"]
VARIANTS = [
    ("he-light-1440", "he-IL", "light", 1440, 900),
    ("he-dark-390", "he-IL", "dark", 390, 844),
    ("en-light-1440", "en-US", "light", 1440, 900),
    ("en-dark-390", "en-US", "dark", 390, 844),
]
HEBREW = re.compile(r"[֐-׿]")
SKIP_LINK = re.compile(r"^(mailto:|tel:|javascript:|sms:|whatsapp:)|/logout|/sign-out|/delete|/cancel", re.I)

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--kind", choices=["web", "app"], default="web")
ap.add_argument("--state")
ap.add_argument("--routes")
ap.add_argument("--max-pages", type=int, default=60)
ap.add_argument("--no-axe", action="store_true")
args = ap.parse_args()
base = args.base.rstrip("/")
out = pathlib.Path(args.out)
(out / "shots").mkdir(parents=True, exist_ok=True)
seeds = (
    [ln.strip() for ln in open(args.routes, encoding="utf-8") if ln.strip()]
    if args.routes
    else (WEB_PUBLIC if args.kind == "web" else APP_PUBLIC)
)
issues: list[dict] = []
visited: dict[str, dict] = {}
link_status: dict[str, int | str] = {}


def add(sev: str, variant: str, path: str, kind: str, detail: str) -> None:
    issues.append({"severity": sev, "variant": variant, "path": path, "kind": kind, "detail": detail[:400]})


def slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home"


def scan(page, ctx, variant: str, locale: str, path: str, queue: list[str], first: bool) -> None:
    errors: list[str] = []
    failed: list[str] = []
    bad: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on(
        "requestfailed",
        lambda r: None if "_rsc=" in r.url or "ERR_ABORTED" in str(r.failure) else failed.append(f"{r.method} {r.url[:120]} {r.failure}"),
    )
    page.on(
        "response",
        lambda r: bad.append(f"{r.status} {r.request.method} {r.url[:140]}") if r.status >= 400 else None,
    )
    try:
        resp = page.goto(base + path, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:  # noqa: BLE001
        add("high", variant, path, "navigation", str(e))
        return
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PWTimeout:
        pass
    page.wait_for_timeout(1200)
    status = resp.status if resp else 0
    expected404 = path.startswith("/no-such-page")
    if status >= 400 and not expected404:
        add("high", variant, path, "http-status", str(status))
    if expected404 and status != 404:
        add("medium", variant, path, "404-page", f"unknown URL returned {status} instead of 404")
    final = urlparse(page.url).path
    text = page.evaluate("document.body ? document.body.innerText : ''")
    if len(text.strip()) < 20 and not expected404:
        add("high", variant, path, "empty-page", f"almost no visible text (final url {final})")
    if final != path.split("?")[0] and first:
        visited.setdefault(path, {})["redirect"] = final
    if locale.startswith("en") and not args.state and HEBREW.search(text):  # logged-in screens show business data in Hebrew
        sample = next((ln for ln in text.splitlines() if HEBREW.search(ln)), "")
        add("medium", variant, path, "untranslated", f"Hebrew text in English UI: {sample[:100]}")
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    if overflow > 1:
        add("medium", variant, path, "overflow-x", f"{overflow}px horizontal overflow")
    broken_imgs = page.evaluate(
        "[...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src).map(i => i.src).slice(0,5)"
    )
    for src in broken_imgs:
        add("medium", variant, path, "broken-image", src)
    for e in errors[:5]:
        add("medium", variant, path, "console-error", e)
    for f in failed[:5]:
        add("low", variant, path, "request-failed", f)
    for b in bad[:6]:
        add("medium", variant, path, "http-4xx-5xx", b)
    if not args.no_axe and not expected404:
        try:
            for v in Axe().run(page).response["violations"]:
                if v["impact"] in ("serious", "critical"):
                    tgt = v["nodes"][0]["target"]
                    add("medium", variant, path, "a11y", f"{v['id']} ({v['impact']}, {len(v['nodes'])}x) {tgt}")
        except Exception as e:  # noqa: BLE001
            add("low", variant, path, "a11y-run", str(e)[:120])
    page.screenshot(path=str(out / "shots" / f"{variant}__{slug(path)}.jpg"), type="jpeg", quality=55, full_page=True)
    if first:
        hrefs = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href)")
        for h in hrefs:
            h, _ = urldefrag(h)
            if not h or SKIP_LINK.search(h):
                continue
            u = urlparse(h)
            if u.netloc == urlparse(base).netloc:
                p = u.path + (("?" + u.query) if u.query else "")
                if p not in queue and p not in seeds:
                    queue.append(p)
            elif h not in link_status:
                link_status[h] = "pending"


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    queue = list(seeds)
    seen: set[str] = set()
    # Pass 1 (Hebrew desktop light): discover pages by following links; the other variants reuse the list.
    pages_order: list[str] = []
    for vi, (variant, locale, scheme, w, hgt) in enumerate(VARIANTS):
        ctx = browser.new_context(
            locale=locale,
            color_scheme=scheme,
            viewport={"width": w, "height": hgt},
            has_touch=w < 600,
            storage_state=args.state,
            bypass_csp=True,
        )
        ctx.add_cookies([{"name": "NEXT_LOCALE", "value": locale[:2], "url": base}])
        page = ctx.new_page()
        if vi == 0:
            while queue and len(seen) < args.max_pages:
                path = queue.pop(0)
                if path in seen:
                    continue
                seen.add(path)
                pages_order.append(path)
                scan(page, ctx, variant, locale, path, queue, True)
                print(variant, path, flush=True)
        else:
            for path in pages_order:
                scan(page, ctx, variant, locale, path, queue, False)
                print(variant, path, flush=True)
        if vi == 0:
            for url in list(link_status):
                try:
                    r = ctx.request.get(url, timeout=20000, max_redirects=5)
                    link_status[url] = r.status
                    social = re.search(r"facebook|instagram|linkedin|twitter|x\.com|tiktok|wa\.me", url)
                    if r.status >= 400 and r.status not in (401, 403, 405, 429, 999) and not social:
                        add("medium", variant, "(external)", "broken-link", f"{r.status} {url}")
                except Exception as e:  # noqa: BLE001
                    link_status[url] = "error"
                    add("low", variant, "(external)", "link-error", f"{url} {str(e)[:80]}")
        ctx.close()
    browser.close()

(out / "issues.json").write_text(json.dumps({"base": base, "pages": pages_order, "links": link_status, "issues": issues}, ensure_ascii=False, indent=1), encoding="utf-8")
sev = {"high": 0, "medium": 0, "low": 0}
for i in issues:
    sev[i["severity"]] += 1
print("PAGES", len(pages_order), "ISSUES", sev)
sys.exit(0)
