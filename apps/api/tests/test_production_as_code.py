"""Production is defined as code but switched off: these checks keep that definition safe.

They read the repository's own files only (no network, no database).
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"


def _blueprint(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def _env(service: dict) -> dict[str, dict]:
    return {item["key"]: item for item in service["envVars"]}


def test_production_api_service_is_defined_for_safe_releases():
    services = {s["name"]: s for s in _blueprint("render.production.yaml")["services"]}
    api = services["business-os-api"]
    env = _env(api)
    assert api["type"] == "web" and api["plan"] != "free"
    assert api["healthCheckPath"] == "/health/ready"
    assert api["preDeployCommand"] == "alembic upgrade head"
    assert api["autoDeploy"] is False
    assert env["API_ENVIRONMENT"]["value"] == "production"
    assert env["RUN_MIGRATIONS_ON_START"]["value"] == "false"
    # The first six settings the API refuses to start without, plus the GL5/GL6 switches.
    for key in (
        "API_DATABASE_URL",
        "API_JWKS_URL",
        "API_SECRETS_KEY",
        "API_INTERNAL_TOKEN",
        "API_WEB_URL",
        "API_API_URL",
        "API_CORS_ORIGINS",
        "API_SECRETS_KEYS",
        "API_ID_HASH_KEY",
    ):
        assert env[key].get("sync") is False, key


def test_production_blueprint_holds_no_secret_values():
    for service in _blueprint("render.production.yaml")["services"]:
        for item in service["envVars"]:
            if item["key"] in ("API_ENVIRONMENT", "RUN_MIGRATIONS_ON_START", "WEB_CONCURRENCY"):
                continue
            if item["key"] == "API_TRUST_FORWARDED_FOR":
                continue
            assert "value" not in item, f"{service['name']}: {item['key']} must be sync: false"


def test_production_jobs_carry_the_rotation_keys():
    # The jobs decrypt values too; without the key list a rotation would break them.
    services = {s["name"]: s for s in _blueprint("render.production.yaml")["services"]}
    for name in ("business-os-jobs-daily", "business-os-jobs-hourly"):
        env = _env(services[name])
        assert env["API_SECRETS_KEYS"].get("sync") is False
        assert env["API_ID_HASH_KEY"].get("sync") is False


def test_staging_blueprint_checks_readiness_and_migrates_on_start():
    api = _blueprint("render.yaml")["services"][0]
    assert api["healthCheckPath"] == "/health/ready"
    assert _env(api)["RUN_MIGRATIONS_ON_START"]["value"] == "true"


def test_dockerfile_has_a_healthcheck_and_no_inline_migration():
    text = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in text
    assert "alembic upgrade head" not in text  # only the entrypoint migrates
    entrypoint = (ROOT / "apps" / "api" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "RUN_MIGRATIONS_ON_START" in entrypoint and "production" in entrypoint


def test_production_environment_never_holds_the_database_string():
    # Background jobs of production run on Render only; GitHub gets no database connection string
    # for it (the owner connection bypasses nothing, but it can change every table).
    for path in WORKFLOWS.glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            if job.get("environment") not in ("production", {"name": "production"}):
                continue
            assert "DATABASE_URL" not in path.read_text(encoding="utf-8"), path.name


def test_production_web_deploy_runs_from_tags_only_and_needs_the_environment():
    path = WORKFLOWS / "deploy-web-production.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    triggers = workflow.get(True) or workflow["on"]  # YAML reads a bare `on` as True
    assert triggers["push"] == {"tags": ["v*"]}
    assert "branches" not in triggers["push"]
    assert workflow["jobs"]["deploy"]["environment"] == "production"


def test_eas_production_profile_does_not_use_staging_addresses():
    eas = json.loads((ROOT / "apps" / "client-app" / "eas.json").read_text(encoding="utf-8"))
    production = eas["build"]["production"]
    assert production.get("environment") == "production"
    assert "staging" not in json.dumps(production)
