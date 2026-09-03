"""Test environment must be fixed before application modules are imported."""

import os

os.environ.setdefault("SUPERTOKENS_ENABLED", "false")
os.environ.setdefault("MOCK_RESET_ENABLED", "true")
os.environ.setdefault("REQUEST_REPOSITORY", "memory")

# LLMを呼ぶ経路はテストごとに差し替える。実APIキーが環境に残っていても、
# テスト結果が外部サービスの応答に左右されないようにする。
os.environ.pop("GEMINI_API_KEY", None)
