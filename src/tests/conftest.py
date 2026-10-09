from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.settings import PROJECT_ROOT, Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, reference_date=date(2026, 10, 7), storage_dir=tmp_path / "storage",
                    rules_path=PROJECT_ROOT / "config" / "facilities.yaml")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client

