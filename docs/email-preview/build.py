# ruff: noqa: E501  (HTML strings)
"""Builds docs/email-preview/index.html: every MyBiz email in Hebrew and English, light and dark.

    python docs/email-preview/build.py          rewrite the page
    python docs/email-preview/build.py --check  fail if the page is out of date (CI runs this)

Open the file in a browser to review the look before anything is sent. Sample data only."""

import html
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.catalog.welcome import WelcomeDetails, build_welcome  # noqa: E402
from app.messaging import email_layout as layout  # noqa: E402
from app.messaging.email import Email, _fill, _html  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "auth_templates", ROOT / "supabase/templates/build.py"
)
auth = importlib.util.module_from_spec(spec)
sys.modules["auth_templates"] = auth
spec.loader.exec_module(auth)

SAMPLE = {
    "he": {
        "name": "דנה",
        "business": "אדיר פיטנס",
        "service": "יוגה",
        "when": "15/10 18:00",
        "previous": "15/10 17:00",
        "note": "",
        "plan": "כרטיסיה 10",
        "date": "30/10",
    },
    "en": {
        "name": "Dana",
        "business": "Adir Fitness",
        "service": "Yoga",
        "when": "15/10 18:00",
        "previous": "15/10 17:00",
        "note": "",
        "plan": "10-class pass",
        "date": "30/10",
    },
}
LABELS = {"he": ("שיעור", "מועד"), "en": ("Class", "When")}


def notification(kind: str, lang: str) -> str:
    messages = json.loads((ROOT / f"apps/api/app/messages/{lang}.json").read_text("utf-8"))["email"]
    v = SAMPLE[lang]
    subject = _fill(messages["subject"][kind], v)
    text = "\n".join(
        [
            _fill(messages["greeting"], v),
            "",
            _fill(messages["body"][kind], v),
            "",
            _fill(messages["footer"], v),
        ]
    )
    details = (
        ((LABELS[lang][0], v["service"]), (LABELS[lang][1], v["when"]))
        if "{when}" in messages["body"][kind] + messages["subject"][kind]
        else ()
    )
    return _html(
        Email(to="x@y.z", subject=subject, text=text, locale=lang, details=details, kind=kind)
    )


def welcome(lang: str) -> str:
    details = WelcomeDetails(
        to="x@y.z",
        business=SAMPLE[lang]["business"],
        locale=lang,
        currency="ILS",
        join_code="HWGVBAX3",
        trial_ends_on=date(2026, 11, 14),
        modules={},
        expected_active_clients=50,
        web_url="https://example.com",
        client_app_url="https://example.com/app",
        simulated=False,
    )
    return build_welcome(details).html or ""


def emails() -> list[tuple[str, str, str]]:
    """(group, name, html per language joined later) as (group, name, {lang: html})."""
    out = []
    kinds = json.loads((ROOT / "apps/api/app/messages/en.json").read_text("utf-8"))["email"][
        "subject"
    ]
    for kind in kinds:
        out.append(("Client notifications", kind, {x: notification(kind, x) for x in ("he", "en")}))
    out.append(("Business", "welcome", {x: welcome(x) for x in ("he", "en")}))
    for name, (_, document) in auth.build().items():
        out.append(
            (
                "Sign-in and account (Hebrew and English together)",
                name,
                {"he": document, "en": document},
            )
        )
    return out


def dark(document: str) -> str:
    return document.replace("@media (prefers-color-scheme: dark) {", "@media all {")


def page() -> str:
    cards = []
    for group, name, versions in emails():
        frames = "".join(
            f'<div class="v" data-lang="{lang}" data-mode="{mode}"><iframe loading="lazy" '
            f'srcdoc="{html.escape(dark(doc) if mode == "dark" else doc, quote=True)}"></iframe></div>'
            for lang, doc in versions.items()
            for mode in ("light", "dark")
        )
        cards.append(
            f'<section data-group="{html.escape(group)}"><h2>{html.escape(name)}</h2>{frames}</section>'
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{layout.BRAND} email preview</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#e5e7eb;color:#111827}}
header{{position:sticky;top:0;background:#111827;color:#fff;padding:12px 16px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;z-index:2}}
button{{border:0;border-radius:8px;padding:8px 14px;font-weight:700;cursor:pointer}} button.on{{background:#2563EB;color:#fff}}
main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px;padding:16px}}
section{{background:#fff;border-radius:12px;padding:12px}} h2{{font-size:15px;margin:0 0 8px}}
iframe{{width:100%;height:760px;border:0;border-radius:8px}} .v{{display:none}} .v.show{{display:block}}
</style></head><body>
<header><b>{layout.BRAND} emails</b><span id="b"></span><span id="m"></span></header>
<main>{"".join(cards)}</main>
<script>
let lang="he",mode="light";
function btn(id,opts,get,set){{const el=document.getElementById(id);el.innerHTML="";opts.forEach(o=>{{const b=document.createElement("button");b.textContent=o;b.className=get()===o?"on":"";b.onclick=()=>{{set(o);draw()}};el.append(b)}})}}
function draw(){{btn("b",["he","en"],()=>lang,x=>lang=x);btn("m",["light","dark"],()=>mode,x=>mode=x);
document.querySelectorAll(".v").forEach(v=>v.classList.toggle("show",v.dataset.lang===lang&&v.dataset.mode===mode))}}
draw();
</script></body></html>"""


def main(argv: list[str]) -> int:
    path = Path(__file__).resolve().parent / "index.html"
    document = page()
    if "--check" in argv:
        if not path.exists() or path.read_text("utf-8") != document:
            print("Out of date, run python docs/email-preview/build.py", file=sys.stderr)
            return 1
        return 0
    path.write_text(document, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
