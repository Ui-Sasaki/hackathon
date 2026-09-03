"""画像アップロードとプロフィール画像APIのテスト。"""

import asyncio
import os
import zlib

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx
import pytest

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.repositories.uploads import get_upload_repository
from app.services import images


class ASGITestClient:
    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


client = ASGITestClient()

OWNER = CurrentUser(
    user_id="usr_101", role="member", status="active",
    email_verified=True, verification_status="approved",
)
OTHER = CurrentUser(
    user_id="usr_207", role="member", status="active",
    email_verified=True, verification_status="approved",
)


def act_as(user: CurrentUser) -> None:
    async def current() -> CurrentUser:
        return user

    app.dependency_overrides[get_current_user] = current


def setup_function() -> None:
    act_as(OWNER)
    client.post("/_mock/reset")


# --- テスト用の画像バイト列 -------------------------------------------


def jpeg_segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


EXIF_SECRET = b"GPS-35.6812-139.7671"


def jpeg_bytes(*, with_metadata: bool = True) -> bytes:
    data = b"\xff\xd8"
    data += jpeg_segment(0xE0, b"JFIF\x00\x01\x02\x00\x00\x01\x00\x01\x00\x00")
    if with_metadata:
        data += jpeg_segment(0xE1, b"Exif\x00\x00" + EXIF_SECRET)
        data += jpeg_segment(0xFE, b"camera comment")
    # SOS以降は画素データとして末尾までそのまま扱われる。
    data += b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
    data += b"\xff\xd9"
    return data


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + chunk_type
        + payload
        + zlib.crc32(chunk_type + payload).to_bytes(4, "big")
    )


PNG_SECRET = b"taken-by-someone"


def png_bytes(*, with_metadata: bool = True) -> bytes:
    header = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
    if with_metadata:
        data += png_chunk(b"tEXt", b"Comment\x00" + PNG_SECRET)
        data += png_chunk(b"eXIf", PNG_SECRET)
    data += png_chunk(b"IDAT", b"\x78\x9c\x63\x00\x00\x00\x02\x00\x01")
    data += png_chunk(b"IEND", b"")
    return data


# --- サービス層 ---------------------------------------------------------


def test_jpeg_metadata_is_removed() -> None:
    sanitized, content_type = images.sanitize_image(jpeg_bytes(), "image/jpeg")
    assert content_type == "image/jpeg"
    assert EXIF_SECRET not in sanitized
    assert b"camera comment" not in sanitized
    # 画素データとJFIFヘッダーは残す。
    assert sanitized.startswith(b"\xff\xd8\xff\xe0")
    assert sanitized.endswith(b"\xff\xd9")


def test_png_metadata_is_removed() -> None:
    sanitized, _ = images.sanitize_image(png_bytes(), "image/png")
    assert PNG_SECRET not in sanitized
    assert b"tEXt" not in sanitized
    assert b"eXIf" not in sanitized
    assert b"IHDR" in sanitized and b"IDAT" in sanitized and b"IEND" in sanitized


def test_image_without_metadata_keeps_its_content() -> None:
    original = png_bytes(with_metadata=False)
    sanitized, _ = images.sanitize_image(original, "image/png")
    assert sanitized == original


def test_extension_must_match_the_declared_type() -> None:
    with pytest.raises(images.ImageValidationError) as error:
        images.validate_declaration("image/png", 1000, "photo.jpg")
    assert error.value.status == 415


def test_declared_size_over_the_limit_is_rejected() -> None:
    with pytest.raises(images.ImageValidationError) as error:
        images.validate_declaration("image/jpeg", images.MAX_IMAGE_BYTES + 1, "a.jpg")
    assert error.value.status == 413


def test_content_type_is_decided_by_the_bytes_not_the_declaration() -> None:
    with pytest.raises(images.ImageValidationError) as error:
        images.sanitize_image(png_bytes(), "image/jpeg")
    assert error.value.code == "CONTENT_TYPE_MISMATCH"


def test_a_renamed_script_is_not_accepted_as_an_image() -> None:
    with pytest.raises(images.ImageValidationError) as error:
        images.sanitize_image(b"<?php echo 1; ?>", "image/jpeg")
    assert error.value.status == 415


def test_truncated_image_is_rejected() -> None:
    with pytest.raises(images.ImageValidationError) as error:
        images.sanitize_image(png_bytes()[:20], "image/png")
    assert error.value.code == "INVALID_IMAGE"


# --- アップロードAPI ---------------------------------------------------


def start_upload(purpose: str = "profile_image", content_type: str = "image/png") -> dict:
    response = client.post(
        "/uploads",
        json={
            "purpose": purpose,
            "contentType": content_type,
            "byteSize": 1024,
            "fileName": "photo.png" if content_type == "image/png" else "photo.jpg",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def send_content(upload: dict, data: bytes, content_type: str = "image/png") -> httpx.Response:
    return client.put(
        upload["uploadUrl"], content=data, headers={"Content-Type": content_type}
    )


def upload_profile_image() -> dict:
    upload = start_upload()
    assert send_content(upload, png_bytes()).status_code == 200
    response = client.put("/profile/image", json={"uploadId": upload["uploadId"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_session_does_not_expose_storage_internals() -> None:
    upload = start_upload()
    assert set(upload) == {"uploadId", "uploadUrl", "expiresAt", "maxBytes"}
    assert "private/" not in upload["uploadUrl"]
    assert upload["maxBytes"] == images.MAX_IMAGE_BYTES


def test_unsupported_declared_type_is_rejected() -> None:
    response = client.post(
        "/uploads",
        json={"purpose": "profile_image", "contentType": "image/gif", "byteSize": 10},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_declared_size_over_the_limit_is_rejected_by_the_api() -> None:
    response = client.post(
        "/uploads",
        json={
            "purpose": "profile_image",
            "contentType": "image/png",
            "byteSize": images.MAX_IMAGE_BYTES + 1,
        },
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_content_that_is_not_an_image_is_rejected() -> None:
    upload = start_upload()
    response = send_content(upload, b"not an image at all")
    assert response.status_code == 415


def test_declared_and_actual_type_mismatch_is_rejected() -> None:
    upload = start_upload(content_type="image/jpeg")
    response = send_content(upload, png_bytes(), content_type="image/jpeg")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "CONTENT_TYPE_MISMATCH"


def test_content_cannot_be_sent_twice() -> None:
    upload = start_upload()
    assert send_content(upload, png_bytes()).status_code == 200
    assert send_content(upload, png_bytes()).status_code == 409


def test_another_user_cannot_send_content_to_my_upload() -> None:
    upload = start_upload()
    act_as(OTHER)
    response = send_content(upload, png_bytes())
    assert response.status_code == 404


def test_another_user_cannot_claim_my_upload_as_their_image() -> None:
    upload = start_upload()
    assert send_content(upload, png_bytes()).status_code == 200
    act_as(OTHER)
    response = client.put("/profile/image", json={"uploadId": upload["uploadId"]})
    assert response.status_code == 404


def test_upload_requires_authentication() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    response = client.post(
        "/uploads",
        json={"purpose": "profile_image", "contentType": "image/png", "byteSize": 10},
    )
    assert response.status_code == 401


def test_purpose_must_match_the_endpoint() -> None:
    upload = start_upload(purpose="verification_document")
    assert send_content(upload, png_bytes()).status_code == 200
    response = client.put("/profile/image", json={"uploadId": upload["uploadId"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UPLOAD_PURPOSE_MISMATCH"


def test_image_cannot_be_confirmed_before_its_content_arrives() -> None:
    upload = start_upload()
    response = client.put("/profile/image", json={"uploadId": upload["uploadId"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UPLOAD_CONTENT_MISSING"


def test_upload_cannot_be_confirmed_twice() -> None:
    upload = start_upload()
    assert send_content(upload, png_bytes()).status_code == 200
    assert client.put("/profile/image", json={"uploadId": upload["uploadId"]}).status_code == 200
    response = client.put("/profile/image", json={"uploadId": upload["uploadId"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UPLOAD_ALREADY_USED"


def test_unknown_upload_is_not_found() -> None:
    response = client.put("/profile/image", json={"uploadId": "does-not-exist"})
    assert response.status_code == 404


# --- プロフィール画像 --------------------------------------------------


def test_profile_exposes_only_a_safe_image_url() -> None:
    confirmed = upload_profile_image()
    profile = client.get("/profile").json()

    assert profile["imageUrl"] == confirmed["imageUrl"]
    assert profile["imageUrl"].startswith("/profile/images/")
    # 推測できる値を公開パスへ出さない。
    assert OWNER.user_id not in profile["imageUrl"]
    assert "photo" not in profile["imageUrl"]
    assert "private/" not in profile["imageUrl"]
    assert "storageObjectKey" not in profile


def test_profile_image_can_be_fetched_by_an_authenticated_user() -> None:
    confirmed = upload_profile_image()
    act_as(OTHER)
    response = client.get(confirmed["imageUrl"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["cache-control"] == "private, no-store"
    assert PNG_SECRET not in response.content


def test_profile_image_requires_authentication() -> None:
    confirmed = upload_profile_image()
    app.dependency_overrides.pop(get_current_user, None)
    assert client.get(confirmed["imageUrl"]).status_code == 401


def test_unknown_image_token_is_not_found() -> None:
    assert client.get("/profile/images/unknown-token").status_code == 404


def test_verification_documents_are_not_served_as_profile_images() -> None:
    upload = start_upload(purpose="verification_document")
    assert send_content(upload, png_bytes()).status_code == 200

    repository = get_upload_repository()
    image = asyncio.run(
        repository.promote_to_image(upload["uploadId"], OWNER.user_id)
    )
    # 参照子を知っていても、用途が違う画像はこの経路では返さない。
    assert client.get(f"/profile/images/{image['viewToken']}").status_code == 404


def test_replacing_an_image_changes_the_url_and_drops_the_old_one() -> None:
    first = upload_profile_image()
    second = upload_profile_image()

    assert first["imageUrl"] != second["imageUrl"]
    assert client.get(second["imageUrl"]).status_code == 200
    assert client.get(first["imageUrl"]).status_code == 404


def test_a_failed_replacement_keeps_the_existing_image() -> None:
    first = upload_profile_image()

    upload = start_upload()
    assert send_content(upload, b"broken").status_code == 415
    assert client.put("/profile/image", json={"uploadId": upload["uploadId"]}).status_code == 409

    profile = client.get("/profile").json()
    assert profile["imageUrl"] == first["imageUrl"]
    assert client.get(first["imageUrl"]).status_code == 200


def test_image_can_be_deleted() -> None:
    confirmed = upload_profile_image()
    assert client.delete("/profile/image").status_code == 204

    profile = client.get("/profile").json()
    assert profile["imageUrl"] is None
    assert client.get(confirmed["imageUrl"]).status_code == 404


def test_deleting_a_missing_image_is_reported() -> None:
    response = client.delete("/profile/image")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROFILE_IMAGE_NOT_FOUND"


def test_delete_requires_authentication() -> None:
    upload_profile_image()
    app.dependency_overrides.pop(get_current_user, None)
    assert client.delete("/profile/image").status_code == 401


def test_profile_starts_without_an_image() -> None:
    assert client.get("/profile").json()["imageUrl"] is None
