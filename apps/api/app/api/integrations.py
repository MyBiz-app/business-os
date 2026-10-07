"""Integrations (decision X13): which outside provider a business uses for payments, invoicing
and messaging, and the platform's defaults for every capability.

A business connects its own provider in settings → Integrations (its terminal, its invoicing
account, its WhatsApp number). Secrets are encrypted before they reach the database and never
come back: the screens only learn which secrets are set. Removing a connection goes back to
the platform's default. Switching provider is replacing the connection: nothing else changes."""

import json
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, require
from app.api.platform import StaffDep
from app.permissions import Permission
from app.providers.choice import platform_default
from app.providers.registry import (
    CAPABILITIES,
    PER_BUSINESS,
    REGISTRY,
    ProviderInfo,
    ProviderNotConfigured,
    UnknownProvider,
    check_settings,
)
from app.providers.secrets import SecretsKeyMissing, decrypt, encrypt

router = APIRouter(tags=["integrations"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]
BusinessCapability = Literal["payments", "invoicing", "messaging"]


class ProviderField(BaseModel):
    key: str
    label: str
    secret: bool
    required: bool


class ProviderOption(BaseModel):
    name: str
    label: str
    description: str
    builtin: bool = Field(description="Works with no outside account (simulated, internal…)")
    fields: list[ProviderField]


class Integration(BaseModel):
    capability: BusinessCapability
    provider: str
    provider_label: str
    own: bool = Field(description="The business's own connection (not the platform default)")
    builtin: bool
    settings: dict[str, str] = Field(description="Plain settings (secrets are never returned)")
    secrets_set: list[str] = Field(description="Which secret settings have a value")
    connected_at: datetime | None
    options: list[ProviderOption]


class IntegrationUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    settings: dict[str, str] = Field(
        default_factory=dict,
        description="Every setting of the provider; an empty secret keeps the one already set",
    )


class PlatformCapability(BaseModel):
    capability: str
    default_provider: str
    default_label: str
    builtin: bool
    businesses_connected: dict[str, int] = Field(description="Own connections, by provider")
    options: list[ProviderOption]


def _option(info: ProviderInfo) -> ProviderOption:
    return ProviderOption(
        name=info.name,
        label=info.label,
        description=info.description,
        builtin=info.builtin,
        fields=[
            ProviderField(key=f.key, label=f.label, secret=f.secret, required=f.required)
            for f in info.fields
        ],
    )


def _integration(db: Session, capability: BusinessCapability) -> Integration:
    row = (
        db.execute(
            text("""
                SELECT provider, settings, secrets, connected_at FROM app.tenant_integrations
                WHERE capability = :c AND active
            """),
            {"c": capability},
        )
        .mappings()
        .first()
    )
    if row is not None:
        info = REGISTRY.get(capability, row["provider"])
        secrets = sorted(decrypt(row["secrets"]))
        settings, connected_at, own = dict(row["settings"] or {}), row["connected_at"], True
    else:
        name, _ = platform_default(capability)
        info = REGISTRY.get(capability, name)
        secrets, settings, connected_at, own = [], {}, None, False
    return Integration(
        capability=capability,
        provider=info.name,
        provider_label=info.label,
        own=own,
        builtin=info.builtin,
        settings=settings,
        secrets_set=secrets,
        connected_at=connected_at,
        options=[_option(p) for p in REGISTRY.of(capability)],
    )


@router.get("/integrations")
def business_integrations(context: SettingsDep) -> list[Integration]:
    """The business's provider per capability, with the providers it can switch to."""
    return [_integration(context.session, c) for c in PER_BUSINESS]  # type: ignore[arg-type]


@router.put("/integrations/{capability}")
def connect(
    capability: BusinessCapability, body: IntegrationUpdate, context: SettingsDep
) -> Integration:
    """Connects (or switches to) a provider. Its settings are checked and the provider is built
    once before saving, so a typo fails here and not on a client's payment."""
    db = context.session
    try:
        info = REGISTRY.get(capability, body.provider)
    except UnknownProvider as error:
        raise HTTPException(status_code=422, detail="unknown_provider") from error
    current = (
        db.execute(
            text("""
                SELECT provider, secrets FROM app.tenant_integrations WHERE capability = :c
            """),
            {"c": capability},
        )
        .mappings()
        .first()
    )
    kept = decrypt(current["secrets"]) if current and current["provider"] == info.name else {}
    secret_keys = {f.key for f in info.fields if f.secret}
    values = {k: v for k, v in body.settings.items() if v.strip()}
    for key in secret_keys:  # an empty secret keeps the one already set
        if key not in values and key in kept:
            values[key] = kept[key]
    try:
        values = check_settings(info, values)
        info.factory(values)
    except (ValueError, ProviderNotConfigured) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    plain = {k: v for k, v in values.items() if k not in secret_keys}
    secret = {k: v for k, v in values.items() if k in secret_keys}
    try:
        blob = encrypt(secret) if secret else None
    except SecretsKeyMissing as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="secrets_key_missing"
        ) from error
    db.execute(
        text("""
            INSERT INTO app.tenant_integrations
                (tenant_id, capability, provider, settings, secrets, connected_by)
            VALUES (:t, :c, :p, CAST(:settings AS jsonb), :secrets, app.current_user_id())
            ON CONFLICT (tenant_id, capability) DO UPDATE
            SET provider = excluded.provider, settings = excluded.settings,
                secrets = excluded.secrets, active = true, connected_by = excluded.connected_by,
                connected_at = CASE WHEN app.tenant_integrations.provider = excluded.provider
                                    THEN app.tenant_integrations.connected_at ELSE now() END,
                updated_at = now()
        """),
        {
            "t": context.tenant_id,
            "c": capability,
            "p": info.name,
            "settings": json.dumps(plain),
            "secrets": blob,
        },
    )
    db.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (:t, 'user', app.current_user_id(), 'integration.connected',
                    jsonb_build_object('capability', CAST(:c AS text),
                                       'provider', CAST(:p AS text)))
        """),
        {"t": context.tenant_id, "c": capability, "p": info.name},
    )
    return _integration(db, capability)


@router.delete("/integrations/{capability}")
def disconnect(capability: BusinessCapability, context: SettingsDep) -> Integration:
    """Removes the business's own connection: the platform's default applies again."""
    db = context.session
    db.execute(text("DELETE FROM app.tenant_integrations WHERE capability = :c"), {"c": capability})
    db.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (:t, 'user', app.current_user_id(), 'integration.disconnected',
                    jsonb_build_object('capability', CAST(:c AS text)))
        """),
        {"t": context.tenant_id, "c": capability},
    )
    return _integration(db, capability)


@router.get("/platform/integrations")
def platform_integrations(session: StaffDep) -> list[PlatformCapability]:
    """The platform's default provider per capability, the providers available, and how many
    businesses connected their own (MyBiz console)."""
    counts: dict[str, dict[str, int]] = {}
    for row in session.execute(text("SELECT * FROM app.integration_counts()")).mappings():
        counts.setdefault(row["capability"], {})[row["provider"]] = row["businesses"]
    result = []
    for capability in CAPABILITIES:
        name, _ = (
            platform_default(capability)
            if capability not in ("email", "ai")
            else (
                _email_or_ai_default(capability),
                {},
            )
        )
        try:
            info = REGISTRY.get(capability, name)
            label, builtin = info.label, info.builtin
        except UnknownProvider:
            label, builtin = name, False
        result.append(
            PlatformCapability(
                capability=capability,
                default_provider=name,
                default_label=label,
                builtin=builtin,
                businesses_connected=counts.get(capability, {}),
                options=[_option(p) for p in REGISTRY.of(capability)],
            )
        )
    return result


def _email_or_ai_default(capability: str) -> str:
    from app.core.config import get_settings

    settings = get_settings()
    if capability == "email":
        provider = settings.email_provider
        return "smtp" if provider == "gmail" else provider
    return "anthropic" if settings.anthropic_api_key is not None else "demo"
