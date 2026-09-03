"""本番で認証や運用の安全装置を外す設定が、起動時に拒否されることのテスト。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.settings import reject_unsafe_in_production

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_production_rejects_an_unsafe_flag() -> None:
    with pytest.raises(RuntimeError) as error:
        reject_unsafe_in_production("AUTH_MOCK_ENABLED", True, "production")

    assert "AUTH_MOCK_ENABLED" in str(error.value)


def test_production_accepts_a_disabled_flag() -> None:
    reject_unsafe_in_production("AUTH_MOCK_ENABLED", False, "production")


@pytest.mark.parametrize("environment", ["development", "test", "staging"])
def test_other_environments_allow_the_flag(environment: str) -> None:
    reject_unsafe_in_production("AUTH_MOCK_ENABLED", True, environment)


def boot(**overrides: str) -> subprocess.CompletedProcess[str]:
    """本番相当の環境変数でモジュールを読み込み、起動できるかを確かめる。"""
    environment = {
        **os.environ,
        "APP_ENV": "production",
        # conftest がテスト用に false を入れているため、本番相当へ明示的に戻す。
        "SUPERTOKENS_ENABLED": "true",
        "REQUEST_REPOSITORY": "postgres",
        "DATABASE_URL": "postgresql://tetote_app@127.0.0.1:5432/tetote",
        "AUTH_MOCK_ENABLED": "false",
        "MOCK_RESET_ENABLED": "false",
        **overrides,
    }
    environment.pop("GEMINI_API_KEY", None)
    return subprocess.run(
        [sys.executable, "-c", "import app.cruds.main"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_production_starts_with_safe_settings() -> None:
    assert boot().returncode == 0


def test_production_refuses_to_start_with_the_auth_mock() -> None:
    result = boot(AUTH_MOCK_ENABLED="true")

    assert result.returncode != 0
    assert "AUTH_MOCK_ENABLED" in result.stderr


def test_production_refuses_to_start_without_supertokens() -> None:
    result = boot(SUPERTOKENS_ENABLED="false")

    assert result.returncode != 0
    assert "SUPERTOKENS_ENABLED" in result.stderr


def test_production_refuses_to_start_with_mock_reset() -> None:
    result = boot(MOCK_RESET_ENABLED="true")

    assert result.returncode != 0
    assert "MOCK_RESET_ENABLED" in result.stderr
