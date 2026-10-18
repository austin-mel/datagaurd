from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.errors import InputError
from src.main import create_app
from src.settings import Settings


@pytest.fixture
def error_client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)

    @app.get("/test-error/{kind}")
    def fail(kind: str) -> None:
        if kind == "input":
            raise InputError("conflict", "Refresh the dataset.", 409, {"version": "v2"})
        if kind == "database":
            raise SQLAlchemyError("private database details")
        if kind == "storage":
            raise OSError("private filesystem path")
        raise RuntimeError("private traceback details")

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(("kind", "status", "code"), [
    ("input", 409, "conflict"), ("database", 503, "database_unavailable"),
    ("storage", 503, "storage_unavailable"), ("unexpected", 500, "internal_error"),
])
def test_exceptions_use_stable_error_envelopes(error_client: TestClient, kind: str, status: int, code: str) -> None:
    response = error_client.get("/test-error/" + kind)
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    error = response.json()["error"]
    assert set(error) == {"code", "message", "details"}
    assert error["code"] == code
    assert "private" not in response.text
    assert error["details"] == ({"version": "v2"} if kind == "input" else {})


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "bad"}])
def test_pagination_schema_errors(client: TestClient, params: dict[str, int | str]) -> None:
    response = client.get("/datasets", params=params)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"]["errors"][0]["location"][0] == "query"


def test_malformed_json_has_safe_validation_error(client: TestClient) -> None:
    response = client.post("/api/v1/datasets/missing/validation", content='{ "version":',
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
