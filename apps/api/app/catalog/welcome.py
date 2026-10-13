"""The welcome email a business owner gets right after signing up: the plan, the trial, the
business's join code, the first steps and the links they need. Text from app/messages
(email.welcome); the HTML is a simple, email-client-safe layout (tables, inline styles)."""

from dataclasses import dataclass
from datetime import date

from app.commerce.modules import CORE_TIERS, quote
from app.messaging import email_layout as layout
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

    lang = locale if locale in ("he", "en") else "he"
    parts = [
        layout.title(subject, lang),
        layout.paragraph(t["hello"], lang),
        layout.paragraph(_fill(t["intro"], business=details.business), lang),
        layout.subheading(t["planTitle"], lang),
        layout.rows(
            [(label, money(amount)) for label, amount in lines]
            + [(t["total"], money(priced.total))],
            lang,
        ),
        layout.paragraph(trial, lang, muted=True),
    ]
    if details.simulated:
        parts.append(layout.paragraph(t["simulated"], lang, muted=True))
    parts += [
        layout.subheading(t["joinTitle"], lang),
        layout.code_box(layout.e(details.join_code)),
        layout.paragraph(t["joinText"], lang, muted=True),
        layout.subheading(t["stepsTitle"], lang),
        layout.steps(list(t["steps"]), lang),
        "".join(layout.button(label, url, primary=i == 0) for i, (label, url) in enumerate(links)),
        layout.paragraph(_fill(t["help"], contact=contact), lang, muted=True),
        layout.text_block(t["signature"], lang),
    ]
    body = layout.shell(
        [layout.Section(lang, "".join(parts))],
        subject=subject,
        preheader=t["preheader"],
        brand=layout.BRAND,
        footer=[(lang, layout.BRAND)],
    )
    return Email(to=details.to, subject=subject, text=text, html=body)
