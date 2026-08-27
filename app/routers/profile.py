"""Profile and approximate-location API routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.api_support import api_errors, profile_repository_dependency
from app.auth import CurrentUser, get_current_user
from app.repositories.profiles import ProfileRepository, ProfileValidationError
from app.schemas import (
    LocationResolveInput,
    LocationResolveResponse,
    OperationalAreaListResponse,
    ProfileResponse,
    ProfileUpdateInput,
)


router = APIRouter()


@router.get(
    "/profile",
    response_model=ProfileResponse,
    tags=["Profile"],
    summary="自分のプロフィールを取得",
    description="Cookieセッション本人の非公開な詳細プロフィールを返す。",
    responses=api_errors(401, 403, 500),
)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    repository: ProfileRepository = Depends(profile_repository_dependency),
):
    profile = await repository.get(current_user)
    if profile is None:
        raise HTTPException(404, detail={"code": "USER_PROFILE_NOT_FOUND"})
    return profile


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
    repository: ProfileRepository = Depends(profile_repository_dependency),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    try:
        return await repository.update(current_user, changes)
    except KeyError as exc:
        raise HTTPException(404, detail={"code": "USER_PROFILE_NOT_FOUND"}) from exc
    except ProfileValidationError as exc:
        raise HTTPException(
            422,
            detail={"code": "PROFILE_VALIDATION_ERROR", "reason": str(exc)},
        ) from exc


@router.get(
    "/locations/areas",
    response_model=OperationalAreaListResponse,
    tags=["Locations"],
    summary="利用可能な活動地域を取得",
    description="活動地域の正本となるcode・label・都道府県コードを返す。",
    responses=api_errors(401, 403, 500),
)
async def list_operational_areas(
    _current_user: CurrentUser = Depends(get_current_user),
    repository: ProfileRepository = Depends(profile_repository_dependency),
):
    return {"items": await repository.list_areas()}


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
