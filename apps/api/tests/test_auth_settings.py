"""The script that pushes supabase/config.toml's auth section to a hosted project."""

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "apply_auth", ROOT / "supabase/apply_auth_settings.py"
)
apply_auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_auth)


def payload(env: dict) -> dict:
    config = tomllib.loads((ROOT / "supabase/config.toml").read_text("utf-8"))
    return apply_auth.build_payload(config, env=env)


def test_config_toml_becomes_the_management_api_settings() -> None:
    result = payload({})
    assert result["mailer_otp_length"] == 6 and result["mailer_otp_exp"] == 3600
    assert result["mailer_autoconfirm"] is False  # confirmations are on
    assert result["external_anonymous_users_enabled"] is False
    assert result["refresh_token_rotation_enabled"] is True
    assert "mybiz://**" in result["uri_allow_list"].split(",")
    magic = (ROOT / "supabase/templates/magic_link.html").read_text("utf-8")
    assert result["mailer_templates_magic_link_content"] == magic
    assert "קוד" in result["mailer_subjects_magic_link"]


def test_environment_overrides_the_local_urls() -> None:
    result = payload(
        {"SITE_URL": "https://app.example", "REDIRECT_URLS": "https://app.example/**, mybiz://**"}
    )
    assert result["site_url"] == "https://app.example"
    assert result["uri_allow_list"] == "https://app.example/**,mybiz://**"


def test_only_changed_settings_are_reported() -> None:
    assert apply_auth.differences({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}) == {
        "b": (2, 3),
        "c": (None, 4),
    }
