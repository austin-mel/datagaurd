from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, reference_date=date(2026, 10, 7))


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client

