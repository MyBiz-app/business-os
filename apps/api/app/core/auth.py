"""Verifies access tokens issued by Supabase Auth."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

ALLOWED_ALGORITHMS = ["ES256", "RS256"]


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str


class SigningKeySource(Protocol):
    def key_for(self, token: str) -> object: ...


class JwksKeySource:
    def __init__(self, jwks_url: str) -> None:
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def key_for(self, token: str) -> object:
        return self._client.get_signing_key_from_jwt(token).key


@lru_cache
def get_key_source() -> SigningKeySource:
    return JwksKeySource(get_settings().jwks_url)


bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid_token",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    key_source: Annotated[SigningKeySource, Depends(get_key_source)],
) -> CurrentUser:
    if credentials is None:
        raise UNAUTHORIZED
    token = credentials.credentials
    try:
        claims = jwt.decode(
            token,
            key=key_source.key_for(token),
            algorithms=ALLOWED_ALGORITHMS,
            audience=get_settings().jwt_audience,
            options={"require": ["sub", "exp", "aud"]},
        )
        return CurrentUser(id=UUID(claims["sub"]), email=claims.get("email", ""))
    except (jwt.PyJWTError, ValueError) as error:
        raise UNAUTHORIZED from error
