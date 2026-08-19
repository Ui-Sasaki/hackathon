"""`uvicorn main:app` 用の互換エントリーポイント。"""

from app.main import app

__all__ = ["app"]
