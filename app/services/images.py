"""Server-side image validation and metadata removal.

要件定義書 12「ファイル形式、容量、拡張子、MIMEタイプを検証する」
「アップロード画像のメタデータを削除する」に対応する。

クライアントの申告は検証の入口にすぎない。実際に保存するかどうかは、
バイト列そのものから判定した結果で決める。
"""

from __future__ import annotations

from typing import Literal

# 要件定義書 13.1「画像アップロード上限：1ファイル10MB」
MAX_IMAGE_BYTES = 10 * 1024 * 1024

ImageContentType = Literal["image/jpeg", "image/png"]

# 拡張子はMIME typeと突き合わせる。片方だけを信用しない。
ALLOWED_IMAGE_TYPES: dict[str, tuple[str, ...]] = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
}

_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# 描画に必要なチャンクだけを残す。テキスト、時刻、EXIFなどの付随情報は落とす。
_PNG_KEPT_CHUNKS = frozenset(
    {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB"}
)


class ImageValidationError(Exception):
    """検証に落ちた理由を、そのままHTTPステータスへ写せる形で運ぶ。"""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def detect_image_type(data: bytes) -> str | None:
    """バイト列の先頭から実体の形式を判定する。拡張子とMIME typeは見ない。"""
    if data.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    if data.startswith(_PNG_SIGNATURE):
        return "image/png"
    return None


def _extension_of(file_name: str | None) -> str | None:
    if not file_name or "." not in file_name:
        return None
    return "." + file_name.rsplit(".", 1)[1].lower()


def validate_declaration(
    content_type: str, byte_size: int, file_name: str | None = None
) -> None:
    """アップロード開始時の申告を検証する。実体の検証は受信後に別途行う。"""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ImageValidationError(
            415, "UNSUPPORTED_MEDIA_TYPE", "JPEGまたはPNGの画像を選んでください"
        )
    if byte_size <= 0:
        raise ImageValidationError(422, "INVALID_IMAGE", "画像を読み取れませんでした")
    if byte_size > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            413, "IMAGE_TOO_LARGE", "画像は10MBまでにしてください"
        )
    extension = _extension_of(file_name)
    if extension is not None and extension not in ALLOWED_IMAGE_TYPES[content_type]:
        raise ImageValidationError(
            415, "EXTENSION_MISMATCH", "ファイル名の拡張子と画像の形式が一致しません"
        )


def _strip_jpeg_metadata(data: bytes) -> bytes:
    """APP1以降のアプリケーションセグメントとコメントを取り除く。

    EXIFはAPP1に入るため、位置情報や端末情報はここで落ちる。
    画素データ（SOS以降）には触れないので、再エンコードは行わない。
    """
    output = bytearray(data[:2])
    index = 2
    length = len(data)
    while index + 4 <= length:
        if data[index] != 0xFF:
            break
        marker = data[index + 1]
        # SOS以降は画素データが続くため、そのまま末尾まで写す。
        if marker == 0xDA:
            output.extend(data[index:])
            return bytes(output)
        segment_length = int.from_bytes(data[index + 2 : index + 4], "big")
        if segment_length < 2 or index + 2 + segment_length > length:
            raise ImageValidationError(
                422, "INVALID_IMAGE", "画像を読み取れませんでした"
            )
        is_metadata = 0xE1 <= marker <= 0xEF or marker == 0xFE
        if not is_metadata:
            output.extend(data[index : index + 2 + segment_length])
        index += 2 + segment_length
    raise ImageValidationError(422, "INVALID_IMAGE", "画像を読み取れませんでした")


def _strip_png_metadata(data: bytes) -> bytes:
    """描画に不要なチャンクを落とす。チャンク単位で捨てるためCRCは再計算しない。"""
    output = bytearray(_PNG_SIGNATURE)
    index = len(_PNG_SIGNATURE)
    length = len(data)
    saw_end = False
    while index + 8 <= length:
        chunk_length = int.from_bytes(data[index : index + 4], "big")
        chunk_type = data[index + 4 : index + 8]
        chunk_end = index + 12 + chunk_length
        if chunk_length < 0 or chunk_end > length:
            raise ImageValidationError(
                422, "INVALID_IMAGE", "画像を読み取れませんでした"
            )
        if chunk_type in _PNG_KEPT_CHUNKS:
            output.extend(data[index:chunk_end])
        if chunk_type == b"IEND":
            saw_end = True
            break
        index = chunk_end
    if not saw_end:
        raise ImageValidationError(422, "INVALID_IMAGE", "画像を読み取れませんでした")
    return bytes(output)


def sanitize_image(data: bytes, declared_content_type: str) -> tuple[bytes, str]:
    """受信したバイト列を検証し、メタデータを除いた画像を返す。

    申告されたMIME typeと実体が食い違う場合は、拡張子偽装として拒否する。
    """
    if len(data) == 0:
        raise ImageValidationError(422, "INVALID_IMAGE", "画像を読み取れませんでした")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            413, "IMAGE_TOO_LARGE", "画像は10MBまでにしてください"
        )
    actual = detect_image_type(data)
    if actual is None:
        raise ImageValidationError(
            415, "UNSUPPORTED_MEDIA_TYPE", "JPEGまたはPNGの画像を選んでください"
        )
    if actual != declared_content_type:
        raise ImageValidationError(
            415, "CONTENT_TYPE_MISMATCH", "選んだファイルの形式が一致しません"
        )
    if actual == "image/jpeg":
        return _strip_jpeg_metadata(data), actual
    return _strip_png_metadata(data), actual
