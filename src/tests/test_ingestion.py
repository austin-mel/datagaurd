import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.errors import InputError
from src.services.tabular import parse_dataset
from src.settings import PROJECT_ROOT, Settings
from src.scripts.generate_fixtures import generate


def test_reproducible_fixtures() -> None:
    expected = generate()
    assert expected == generate()
    for name, data in zip(["facilities_clean.csv", "facilities_dirty.csv", "facilities_errors.json"], expected, strict=True):
        assert (PROJECT_ROOT / "src" / "data" / name).read_bytes() == data
    assert len(json.loads(generate(200)[2])["errors"]) == 21
    with pytest.raises(ValueError):
        generate(19)


@pytest.mark.parametrize("name", ["facilities_clean.csv", "facilities_dirty.csv"])
def test_fixture_upload(client: TestClient, name: str) -> None:
    response = client.post("/datasets/upload", files={"file": (name, (Path("src/data") / name).read_bytes(), "text/csv")})
    assert response.status_code == 200
    metadata = response.json()["metadata"]
    assert metadata["row_count"] == 150
    assert metadata["column_count"] == 7
    assert metadata["headers"][0] == "facility_id"
    assert response.json()["persisted"] is True


def test_text_bom_and_logical_record_numbers(settings: Settings) -> None:
    parsed = parse_dataset(b'\xef\xbb\xbfid,name\r\n001,"line one\nline two"\r\n002,"a,b"\r\n', "demo.csv", settings)
    assert parsed.records == (("001", "line one\nline two"), ("002", "a,b"))
    assert parsed.metadata.row_count == 2
    assert parse_dataset(b'id\n"a""b"\n', "x.csv", settings).records == (('a"b',),)


@pytest.mark.parametrize(("content", "code"), [
    (b"", "empty_file"), (b" \n", "empty_file"), (b"\xef\xbb\xbf", "empty_file"),
    (b"a,b\n", "zero_rows"), (b"a,a\n1,2", "duplicate_header"),
    (b"a, \n1,2", "blank_header"), (b"a,b\n1", "malformed_row"),
    (b"a\n1,2", "malformed_row"), (b"a\n\n", "malformed_row"),
    (b'a\n"unclosed', "malformed_csv"), (b'a\na"b', "malformed_csv"),
    (b'a\n"a" b', "malformed_csv"), (b"a\n\xff", "unsupported_encoding"),
    (b"a\n\x00", "unsupported_encoding"),
])
def test_bad_csv(content: bytes, code: str, settings: Settings) -> None:
    with pytest.raises(InputError) as caught:
        parse_dataset(content, "bad.csv", settings)
    assert caught.value.code == code


def test_byte_and_row_boundaries(settings: Settings) -> None:
    data = b"a\n1\n2\n"
    exact = settings.model_copy(update={"max_upload_bytes": len(data), "max_rows": 2})
    assert parse_dataset(data, "x.csv", exact).metadata.row_count == 2
    for changed, code in [({"max_upload_bytes": len(data) - 1}, "upload_too_large"), ({"max_rows": 1}, "too_many_rows")]:
        with pytest.raises(InputError) as caught:
            parse_dataset(data, "x.csv", exact.model_copy(update=changed))
        assert caught.value.code == code
        assert caught.value.status_code == 413
    assert parse_dataset(b"a\n" + b"x" * 140_000, "x.csv", settings).metadata.row_count == 1


@pytest.mark.parametrize(("name", "media"), [("x.txt", "text/csv"), ("x.csv", "application/json")])
def test_file_type(client: TestClient, name: str, media: str) -> None:
    response = client.post("/datasets/upload", files={"file": (name, b"a\n1", media)})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_missing_file(client: TestClient) -> None:
    response = client.post("/datasets/upload")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"

