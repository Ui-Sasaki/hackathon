import json
from pathlib import Path

from app.main import app


MAJOR_OPERATIONS = {
    ("get", "/profile"), ("patch", "/profile"),
    ("post", "/requests/structure"), ("get", "/requests"),
    ("post", "/requests"), ("get", "/requests/{request_id}"),
    ("patch", "/requests/{request_id}"), ("delete", "/requests/{request_id}"),
    ("post", "/requests/{request_id}/applications"),
    ("get", "/requests/{request_id}/applications"),
    ("post", "/applications/{application_id}/select"),
    ("post", "/applications/{application_id}/withdraw"),
    ("get", "/matches/{match_id}"), ("get", "/matches/{match_id}/messages"),
    ("post", "/matches/{match_id}/messages"),
    ("post", "/matches/{match_id}/complete"),
    ("post", "/matches/{match_id}/dispute"),
    ("post", "/matches/{match_id}/reviews"),
    ("post", "/achievements/generate"),
    ("patch", "/achievements/visibility"), ("post", "/verifications"),
    ("post", "/reports"), ("post", "/users/{user_id}/block"),
}


def test_generated_openapi_is_complete_and_authenticated() -> None:
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert "ErrorResponse" in schema["components"]["schemas"]
    assert schema["components"]["securitySchemes"]["SuperTokensSession"]["in"] == "cookie"
    for method, path in MAJOR_OPERATIONS:
        operation = schema["paths"][path][method]
        success = next(code for code in operation["responses"] if code.startswith("2"))
        if success != "204":
            content = operation["responses"][success]["content"]["application/json"]
            assert "schema" in content, (method, path)
        assert operation["security"] == [{"SuperTokensSession": []}], (method, path)


def test_list_contracts_expose_cursor_paging() -> None:
    schemas = app.openapi()["components"]["schemas"]
    assert "nextCursor" in schemas["RequestListResponse"]["properties"]
    assert "nextCursor" in schemas["MessageListResponse"]["properties"]


def test_openapi_does_not_publish_secret_or_internal_fields() -> None:
    text = json.dumps(app.openapi()).lower()
    forbidden = {
        "password_hash", "service_role_key", "session_token", "access_token",
        "approximate_latitude", "approximate_longitude",
        "reviewer_id", "requester_auth_subject",
    }
    assert all(field not in text for field in forbidden)
    verification_output = app.openapi()["components"]["schemas"]["VerificationResponse"]
    assert "storageObjectKey" not in verification_output["properties"]


def test_checked_in_openapi_matches_application() -> None:
    exported = json.loads(
        (Path(__file__).parents[1] / "docs" / "openapi.json").read_text(encoding="utf-8")
    )
    assert exported == app.openapi()
