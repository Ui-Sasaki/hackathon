from fastapi.middleware.cors import CORSMiddleware

from app.cruds.main import app


def test_cors_wraps_authentication_middleware() -> None:
    assert app.user_middleware[0].cls is CORSMiddleware
