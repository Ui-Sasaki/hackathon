"""SuperTokens configuration and FastAPI authentication dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Literal

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyCookie


SUPERTOKENS_ENABLED = os.getenv("SUPERTOKENS_ENABLED", "true").lower() in {
    "1", "true", "yes", "on"
}

if SUPERTOKENS_ENABLED:
    from supertokens_python import InputAppInfo, SupertokensConfig, get_all_cors_headers, init
    from supertokens_python.exceptions import SuperTokensError
    from supertokens_python.recipe import emailpassword, multifactorauth, session
    from supertokens_python.recipe.emailpassword import EmailPasswordOverrideConfig
    from supertokens_python.recipe.emailpassword.interfaces import PasswordResetPostOkResult
    from supertokens_python.recipe.session.asyncio import revoke_all_sessions_for_user
    from supertokens_python.recipe.session.framework.fastapi import verify_session


# 利用者の永続的な種別だけを表す。依頼者・支援者は利用者の属性ではなく、
# 依頼やマッチに対する文脈上のアクターなので、ここには含めない
# （要件定義書 §5 では双方が依頼作成と応募を行える）。
Role = Literal["member", "admin", "verifier"]
session_cookie = APIKeyCookie(
    name="sAccessToken",
    scheme_name="SuperTokensSession",
    description=(
        "SuperTokensが発行するHttpOnly Cookieセッション。更新系ではSDKが付与する"
        "anti-csrfヘッダーも必要です。ユーザーIDやロールはセッションから決定します。"
    ),
    auto_error=False,
)


@dataclass(frozen=True)
class CurrentUser:
    """Identity from SuperTokens plus authorization state from the application DB."""

    user_id: str
    role: Role
    status: str
    email_verified: bool
    verification_status: str
    mfa_completed: bool = False


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _override_emailpassword_apis(original):
    original_password_reset_post = original.password_reset_post

    async def password_reset_post(*args, **kwargs):
        result = await original_password_reset_post(*args, **kwargs)
        if isinstance(result, PasswordResetPostOkResult):
            # A changed password invalidates every pre-existing login, including
            # sessions belonging to linked login methods.
            await revoke_all_sessions_for_user(result.user.id)
        return result

    original.password_reset_post = password_reset_post
    return original


def initialise_supertokens() -> None:
    """Initialise the SDK once when the ASGI module is imported."""

    if not SUPERTOKENS_ENABLED:
        return
    init(
        app_info=InputAppInfo(
            app_name="たすけの輪",
            api_domain=os.getenv("API_DOMAIN", "http://localhost:8000"),
            website_domain=os.getenv("WEBSITE_DOMAIN", "http://localhost:3000"),
            api_base_path="/auth",
            website_base_path="/auth",
        ),
        supertokens_config=SupertokensConfig(
            connection_uri=os.getenv("SUPERTOKENS_CONNECTION_URI", "http://localhost:3567"),
            api_key=os.getenv("SUPERTOKENS_API_KEY") or None,
        ),
        framework="fastapi",
        recipe_list=[
            emailpassword.init(
                override=EmailPasswordOverrideConfig(apis=_override_emailpassword_apis)
            ),
            session.init(
                cookie_secure=_env_bool("AUTH_COOKIE_SECURE", True),
                cookie_same_site=os.getenv("AUTH_COOKIE_SAME_SITE", "lax"),
                anti_csrf="VIA_CUSTOM_HEADER",
            ),
            # Enables adding TOTP/passwordless second factors without changing
            # the session/authentication boundary used by business endpoints.
            multifactorauth.init(first_factors=["emailpassword"]),
        ],
    )


initialise_supertokens()


def cors_headers() -> list[str]:
    if not SUPERTOKENS_ENABLED:
        return ["Content-Type", "Idempotency-Key"]
    return ["Content-Type", "Idempotency-Key", *get_all_cors_headers()]


# Supabase will replace this lookup. Keeping it injectable makes session tests
# independent from a running SuperTokens Core and application database.
_user_lookup: Callable[[str], dict[str, Any] | None] = lambda _user_id: None


def configure_user_lookup(lookup: Callable[[str], dict[str, Any] | None]) -> None:
    global _user_lookup
    _user_lookup = lookup


async def get_current_user(
    request: Request,
    _session_cookie: str | None = Security(session_cookie),
) -> CurrentUser:
    if not SUPERTOKENS_ENABLED:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})
    try:
        verified = await verify_session(
            anti_csrf_check=True,
            check_database=True,
        )(request)
    except SuperTokensError as exc:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"}) from exc

    if verified is None:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})

    user_id = verified.get_user_id()
    record = _user_lookup(user_id)
    if record is None:
        raise HTTPException(403, detail={"code": "USER_PROFILE_NOT_FOUND"})
    if record.get("status") != "active":
        raise HTTPException(403, detail={"code": "USER_SUSPENDED"})

    payload = verified.get_access_token_payload()
    mfa_claim = payload.get("st-mfa", {})
    return CurrentUser(
        user_id=user_id,
        role=record["role"],
        status=record["status"],
        email_verified=record.get("emailVerified", False),
        verification_status=record.get("verificationStatus", "unverified"),
        mfa_completed=bool(mfa_claim.get("v", False)),
    )


def require_roles(*roles: Role, verified: bool = False):
    async def dependency(request: Request) -> CurrentUser:
        user = await get_current_user(request)
        if user.role not in roles:
            raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
        if verified and user.verification_status != "approved":
            raise HTTPException(403, detail={"code": "VERIFICATION_REQUIRED"})
        if user.role in {"admin", "verifier"} and not user.mfa_completed:
            raise HTTPException(403, detail={"code": "MFA_REQUIRED"})
        return user

    return dependency
