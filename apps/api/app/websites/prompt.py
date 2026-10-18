"""The ready-made prompt for Claude Code, built from a submitted order (spec 23.5).

The structure is fixed so every site starts from the same quality bar: goal, audience, sections,
branding, motion, copy, assets and the mandatory requirements. The business's own words are
copied as written."""

from typing import Any

GOALS = {
    "leads": "bring in inquiries",
    "bookings": "get bookings",
    "showcase": "present the business",
    "sell": "sell products or plans",
}
SECTIONS = {
    "hero": "Hero: the offer in one line and the main call to action",
    "services": "Services and prices (use the list under Business data)",
    "gallery": "Gallery",
    "team": "Team",
    "testimonials": "Testimonials",
    "faq": "Frequently asked questions",
    "location": "Location, map link and opening hours",
    "contact": "Contact",
    "booking": "Booking: the visitor books or joins a class directly through the platform",
    "whatsapp": "WhatsApp button",
}
STYLES = {
    "clean": "modern and clean",
    "luxury": "luxurious and restrained",
    "warm": "warm and family-friendly",
    "vibrant": "young and vibrant",
}
MOTION = {
    "none": "no animation",
    "subtle": "subtle: gentle fades and hover states",
    "rich": "rich: scroll animations and animated section transitions",
}
LANGUAGES = {"he": "Hebrew (right to left)", "en": "English (left to right)"}


def _line(label: str, value: object) -> str:
    return f"- {label}: {value}" if value else f"- {label}: not specified"


def build_prompt(
    *,
    brief: dict[str, Any],
    snapshot: dict[str, Any],
    tracking_key: str,
    api_url: str,
    with_system: bool,
) -> str:
    business = snapshot.get("business") or {}
    branches = snapshot.get("branches") or []
    services = snapshot.get("services") or []
    sections = brief.get("sections") or []
    goals = [GOALS.get(g, g) for g in brief.get("goals") or []]
    languages = [LANGUAGES.get(code, code) for code in brief.get("languages") or []]
    api = api_url.rstrip("/")
    code = business.get("join_code")

    out: list[str] = ["# Build a landing page", ""]
    out += [
        "You are building a single-page landing site for a small business. Follow this brief",
        "exactly. Where it says 'not specified', choose well and keep it simple.",
        "",
        "## Goal",
        _line("What the site is for", ", ".join(goals)),
        _line("The single most important action", brief.get("main_action")),
        "",
        "## Business data",
        _line("Name", business.get("name")),
        _line("Field", business.get("vertical")),
        _line("What makes it special (the owner's words)", brief.get("unique")),
        _line("Audience", brief.get("audience")),
        _line("Area", brief.get("area")),
    ]
    for branch in branches:
        out.append(
            f"- Branch: {branch.get('name')}"
            + (f", {branch['address']}" if branch.get("address") else "")
        )
    if "services" in sections and services:
        out += ["", "Services and prices:"]
        out += [
            f"- {s['name']}: {s['price']} {s['currency']}" if s.get("price") else f"- {s['name']}"
            for s in services
        ]
    out += ["", "## Sections, in this order"]
    out += [f"{i}. {SECTIONS.get(s, s)}" for i, s in enumerate(sections, 1)] or ["- not specified"]

    out += ["", "## Branding"]
    if brief.get("colors"):
        out.append(_line("Colors", ", ".join(brief["colors"])))
    elif brief.get("colors_from_brand", True):
        out.append(_line("Colors", f"the business's brand color {business.get('primary_color')}"))
    out += [
        _line("Style", STYLES.get(brief.get("style") or "", brief.get("style"))),
        _line("Font", brief.get("font")),
        "- Logo: "
        + (
            "the business has no logo; use a clean wordmark"
            if brief.get("no_logo")
            else "see assets"
        ),
        "",
        "## Motion",
        _line("Level", MOTION.get(brief.get("motion") or "", brief.get("motion"))),
        "",
        "## Copy",
        "- The owner writes the texts."
        if brief.get("copy_by") == "me"
        else "- Write all the texts yourself, in the business's voice, from the data above.",
        _line("Languages", ", ".join(languages)),
        "",
        "## Assets",
    ]
    images = brief.get("images") or []
    if images:
        out += [f"- Image {i}: {img.get('note') or 'no note'}" for i, img in enumerate(images, 1)]
        out.append("- The image files are in the ZIP delivered with this order.")
    if brief.get("no_good_photos"):
        out.append("- The business has no good photos: add suitable stock photos.")
    for site in brief.get("inspiration") or []:
        out.append(f"- Inspiration: {site['url']} (likes: {site.get('likes') or 'not specified'})")
    out += [
        "",
        "## Domain",
        _line(
            "Domain",
            {
                "have": brief.get("domain_name"),
                "buy": "to be bought for the business",
                "temporary": "a temporary subdomain",
            }.get(brief.get("domain") or ""),
        ),
        _line("Due date", brief.get("due_date")),
        "",
        "## Mandatory requirements",
        "- Accessibility to Israeli Standard 5568 (WCAG 2.0 AA at least), with an accessibility "
        "statement page.",
        "- Fast: optimized images, no render-blocking scripts, good Core Web Vitals.",
        "- Basic SEO: title, description, headings, Open Graph tags, sitemap, structured data "
        "for a local business.",
        "- Right to left support for Hebrew with logical CSS properties.",
    ]
    if code:
        out += [
            "- A contact form that posts to the platform: "
            f"POST {api}/public/businesses/{code}/inquiries "
            "with JSON {first_name, last_name?, email?, phone?, interest?} and an empty hidden "
            'field "website" (spam trap). It answers 202. The inquiry appears as a lead with '
            'the source "website".',
        ]
    if with_system and "booking" in sections:
        out.append(
            "- Booking links to the business's client page on the platform; do not rebuild booking."
        )
    out += [
        "- Visit counting, no cookies and nothing personal: on page load send "
        f"POST {api}/public/website-visits "
        f'with JSON {{"key": "{tracking_key}", "source": "direct|search|social|other"}} '
        "(source from the referrer: a search engine, a social network, or direct).",
        "",
    ]
    return "\n".join(out)
