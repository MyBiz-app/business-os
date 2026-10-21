"""Where a page starts after a click: the landing site and the business app. A new page begins at the
top, a link to a section lands it just below the sticky header, back returns to where you were, the
side menu marker follows the page, and a window over a page leaves the page where it is.
Usage: python e2e/navigation.py <owner email with data> [--landing-only]"""

import sys

from playwright.sync_api import sync_playwright

import helpers as h

email = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
landing_only = "--landing-only" in sys.argv
failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def settle(page, ms: int = 1500) -> None:
    """Long enough for a page change, its fade and a smooth scroll to finish."""
    page.wait_for_timeout(ms)


def y(page) -> int:
    return page.evaluate("Math.round(window.scrollY)")


def header_bottom(page) -> int:
    return page.evaluate(
        "Math.max(0, ...[...document.querySelectorAll('header')].filter(e => getComputedStyle(e).position === 'sticky')"
        ".map(e => e.getBoundingClientRect().bottom))"
    )


def to_bottom(page) -> None:
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(300)


def lands_at_top(page, click, what: str) -> None:
    """Scrolled to the end of the page, `click` opens another page: it must start at the top, in one move."""
    to_bottom(page)
    before = page.url
    # Count how often the scroll position changes after the click: one jump is a swap, two is the page
    # landing in the middle and then correcting (the old behaviour).
    page.evaluate(
        "window.__moves = []; window.__last = window.scrollY;"
        "window.addEventListener('scroll', () => { window.__moves.push(Math.round(window.scrollY)); });"
    )
    click()
    settle(page)
    moved = page.url != before
    moves = page.evaluate("window.__moves")
    jumps = [m for m in moves if m != 0]
    check(moved and y(page) == 0, f"{what}: starts at the top (now {y(page)})")
    check(len(jumps) <= 1, f"{what}: lands in one move, not two (positions seen: {moves[:6]})")


def landing(page) -> None:
    page.goto(h.BASE + "/")
    h.ready(page)
    hrefs = ["/features", "/pricing", "/about", "/contact", "/industries/fitness", "/legal/terms"]
    for href in hrefs:
        page.goto(h.BASE + "/")
        h.ready(page)
        lands_at_top(page, lambda href=href: page.locator(f"footer a[href='{href}']").first.click(), f"landing footer link {href}")
    # Back returns to where the home page was.
    page.goto(h.BASE + "/")
    h.ready(page)
    page.evaluate("window.scrollTo(0, 1400)")
    page.wait_for_timeout(300)
    # A link of the sticky header, so the page is not scrolled again to reach it.
    link = page.locator("header a[href='/features']:visible")
    if link.count() == 0:  # the phone's header folds its links into a menu
        return
    link.first.click()
    settle(page)
    page.go_back()
    settle(page)
    check(abs(y(page) - 1400) < 60, f"landing: back returns to where the home page was (now {y(page)})")


def crm(page) -> None:
    page.goto(h.BASE + "/dashboard")
    h.ready(page)
    # Every item of the side menu starts its page at the top, from the end of a long page.
    links = page.evaluate(
        "[...document.querySelectorAll('aside > nav > ul > li > div > a[href], aside nav > ul > li > div > a[href]')]"
        ".map(a => a.getAttribute('href')).filter(href => href && !href.includes('#'))"
    )
    check(len(links) >= 5, f"side menu has items ({len(links)})")
    for href in dict.fromkeys(links):
        page.goto(h.BASE + "/dashboard")
        h.ready(page)
        lands_at_top(page, lambda href=href: page.locator(f"aside a[href='{href}']").first.click(), f"side menu {href}")
        h.skip_tour(page)

    # The team's tabs are pages of their own: each starts at the top.
    page.goto(h.BASE + "/team")
    h.ready(page)
    tabs = page.evaluate("[...document.querySelectorAll('main nav[aria-label] a[href^=\"/team\"]')].map(a => a.getAttribute('href'))")
    for href in dict.fromkeys(tabs):
        page.goto(h.BASE + "/team")
        h.ready(page)
        lands_at_top(page, lambda href=href: page.locator(f"main nav a[href='{href}']").first.click(), f"team tab {href}")

    # A link to a section of another page lands it just below the sticky header.
    for path, anchor in (("/ai", "ai-tasks"), ("/settings/business", "readiness-heading")):
        page.goto(h.BASE + "/dashboard")
        h.ready(page)
        page.evaluate("window.scrollTo(0, 300)")
        page.evaluate(
            "([path, anchor]) => { const a = document.createElement('a'); a.href = `${path}#${anchor}`; a.id = 'e2e-anchor';"
            " a.textContent = 'go'; a.style.cssText = 'position:fixed;top:120px;left:20px;z-index:9999'; document.body.appendChild(a); }",
            [path, anchor],
        )
        page.locator("#e2e-anchor").click()
        settle(page, 2500)
        h.skip_tour(page)
        top = page.evaluate(f"document.getElementById('{anchor}')?.getBoundingClientRect().top ?? null")
        below = header_bottom(page)
        check(top is not None and below <= top <= below + 120, f"{path}#{anchor}: section sits just below the header (top {top}, header {below})")

    # The settings menu lists the sections of the open topic and follows the page as it scrolls.
    page.goto(h.BASE + "/settings/business")
    h.ready(page)
    nested = page.locator(".section-nav a[href^='#']")
    check(nested.count() >= 2, f"settings topic lists its sections in the inner menu ({nested.count()})")
    if nested.count() >= 2:
        first = page.evaluate("document.querySelector('.section-nav [data-pill]:last-of-type')?.textContent ?? ''")
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        settle(page, 800)
        last = page.evaluate("[...document.querySelectorAll('.section-nav [data-pill]')].pop()?.textContent ?? ''")
        check(first != last, f"settings menu marker moved with the scroll ({first!r} -> {last!r})")

    # A window over a page leaves the page where it is.
    page.goto(h.BASE + "/clients")
    h.ready(page)
    page.evaluate("window.scrollTo(0, 400)")
    page.wait_for_timeout(300)
    before = y(page)
    page.locator("main a[href^='/clients/']:not([href*='new']):not([href*='import']):not([href*='join'])").first.click()
    settle(page)
    if page.locator("dialog[open]").count():
        check(abs(y(page) - before) < 5, f"a window over the client list keeps the list in place ({before} -> {y(page)})")
        page.keyboard.press("Escape")
        settle(page)
        check(abs(y(page) - before) < 5, f"closing it leaves the list in place ({before} -> {y(page)})")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=h.chromium())
    for name, locale, scheme, viewport in (
        ("en-desktop", "en-US", "light", {"width": 1280, "height": 800}),
        ("he-phone", "he-IL", "light", {"width": 390, "height": 800}),
    ):
        print(f"-- {name}")
        page = b.new_context(locale=locale, color_scheme=scheme, viewport=viewport).new_page()
        landing(page)
        if not landing_only and email:
            h.login(page, email)
            crm(page)

if failures:
    print(f"\n{len(failures)} failed")
    sys.exit(1)
print("\nall ok")
