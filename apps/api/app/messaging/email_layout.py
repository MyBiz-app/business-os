# ruff: noqa: E501  (HTML strings)
"""The MyBiz email look: one HTML shell for every email the product sends.

Used by the API (client notifications, staff rosters, the welcome email) and by
supabase/templates/build.py (sign-in, verification and password emails, which Supabase sends).
Table layout and inline CSS so Gmail, Outlook and phone clients render it the same; a small
`prefers-color-scheme` block adds a dark version where the client supports it, and the inline
colors stay readable where it does not. Palette and fonts follow docs/design-system.md."""

import html
import json
from dataclasses import dataclass
from pathlib import Path

NAVY = "#111827"
BLUE = "#2563EB"
PURPLE = "#7C3AED"
CYAN = "#06B6D4"
INK = "#111827"
MUTED = "#4B5563"
PAGE = "#F3F4F8"
LINE = "#E5E7EB"
TINT = "#EEF2FF"

# The name comes from brand.json next to core/brand.py (this file is also loaded on its own by
# supabase/templates/build.py, so it cannot import the app package).
BRAND = json.loads((Path(__file__).resolve().parents[1] / "core/brand.json").read_text("utf-8"))[
    "name"
]

FONT = "Assistant,'Plus Jakarta Sans','Segoe UI',Arial,Helvetica,sans-serif"

DARK_CSS = """
:root { color-scheme: light dark; supported-color-schemes: light dark; }
@media (prefers-color-scheme: dark) {
  .mb-page { background:#0B1020 !important; }
  .mb-card { background:#161B2E !important; }
  .mb-ink { color:#F3F4F6 !important; }
  .mb-muted { color:#AEB6C7 !important; }
  .mb-box { background:#1F2742 !important; border-color:#2E3860 !important; }
  .mb-code { color:#FFFFFF !important; }
  .mb-rule { border-color:#2E3860 !important; }
  .mb-link { color:#93B4FF !important; }
}
"""


# The big icon at the top of each kind of email (notification kind, welcome, auth emails).
ICONS = {
    "default": "✉️",
    "welcome": "🎉",
    "confirmation": "👋",
    "magic_link": "🔑",
    "reauthentication": "🛡️",
    "recovery": "🔒",
    "invite": "💌",
    "email_change": "📧",
    "email_changed_notification": "📧",
    "password_changed_notification": "🔒",
    "booked_by_studio": "✅",
    "waitlist_promoted": "🎟️",
    "waitlisted_by_studio": "⏳",
    "booking_cancelled_by_studio": "❌",
    "session_cancelled": "❌",
    "session_moved": "🔄",
    "session_reminder": "⏰",
    "health_approved": "✅",
    "health_rejected": "📋",
    "plan_ending": "💳",
    "friend_request": "🤝",
    "class_invite": "💌",
    "freeze_approved": "❄️",
    "freeze_rejected": "📋",
    "roster": "📅",
    "broadcast": "📣",
}


@dataclass(frozen=True)
class Section:
    """One language of an email: `lang` is "he" or "en"; `body` is trusted HTML (see the helpers)."""

    lang: str
    body: str


def e(value: str) -> str:
    return html.escape(value, quote=True)


def _dir(lang: str) -> tuple[str, str]:
    return ("rtl", "right") if lang == "he" else ("ltr", "left")


def title(text: str, lang: str) -> str:
    _, align = _dir(lang)
    return (
        f'<h1 class="mb-ink" style="margin:0 0 12px;font-size:24px;line-height:1.3;'
        f'font-weight:800;color:{INK};text-align:{align}">{e(text)}</h1>'
    )


def paragraph(text: str, lang: str, *, muted: bool = False) -> str:
    _, align = _dir(lang)
    color, cls = (MUTED, "mb-muted") if muted else (INK, "mb-ink")
    size = "14px" if muted else "16px"
    return (
        f'<p class="{cls}" style="margin:0 0 16px;font-size:{size};line-height:1.65;'
        f'color:{color};text-align:{align}">{e(text)}</p>'
    )


def text_block(text: str, lang: str, *, muted: bool = False) -> str:
    """Plain text with line breaks kept (the body of a text-first email)."""
    _, align = _dir(lang)
    color, cls = (MUTED, "mb-muted") if muted else (INK, "mb-ink")
    return (
        f'<p class="{cls}" style="margin:0 0 16px;font-size:{"14px" if muted else "16px"};line-height:1.65;'
        f'color:{color};text-align:{align}">{"<br>".join(e(line) for line in text.split(chr(10)))}</p>'
    )


def steps(items: list[str], lang: str) -> str:
    _, align = _dir(lang)
    pad = "padding-right" if lang == "he" else "padding-left"
    body = "".join(f'<li style="margin:0 0 6px">{e(item)}</li>' for item in items)
    return (
        f'<ol class="mb-ink" style="margin:0 0 20px;{pad}:22px;font-size:15px;line-height:1.6;'
        f'color:{INK};text-align:{align}">{body}</ol>'
    )


def subheading(text: str, lang: str) -> str:
    _, align = _dir(lang)
    return (
        f'<h2 class="mb-ink" style="margin:20px 0 8px;font-size:17px;font-weight:800;'
        f'color:{INK};text-align:{align}">{e(text)}</h2>'
    )


def code_box(code: str) -> str:
    """The one-time code, big and easy to copy; always left-to-right, also inside Hebrew text."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 20px">'
        f'<tr><td class="mb-box" align="center" style="background:{TINT};border:1px solid #C7D2FE;'
        f'border-radius:14px;padding:18px 12px">'
        f'<div class="mb-code" dir="ltr" style="font-family:Consolas,\'Courier New\',monospace;'
        f'font-size:34px;line-height:1.2;font-weight:800;letter-spacing:8px;color:{NAVY}">'
        f"{code}</div></td></tr></table>"
    )


def button(label: str, url: str, *, primary: bool = True) -> str:
    """A bulletproof button: a padded table cell, so it keeps its shape in Outlook."""
    bg, fg = (BLUE, "#FFFFFF") if primary else (TINT, "#3730A3")
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:8px auto 20px">'
        f'<tr><td align="center" bgcolor="{bg}" style="border-radius:12px;background:{bg}">'
        f'<a href="{e(url)}" style="display:inline-block;padding:14px 28px;'
        f"font-size:16px;font-weight:700;color:{fg};text-decoration:none;border-radius:12px;"
        f'font-family:{FONT}">{e(label)}</a></td></tr></table>'
    )


def link_fallback(url: str, lang: str) -> str:
    """The raw link under a button, for clients that do not show buttons."""
    return (
        f'<p class="mb-muted" dir="ltr" style="margin:0 0 16px;font-size:12px;line-height:1.5;'
        f'color:{MUTED};word-break:break-all;overflow-wrap:anywhere;text-align:center"><a class="mb-link" href="{e(url)}" '
        f'style="color:{BLUE}">{e(url)}</a></p>'
    )


def rows(items: list[tuple[str, str]], lang: str) -> str:
    """Label/value lines (a price list, a roster); values are escaped."""
    _, align = _dir(lang)
    far = "left" if lang == "he" else "right"
    body = "".join(
        f'<tr><td class="mb-ink mb-rule" style="padding:9px 0;border-bottom:1px solid {LINE};'
        f'font-size:15px;color:{INK};text-align:{align}">{e(label)}</td>'
        f'<td class="mb-ink mb-rule" style="padding:9px 0;border-bottom:1px solid {LINE};'
        f'font-size:15px;font-weight:700;color:{INK};text-align:{far};white-space:nowrap">{e(value)}</td></tr>'
        for label, value in items
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 16px">{body}</table>'
    )


def hero(kind: str | None) -> str:
    """A big round icon for the kind of email, centered above the text."""
    icon = ICONS.get(kind or "", ICONS["default"])
    return (
        '<table role="presentation" align="center" cellpadding="0" cellspacing="0" style="margin:0 auto 18px"><tr>'
        f'<td width="72" height="72" align="center" bgcolor="{TINT}" class="mb-box" style="width:72px;height:72px;'
        f'border-radius:36px;background:{TINT};font-size:36px;line-height:72px">{icon}</td></tr></table>'
    )


def detail_card(items: list[tuple[str, str]], lang: str) -> str:
    """A tinted card of label/value lines (date, time, place, amount)."""
    _, align = _dir(lang)
    far = "left" if lang == "he" else "right"
    body = "".join(
        f'<tr><td class="mb-muted" style="padding:6px 0;font-size:14px;color:{MUTED};text-align:{align}">{e(label)}</td>'
        f'<td class="mb-ink" style="padding:6px 0;font-size:15px;font-weight:700;color:{INK};text-align:{far}">{e(value)}</td></tr>'
        for label, value in items
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px">'
        f'<tr><td class="mb-box" style="background:{TINT};border:1px solid #C7D2FE;border-radius:14px;padding:12px 18px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{body}</table></td></tr></table>'
    )


def _section(section: Section, first: bool) -> str:
    direction, align = _dir(section.lang)
    divider = (
        ""
        if first
        else f'<div class="mb-rule" style="border-top:1px solid {LINE};margin:28px 0 24px"></div>'
    )
    return (
        f'{divider}<div lang="{section.lang}" dir="{direction}" style="text-align:{align}">'
        f"{section.body}</div>"
    )


def shell(
    sections: list[Section],
    *,
    subject: str,
    preheader: str,
    brand: str,
    footer: list[tuple[str, str]],
    kind: str | None = None,
) -> str:
    """The whole document. `footer` is one (lang, text) line per language."""
    lang = sections[0].lang
    direction, _ = _dir(lang)
    content = hero(kind) + "".join(_section(s, i == 0) for i, s in enumerate(sections))
    foot = "".join(
        f'<div lang="{fl}" dir="{_dir(fl)[0]}" class="mb-muted" style="margin:0 0 4px;font-size:12px;'
        f'line-height:1.5;color:{MUTED};text-align:center">{e(text)}</div>'
        for fl, text in footer
    )
    return f"""<!doctype html>
<html lang="{lang}" dir="{direction}" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{e(subject)}</title>
<style>{DARK_CSS}</style>
</head>
<body class="mb-page" style="margin:0;padding:0;background:{PAGE};font-family:{FONT}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAGE}">{e(preheader)}&#8199;&#847;&#8199;&#847;&#8199;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="mb-page" style="background:{PAGE}">
<tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="mb-card" style="max-width:560px;table-layout:fixed;background:#FFFFFF;border-radius:20px;overflow:hidden">
<tr><td bgcolor="{BLUE}" style="background:{BLUE};background-image:linear-gradient(135deg,{PURPLE},{BLUE},{CYAN});padding:26px 28px" dir="ltr">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td width="44" height="44" align="center" bgcolor="#FFFFFF" style="width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,0.22);font-size:24px;font-weight:800;color:#FFFFFF;font-family:{FONT}">M</td>
<td style="padding-left:12px;font-size:22px;font-weight:800;color:#FFFFFF;font-family:{FONT}">{e(brand)}</td>
</tr></table></td></tr>
<tr><td style="padding:32px 24px 28px;word-wrap:break-word;overflow-wrap:anywhere">{content}</td></tr>
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px"><tr><td style="padding:18px 12px 0">{foot}</td></tr></table>
</td></tr></table>
</body></html>"""
