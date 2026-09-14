import base64
import binascii
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import InvalidTokenError
from loguru import logger

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class DelegationIdentity:
    """JWT 中已验证的调用身份；业务代码不得再直接解释原始 claims。"""

    user_id: int
    patient_id: int | None
    account_type: str | None
    scopes: frozenset[str]


@dataclass(frozen=True)
class DelegationContext:
    """仅在当前 HTTP 请求中使用的委托凭据，不能写入对话持久化状态。"""

    token: str
    claims: dict[str, Any]
    identity: DelegationIdentity


def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="invalid internal api key")


def _delegation_key(encoded_secret: str) -> bytes:
    if not encoded_secret:
        raise RuntimeError("AI_DELEGATION_SIGNING_SECRET is not configured")
    try:
        key = base64.b64decode(encoded_secret, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("AI_DELEGATION_SIGNING_SECRET must be valid Base64") from exc
    if len(key) < 32:
        raise RuntimeError("AI_DELEGATION_SIGNING_SECRET must decode to at least 32 bytes")
    return key


def _optional_int_claim(claims: dict[str, Any], name: str) -> int | None:
    value = claims.get(name)
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError(f"invalid {name} claim") from exc
    if parsed <= 0:
        raise InvalidTokenError(f"invalid {name} claim")
    return parsed


def _identity_from_claims(claims: dict[str, Any]) -> DelegationIdentity:
    try:
        user_id = int(claims.get("sub"))
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("invalid subject claim") from exc
    if user_id <= 0:
        raise InvalidTokenError("invalid subject claim")

    raw_scopes = claims.get("scopes")
    scopes = (
        frozenset(
            item.strip()
            for item in raw_scopes
            if isinstance(item, str) and item.strip()
        )
        if isinstance(raw_scopes, (list, tuple, set))
        else frozenset()
    )
    account_type = claims.get("accountType")
    return DelegationIdentity(
        user_id=user_id,
        patient_id=_optional_int_claim(claims, "patientId"),
        account_type=account_type if isinstance(account_type, str) else None,
        scopes=scopes,
    )


def verify_delegation_token(
    x_delegated_token: str | None = Header(None, alias="X-Delegated-Token"),
    settings: Settings = Depends(get_settings),
) -> DelegationContext:
    """Validate the short-lived JWT delegated by the Java gateway."""
    if not x_delegated_token:
        raise HTTPException(status_code=401, detail="missing delegated token")

    try:
        claims = jwt.decode(
            x_delegated_token,
            _delegation_key(settings.delegation_signing_secret),
            # JJWT selects HS256/384/512 according to the configured HMAC key length.
            algorithms=["HS256", "HS384", "HS512"],
            issuer="wenrun-java",
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid delegated token") from exc
    except RuntimeError as exc:
        logger.exception("delegation token verification unavailable")
        raise HTTPException(status_code=500, detail="delegation token verification is unavailable") from exc

    try:
        identity = _identity_from_claims(claims)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid delegated token") from exc

    return DelegationContext(
        token=x_delegated_token,
        claims=claims,
        identity=identity,
    )
