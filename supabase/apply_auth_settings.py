"""Applies the auth section of supabase/config.toml to a hosted Supabase project, so the
dashboard cannot drift from the repo (docs/deploy/auth-settings.md).

    SUPABASE_ACCESS_TOKEN=... SUPABASE_PROJECT_REF=... python supabase/apply_auth_settings.py
    ... --apply        really change the project (without it: only print the differences)

SITE_URL and REDIRECT_URLS (comma separated) override the localhost values of config.toml for
the environment. Standard library only. Email template bodies are sent but never printed."""

import json
import os
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.supabase.com/v1/projects/{ref}/config/auth"
TEMPLATES = {
    name: name
    for name in (
        "confirmation",
        "magic_link",
        "recovery",
        "invite",
        "email_change",
        "reauthentication",
    )
}
# Security notifications (config.toml: [auth.email.notification.*]) are named differently in the API.
NOTIFICATIONS = ("password_changed", "email_changed")


def build_payload(config: dict, root: Path = ROOT, env: dict | None = None) -> dict:
    """The Management API's auth settings that config.toml says. Pure, so it can be tested."""
    env = os.environ if env is None else env
    auth = config["auth"]
    email = auth["email"]
    redirects = (
        [u.strip() for u in env["REDIRECT_URLS"].split(",") if u.strip()]
        if env.get("REDIRECT_URLS")
        else auth["additional_redirect_urls"]
    )
    payload = {
        "site_url": env.get("SITE_URL") or auth["site_url"],
        "uri_allow_list": ",".join(redirects),
        "jwt_exp": auth["jwt_expiry"],
        "refresh_token_rotation_enabled": auth["enable_refresh_token_rotation"],
        "security_refresh_token_reuse_interval": auth["refresh_token_reuse_interval"],
        "external_anonymous_users_enabled": auth["enable_anonymous_sign_ins"],
        "password_min_length": auth["minimum_password_length"],
        "mailer_autoconfirm": not email["enable_confirmations"],
        "mailer_otp_length": email["otp_length"],
        "mailer_otp_exp": email["otp_expiry"],
    }
    for name, key in TEMPLATES.items():
        template = email["template"][name]
        payload[f"mailer_subjects_{key}"] = template["subject"]
        path = root / template["content_path"].removeprefix("./")
        payload[f"mailer_templates_{key}_content"] = path.read_text(encoding="utf-8")
    for name in NOTIFICATIONS:
        notification = email["notification"][name]
        payload[f"mailer_notifications_{name}_enabled"] = notification["enabled"]
        payload[f"mailer_subjects_{name}_notification"] = notification["subject"]
        path = root / notification["content_path"].removeprefix("./")
        payload[f"mailer_templates_{name}_notification_content"] = path.read_text(encoding="utf-8")
    return payload


def differences(current: dict, wanted: dict) -> dict[str, tuple]:
    return {k: (current.get(k), v) for k, v in wanted.items() if current.get(k) != v}


def call(method: str, url: str, token: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        url,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"{}")


def show(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 60 else f"<{len(text)} chars>"


def main(argv: list[str]) -> int:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    ref = os.environ.get("SUPABASE_PROJECT_REF")
    if not token or not ref:
        print("SUPABASE_ACCESS_TOKEN and SUPABASE_PROJECT_REF are required", file=sys.stderr)
        return 2
    wanted = build_payload(tomllib.loads((ROOT / "supabase/config.toml").read_text("utf-8")))
    url = API.format(ref=ref)
    current = call("GET", url, token)
    unknown = [key for key in wanted if key not in current]
    optional = [
        key
        for key in unknown
        if key.startswith("mailer_") and "_notification" in key or "mailer_notifications_" in key
    ]
    if optional:  # older projects may lack the security-notification emails: skip those only
        print(f"Skipping settings this project does not have: {optional}", file=sys.stderr)
        wanted = {k: v for k, v in wanted.items() if k not in optional}
        unknown = [key for key in unknown if key not in optional]
    if unknown:
        print(f"Settings the API does not know (nothing changed): {unknown}", file=sys.stderr)
        return 1
    changes = differences(current, wanted)
    if not changes:
        print("Auth settings already match config.toml.")
        return 0
    for key, (old, new) in changes.items():
        print(f"{key}: {show(old)} -> {show(new)}")
    if "--apply" not in argv:
        print("Dry run. Re-run with --apply to change the project.")
        return 0
    call("PATCH", url, token, {key: new for key, (_, new) in changes.items()})
    print(f"Applied {len(changes)} setting(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
