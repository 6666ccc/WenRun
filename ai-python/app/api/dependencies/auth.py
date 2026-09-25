"""聊天接口的两道入口检查。

X-Api-Key 确认请求来自允许访问的内部调用方；X-Delegated-Token 是 Java
为本次调用签发的短期 JWT，Python 验证后才把其中的用户和患者身份交给业务代码。
请求体里的 userContext 只是待核对的数据，不能代替已验证的令牌身份。
"""

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
    """检查内部 API 密钥；失败时 FastAPI 不会进入聊天路由函数。"""
    if not x_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="invalid internal api key")


def _delegation_key(encoded_secret: str) -> bytes:
    """把配置中的 Base64 密钥还原为 JWT 验签所需的字节，并检查长度。"""
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
    """读取允许缺省的正整数身份字段；格式不对时视为无效令牌。"""
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
    """只提取业务真正需要的身份字段，不让下游自行解释原始 JWT。"""
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
    """验证 Java 传来的委托 JWT，再返回本次请求可用的已验证身份。"""
    if not x_delegated_token:
        raise HTTPException(status_code=401, detail="missing delegated token")

    try:
        # 验证签名、签发者和过期时间；成功解码才可信任 claims 中的身份。
        claims = jwt.decode(
            x_delegated_token,
            _delegation_key(settings.delegation_signing_secret),
            # Java 的 JJWT 会按 HMAC 密钥长度选择 HS256/384/512，验签需接受对应算法。
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
