"""大学メール確認コードの生成、検証、Cloudflare送信。"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from html import escape

import httpx


def normalize_university_email(value: str) -> str:
    email = value.strip().lower()
    if email.count("@") != 1 or not email.rsplit("@", 1)[1].endswith(".ac.jp"):
        raise ValueError("UNIVERSITY_EMAIL_REQUIRED")
    return email


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def code_digest(challenge_id: str, code: str) -> str:
    secret = os.getenv("VERIFICATION_CODE_SECRET")
    if not secret:
        if os.getenv("APP_ENV", "development") == "production":
            raise RuntimeError("VERIFICATION_CODE_SECRET is required")
        secret = "development-only-verification-secret"
    return hmac.new(secret.encode(), f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()


async def send_code(email: str, code: str) -> None:
    token = os.getenv("CLOUDFLARE_EMAIL_API_TOKEN")
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    sender = os.getenv("VERIFICATION_EMAIL_FROM")
    if not all((token, account, sender)):
        if os.getenv("APP_ENV", "development") == "production":
            raise RuntimeError("Cloudflare Email Service is not configured")
        return
    text = f"たすけの輪の大学メール確認コードは {code} です。10分以内に入力してください。"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account}/email/sending/send",
            headers={"Authorization": f"Bearer {token}"},
            json={"to": email, "from": {"address": sender, "name": "たすけの輪"},
                  "subject": "大学メール確認コード", "text": text,
                  "html": f"<p>{escape(text)}</p>"},
        )
    response.raise_for_status()
