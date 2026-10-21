"""Builds the auth email templates (the .html files next to this script) from one design.

    python supabase/templates/build.py          rewrite the files
    python supabase/templates/build.py --check  fail if a file is out of date (CI runs this)

Supabase sends these emails and cannot pick a language per user, so every email carries Hebrew
and English one above the other. The look comes from apps/api/app/messaging/email_layout.py,
the same shell the API's own emails use. {{ ... }} are Supabase template variables."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "email_layout", ROOT / "apps/api/app/messaging/email_layout.py"
)
layout = importlib.util.module_from_spec(spec)
sys.modules["email_layout"] = layout
spec.loader.exec_module(layout)

BRAND = json.loads((ROOT / "packages/i18n/brand.json").read_text("utf-8"))["name"]
WRITTEN = "MyBiz"  # the product name as the texts below spell it; build() swaps in BRAND
CONFIRM = "{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type="
CODE = "{{ .Token }}"

FOOTER = [
    ("he", f"{BRAND} · הודעה אוטומטית, אין צורך להשיב."),
    ("en", f"{BRAND} · Automated message, no need to reply."),
]


def sec(lang: str, heading: str, *parts: str) -> layout.Section:
    return layout.Section(lang, layout.title(heading, lang) + "".join(parts))


def p(text: str, lang: str, muted: bool = False) -> str:
    return layout.paragraph(text, lang, muted=muted)


def link_button(label: str, url: str) -> str:
    return layout.button(label, url) + layout.link_fallback(url, "en")


# name -> (subject, preheader, he parts, en parts); parts are (heading, [html...]).
def build() -> dict[str, tuple[str, str]]:
    ignore_he = "אם לא ביקשתם זאת, אפשר להתעלם מההודעה, שום דבר לא ישתנה."
    ignore_en = "If you didn't ask for this, you can ignore this email. Nothing will change."
    confirm_url = CONFIRM + "email"
    recovery_url = CONFIRM + "recovery&next=/reset-password"
    templates = {
        "confirmation": (
            "Confirm your email · אימות כתובת אימייל",
            "Your verification code · קוד האימות שלכם",
            sec(
                "he",
                "ברוכים הבאים ל-MyBiz",
                p("עוד רגע וסיימנו. בכניסה מהאפליקציה הקלידו את הקוד:", "he"),
                layout.code_box(CODE),
                p("באתר? לחצו כדי לאמת את הכתובת ולהשלים את ההרשמה:", "he"),
                link_button("אימות האימייל", confirm_url),
                p("הקוד והקישור תקפים לזמן מוגבל. " + ignore_he, "he", muted=True),
            ),
            sec(
                "en",
                "Welcome to MyBiz",
                p("Almost there. In the app, enter this code:", "en"),
                layout.code_box(CODE),
                p("On the website? Click to verify your address and finish signing up:", "en"),
                link_button("Verify my email", confirm_url),
                p("The code and the link expire after a while. " + ignore_en, "en", muted=True),
            ),
        ),
        "magic_link": (
            "Your sign-in code · קוד כניסה",
            "Your sign-in code · קוד הכניסה שלכם",
            sec(
                "he",
                "קוד הכניסה שלכם",
                p("הקלידו את הקוד כדי להיכנס ל-MyBiz:", "he"),
                layout.code_box(CODE),
                p(
                    "הקוד תקף לשעה אחת, לשימוש חד-פעמי. אל תשתפו אותו עם אף אחד. " + ignore_he,
                    "he",
                    muted=True,
                ),
            ),
            sec(
                "en",
                "Your sign-in code",
                p("Enter this code to sign in to MyBiz:", "en"),
                layout.code_box(CODE),
                p(
                    "The code is valid for one hour and works once. Never share it with anyone. "
                    + ignore_en,
                    "en",
                    muted=True,
                ),
            ),
        ),
        "recovery": (
            "Reset your password · איפוס סיסמה",
            "Choose a new password · בחירת סיסמה חדשה",
            sec(
                "he",
                "איפוס סיסמה",
                p("קיבלנו בקשה לאפס את הסיסמה שלכם. לחצו כדי לבחור סיסמה חדשה:", "he"),
                link_button("בחירת סיסמה חדשה", recovery_url),
                p(ignore_he + " הסיסמה הקיימת ממשיכה לעבוד.", "he", muted=True),
            ),
            sec(
                "en",
                "Reset your password",
                p("We got a request to reset your password. Click to choose a new one:", "en"),
                link_button("Choose a new password", recovery_url),
                p(ignore_en + " Your current password keeps working.", "en", muted=True),
            ),
        ),
        "invite": (
            "You've been invited · הוזמנתם ל-MyBiz",
            "Accept your invitation · קבלת ההזמנה",
            sec(
                "he",
                "הוזמנתם להצטרף ל-MyBiz",
                p("הוזמנתם להצטרף. לחצו כדי לקבל את ההזמנה וליצור את החשבון:", "he"),
                link_button("קבלת ההזמנה", CONFIRM + "invite"),
                p("לא הכרתם את ההזמנה? אפשר להתעלם מההודעה.", "he", muted=True),
            ),
            sec(
                "en",
                "You're invited to MyBiz",
                p("You've been invited to join. Click to accept and set up your account:", "en"),
                link_button("Accept invitation", CONFIRM + "invite"),
                p("Don't recognize this invitation? You can ignore this email.", "en", muted=True),
            ),
        ),
        "email_change": (
            "Confirm your new email · אימות כתובת חדשה",
            "Confirm the new address · אימות הכתובת החדשה",
            sec(
                "he",
                "אימות כתובת אימייל חדשה",
                p(
                    "ביקשתם לשנות את כתובת האימייל של החשבון ל-{{ .NewEmail }}. לחצו כדי לאשר:",
                    "he",
                ),
                link_button("אישור הכתובת החדשה", CONFIRM + "email_change"),
                p("לא ביקשתם? אל תלחצו, ושקלו להחליף סיסמה.", "he", muted=True),
            ),
            sec(
                "en",
                "Confirm your new email address",
                p(
                    "You asked to change your account's email to {{ .NewEmail }}. Click to confirm:",
                    "en",
                ),
                link_button("Confirm new address", CONFIRM + "email_change"),
                p(
                    "Didn't ask for this? Don't click, and consider changing your password.",
                    "en",
                    muted=True,
                ),
            ),
        ),
        "reauthentication": (
            "Confirm it's you · אישור זהות",
            "Your confirmation code · קוד האישור שלכם",
            sec(
                "he",
                "אישור זהות",
                p("לפני שנמשיך, הקלידו את הקוד כדי לאשר שזה אתם:", "he"),
                layout.code_box(CODE),
                p("הקוד תקף לזמן קצר ולשימוש חד-פעמי. " + ignore_he, "he", muted=True),
            ),
            sec(
                "en",
                "Confirm it's you",
                p("Before we continue, enter this code to confirm it's you:", "en"),
                layout.code_box(CODE),
                p("The code is short-lived and works once. " + ignore_en, "en", muted=True),
            ),
        ),
        "password_changed_notification": (
            "Your password was changed · הסיסמה שונתה",
            "Your password was changed · הסיסמה שלכם שונתה",
            sec(
                "he",
                "הסיסמה שלכם שונתה",
                p("הסיסמה של החשבון {{ .Email }} שונתה זה עתה.", "he"),
                p("לא אתם? אפסו את הסיסמה מיד ופנו אלינו.", "he", muted=True),
            ),
            sec(
                "en",
                "Your password was changed",
                p("The password for {{ .Email }} was just changed.", "en"),
                p("Wasn't you? Reset your password right away and contact us.", "en", muted=True),
            ),
        ),
        "email_changed_notification": (
            "Your email was changed · כתובת האימייל שונתה",
            "Your email was changed · כתובת האימייל שלכם שונתה",
            sec(
                "he",
                "כתובת האימייל שלכם שונתה",
                p("כתובת האימייל של החשבון שונתה מ-{{ .OldEmail }} ל-{{ .Email }}.", "he"),
                p("לא אתם? פנו אלינו מיד.", "he", muted=True),
            ),
            sec(
                "en",
                "Your email address was changed",
                p("Your account's email changed from {{ .OldEmail }} to {{ .Email }}.", "en"),
                p("Wasn't you? Contact us right away.", "en", muted=True),
            ),
        ),
    }
    out = {}
    for name, (subject, preheader, he, en) in templates.items():
        subject, preheader = (text.replace(WRITTEN, BRAND) for text in (subject, preheader))
        document = layout.shell(
            [he, en], subject=subject, preheader=preheader, brand=BRAND, footer=FOOTER, kind=name
        )
        out[name] = (subject, document.replace(WRITTEN, BRAND))
    return out


def main(argv: list[str]) -> int:
    stale = []
    for name, (_, document) in build().items():
        path = HERE / f"{name}.html"
        if "--check" in argv:
            if not path.exists() or path.read_text("utf-8") != document:
                stale.append(path.name)
        else:
            path.write_text(document, encoding="utf-8")
    if stale:
        print(f"Out of date, run python supabase/templates/build.py: {stale}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
