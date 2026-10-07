import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.settings import Settings


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]


def test_settings_defaults_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAGUARD_MAX_ROWS", "7")
    assert Settings(_env_file=None).max_rows == 7
    assert Settings(_env_file=None).max_upload_bytes == 10 * 1024 * 1024
    monkeypatch.setenv("DATAGUARD_MAX_ROWS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

