"""The welcome email a business owner gets right after signing up: the plan, the trial, the
business's join code, the first steps and the links they need. Text from app/messages
(email.welcome); the HTML is a simple, email-client-safe layout (tables, inline styles)."""

import html
from dataclasses import dataclass
from datetime import date

from app.commerce.modules import CORE_TIERS, quote
from app.messaging.email import Email, load_all_messages


@dataclass(frozen=True)
class WelcomeDetails:
    to: str
    business: str
    locale: str
    currency: str
    join_code: str
    trial_ends_on: date
    modules: dict[str, int]
    expected_active_clients: int
    web_url: str
    client_app_url: str
    simulated: bool


def _fill(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def _money(amount: int, currency: str, locale: str) -> str:
    symbol = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(currency, currency + " ")
    number = f"{amount / 100:,.2f}".rstrip("0").rstrip(".")
    return f"{number} {symbol}" if locale == "he" else f"{symbol}{number}"


def _day(value: date, locale: str) -> str:
    return value.strftime("%d/%m/%Y") if locale == "he" else value.strftime("%b %d, %Y")


def build_welcome(details: WelcomeDetails) -> Email:
    locale = details.locale if details.locale in ("he", "en") else "en"
    messages = load_all_messages(locale)
    t = messages["email"]["welcome"]
    names = messages["modules"]["names"]
    priced = quote(details.modules, details.expected_active_clients, details.currency)
    money = lambda amount: _money(amount, details.currency, locale)  # noqa: E731
    tier = next(
        (
            limit
            for limit, _ in CORE_TIERS
            if limit is None or details.expected_active_clients <= limit
        ),
        None,
    )
    core_label = _fill(t["core"], count=f"{tier:,}") if tier is not None else t["coreCustom"]
    lines = [(core_label, priced.core)] + [
        (
            names.get(key, key)
            + (f" × {details.modules[key]}" if details.modules[key] > 1 else ""),
            amount,
        )
        for key, amount in priced.lines.items()
    ]
    trial = _fill(t["trial"], date=_day(details.trial_ends_on, locale))
    contact = f"{details.web_url}/contact"
    links = [
        (t["openApp"], f"{details.web_url}/dashboard"),
        (t["guide"], f"{details.web_url}/getting-started"),
        (t["clientApp"], f"{details.client_app_url}/join?code={details.join_code}"),
    ]
    subject = _fill(t["subject"], business=details.business)

    text = "\n".join(
        [
            t["hello"],
            "",
            _fill(t["intro"], business=details.business),
            "",
            f"{t['planTitle']}:",
            *[f"- {label}: {money(amount)}" for label, amount in lines],
            f"{t['total']}: {money(priced.total)}",
            trial,
            *([t["simulated"]] if details.simulated else []),
            "",
            f"{t['joinTitle']}: {details.join_code}",
            t["joinText"],
            "",
            f"{t['stepsTitle']}:",
            *[f"{i}. {step}" for i, step in enumerate(t["steps"], start=1)],
            "",
            *[f"{label}: {url}" for label, url in links],
            "",
            _fill(t["help"], contact=contact),
            "",
            t["signature"],
        ]
    )

    e = html.escape
    direction = "rtl" if locale == "he" else "ltr"
    align = "right" if locale == "he" else "left"
    far = "left" if locale == "he" else "right"
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #eceef5">{e(label)}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #eceef5;text-align:{far};'
        f'white-space:nowrap">{e(money(amount))}</td></tr>'
        for label, amount in lines
    )
    steps = "".join(f'<li style="margin:0 0 6px">{e(step)}</li>' for step in t["steps"])
    buttons = "".join(
        f'<a href="{e(url)}" style="display:inline-block;margin:4px;padding:12px 18px;'
        f"border-radius:12px;text-decoration:none;font-weight:700;"
        f'{"background:#4f46e5;color:#ffffff" if i == 0 else "background:#eef0ff;color:#3730a3"}">'
        f"{e(label)}</a>"
        for i, (label, url) in enumerate(links)
    )
    simulated = (
        f'<p style="margin:8px 0 0;font-size:13px;color:#92400e">{e(t["simulated"])}</p>'
        if details.simulated
        else ""
    )
    signature = "<br>".join(e(line) for line in t["signature"].split("\n"))
    body = f"""<!doctype html>
<html lang="{locale}" dir="{direction}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(subject)}</title></head>
<body style="margin:0;background:#f4f5fb;font-family:Arial,Helvetica,sans-serif;color:#18181b">
<span style="display:none;max-height:0;overflow:hidden">{e(t["preheader"])}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5fb">
<tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="max-width:560px;background:#ffffff;border-radius:20px;overflow:hidden;text-align:{align}" dir="{direction}">
<tr><td style="background:linear-gradient(135deg,#4f46e5,#c026d3);background-color:#4f46e5;padding:28px 28px 24px;color:#ffffff">
<div style="font-size:15px;font-weight:700;opacity:.9">MyBiz</div>
<div style="font-size:26px;font-weight:800;margin-top:8px">{e(subject)}</div>
</td></tr>
<tr><td style="padding:24px 28px;font-size:15px;line-height:1.6">
<p style="margin:0 0 12px">{e(t["hello"])}</p>
<p style="margin:0 0 20px">{e(_fill(t["intro"], business=details.business))}</p>
<h2 style="font-size:17px;margin:0 0 8px">{e(t["planTitle"])}</h2>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{rows}
<tr><td style="padding:10px 0;font-weight:800">{e(t["total"])}</td>
<td style="padding:10px 0;font-weight:800;text-align:{far};white-space:nowrap">{e(money(priced.total))}</td></tr>
</table>
<p style="margin:8px 0 0;font-size:14px;color:#52525b">{e(trial)}</p>{simulated}
<div style="margin:22px 0;padding:16px;border-radius:14px;background:#f4f5fb;text-align:center">
<div style="font-size:13px;color:#52525b">{e(t["joinTitle"])}</div>
<div style="font-size:30px;font-weight:800;letter-spacing:6px;direction:ltr">{e(details.join_code)}</div>
<div style="font-size:13px;color:#52525b">{e(t["joinText"])}</div>
</div>
<h2 style="font-size:17px;margin:0 0 8px">{e(t["stepsTitle"])}</h2>
<ol style="margin:0 0 20px;padding-{align}:20px">{steps}</ol>
<div style="text-align:center;margin:8px 0 20px">{buttons}</div>
<p style="margin:0 0 16px;font-size:14px;color:#52525b">{e(_fill(t["help"], contact=contact))}</p>
<p style="margin:0">{signature}</p>
</td></tr></table></td></tr></table></body></html>"""
    return Email(to=details.to, subject=subject, text=text, html=body)
