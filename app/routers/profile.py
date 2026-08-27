"""Profile and approximate-location API routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.api_support import api_errors
from app.auth import CurrentUser, get_current_user
from app.schemas import (
    LocationResolveInput,
    LocationResolveResponse,
    ProfileResponse,
    ProfileUpdateInput,
)


router = APIRouter()


@router.get(
    "/profile",
    response_model=ProfileResponse,
    tags=["Profile"],
    summary="自分のプロフィールを取得",
    description="Cookieセッションの本人の公開可能なプロフィールだけを返す。",
    responses=api_errors(401, 403, 500),
)
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    from app.cruds import main as runtime

    return runtime.users_store[current_user.user_id]


@router.patch(
    "/profile",
    response_model=ProfileResponse,
    tags=["Profile"],
    summary="自分のプロフィールを更新",
    description=(
        "表示名または概算地域を更新する。ユーザーID、ロール、本人確認状態は入力できない。"
    ),
    responses=api_errors(401, 403, 422, 500),
)
async def update_profile(
    body: ProfileUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    profile = runtime.users_store[current_user.user_id]
    profile.update(changes)
    profile["updatedAt"] = runtime.now_iso()
    return profile


@router.post(
    "/locations/resolve",
    response_model=LocationResolveResponse,
    tags=["Locations"],
    summary="現在地を概算地域へ変換",
    description=(
        "同意済み座標を概算地域へ変換する。座標は保存も返却もしない。"
        "取得失敗時は登録地域へフォールバックする。"
    ),
    responses=api_errors(401, 422, 500),
)
async def resolve_browser_location(
    body: LocationResolveInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    area_code, source = runtime.resolve_location(body, current_user)
    return {
        "areaCode": area_code,
        "areaLabel": runtime.REGIONS[area_code]["label"],
        "source": source,
        "fallbackUsed": source == "registered_region",
    }
