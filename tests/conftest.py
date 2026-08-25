"""Test environment must be fixed before application modules are imported."""

import os

os.environ.setdefault("SUPERTOKENS_ENABLED", "false")
os.environ.setdefault("MOCK_RESET_ENABLED", "true")
os.environ.setdefault("REQUEST_REPOSITORY", "memory")
