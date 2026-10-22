from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.services.default_dataset import DEFAULT_DATASET_ID
from src.settings import PROJECT_ROOT, Settings


def test_default_workspace_contains_bundled_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATAGUARD_SEED_DEFAULT_DATASET")
    settings = Settings(_env_file=None, storage_dir=tmp_path / "storage")
    assert settings.seed_default_dataset is True
    path = f"/api/v1/datasets/{DEFAULT_DATASET_ID}"
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/workspace")
        assert response.status_code == 200
        dataset, = response.json()["datasets"]
        assert dataset["id"] == DEFAULT_DATASET_ID
        assert dataset["name"] == "facilities_dirty.csv"
        assert dataset["rowCount"] == 150
        assert len(dataset["columns"]) == 7
        assert dataset["processingStatus"] == "completed"
        assert dataset["status"] == "needs-review"
        assert dataset["validation"]["issues"]
        assert dataset["ruleset"]["name"] == "facilities"
        assert client.get(path + "/file", params={"version": "v1"}).content == (
            PROJECT_ROOT / "src/data/facilities_dirty.csv"
        ).read_bytes()
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/workspace").json()["datasets"] == [dataset]
        assert client.get(f"/datasets/{DEFAULT_DATASET_ID}/versions").json()["total"] == 1


def test_startup_preserves_new_versions_and_other_uploads(settings: Settings) -> None:
    settings = settings.model_copy(update={"seed_default_dataset": True})
    path = f"/api/v1/datasets/{DEFAULT_DATASET_ID}"
    with TestClient(create_app(settings)) as client:
        clean = (PROJECT_ROOT / "src/data/facilities_clean.csv").read_bytes()
        response = client.post(f"/datasets/{DEFAULT_DATASET_ID}/versions",
                               files={"file": ("facilities_clean.csv", clean, "text/csv")})
        assert response.status_code == 200, response.text
        other = client.post("/api/v1/datasets", files={"file": ("other.csv", b"id\n1\n", "text/csv")})
        assert other.status_code == 201
        dataset = client.get(path).json()
    with TestClient(create_app(settings)) as client:
        assert client.get(path).json() == dataset
        assert client.get("/datasets").json()["total"] == 2
        assert client.get(f"/datasets/{DEFAULT_DATASET_ID}/versions").json()["total"] == 2
        assert client.get(path + "/file", params={"version": "v2"}).content == clean


def test_startup_seeding_can_be_disabled(settings: Settings) -> None:
    assert settings.seed_default_dataset is False
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/workspace").json()["datasets"] == []
