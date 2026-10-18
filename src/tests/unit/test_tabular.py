import hashlib
from datetime import date, datetime, time
from decimal import Decimal

import pytest

from src.errors import InputError
from src.services.tabular import is_missing, parse_dataset, replace_values, scalar_text, validate_file_type
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("value", "expected"), [("", True), (" \t\n", True), ("\u00a0", True),
                                                 ("0", False), ("null", False), ("NaN", False)])
def test_missing_values_are_whitespace_only(value: str, expected: bool) -> None:
    assert is_missing(value) is expected


@pytest.mark.parametrize(("value", "expected"), [
    (None, ""), (True, "true"), (False, "false"), (42, "42"), (1.5, "1.5"),
    (Decimal("1.2300"), "1.2300"), (" 001 ", " 001 "),
    (date(2026, 10, 7), "2026-10-07"), (time(12, 30), "12:30:00"),
    (datetime(2026, 10, 7, 12, 30), "2026-10-07T12:30:00"),
])
def test_scalar_conversion_preserves_values(value: object, expected: str) -> None:
    assert scalar_text(value) == expected


@pytest.mark.parametrize("value", [[], {}, b"binary", {1, 2}])
def test_nested_and_binary_cells_are_rejected(value: object) -> None:
    with pytest.raises(InputError) as caught:
        scalar_text(value)
    assert caught.value.code == "unsupported_cell"


@pytest.mark.parametrize(("name", "media"), [
    ("DATA.CSV", "TEXT/CSV; charset=utf-8"), ("data.csv", "application/csv"),
    ("data.csv", "application/vnd.ms-excel"), ("data.tsv", "text/tsv"),
    ("data.parquet", "application/x-parquet"), ("data.xlsx", "application/octet-stream"),
    ("data.csv", None), ("data.tsv", ""),
])
def test_supported_media_aliases(name: str, media: str | None) -> None:
    assert validate_file_type(name, media) == name


@pytest.mark.parametrize("name", [None, "", "no_extension", "data.csv.exe", ".csv"])
def test_file_requires_supported_extension(name: str | None) -> None:
    with pytest.raises(InputError) as caught:
        validate_file_type(name, "text/csv")
    assert caught.value.code == "unsupported_file_type"
    assert caught.value.status_code == 415


def test_metadata_and_columns_preserve_exact_input(settings: Settings) -> None:
    content = ' id ,name\r\n001,"Café, Inc"\r\n'.encode()
    parsed = parse_dataset(content, "original.CSV", settings)
    assert parsed.metadata.content_sha256 == hashlib.sha256(content).hexdigest()
    assert parsed.metadata.size_bytes == len(content)
    assert parsed.metadata.original_filename == "original.CSV"
    assert parsed.metadata.headers == [" id ", "name"]
    assert parsed.column(" id ") == ["001"]
    with pytest.raises(ValueError):
        parsed.column("id")


def test_header_only_snapshots_are_explicitly_allowed(settings: Settings) -> None:
    parsed = parse_dataset(b"id,value\n", "empty.csv", settings, allow_empty=True)
    assert parsed.records == ()
    assert parsed.metadata.row_count == 0
    with pytest.raises(InputError) as caught:
        parse_dataset(b"id,value\n", "empty.csv", settings)
    assert caught.value.code == "zero_rows"


def test_snapshot_and_upload_byte_limits_are_separate(settings: Settings) -> None:
    content = b"id\n123456\n"
    limits = settings.model_copy(update={"max_upload_bytes": 5, "max_decoded_bytes": len(content)})
    assert parse_dataset(content, "data.csv", limits, internal_snapshot=True).records == (("123456",),)
    with pytest.raises(InputError) as caught:
        parse_dataset(content, "data.csv", limits)
    assert caught.value.code == "upload_too_large"
    with pytest.raises(InputError) as caught:
        parse_dataset(content + b"\n", "data.csv", limits, internal_snapshot=True)
    assert caught.value.code == "snapshot_too_large"


def test_decoded_limit_counts_utf8_bytes(settings: Settings) -> None:
    content = "id\né\n".encode()
    assert parse_dataset(content, "data.csv", settings.model_copy(update={"max_decoded_bytes": 4})).records == (("é",),)
    with pytest.raises(InputError) as caught:
        parse_dataset(content, "data.csv", settings.model_copy(update={"max_decoded_bytes": 3}))
    assert caught.value.code == "decoded_too_large"


@pytest.mark.parametrize("extension", ["csv", "tsv", "parquet"])
def test_worksheet_argument_only_applies_to_excel(settings: Settings, extension: str) -> None:
    with pytest.raises(InputError) as caught:
        parse_dataset(b"id\n1\n", "data." + extension, settings, sheet_name="Sheet1")
    assert caught.value.code == "unexpected_sheet"


@pytest.mark.parametrize(("extension", "delimiter"), [("csv", ","), ("tsv", "\t")])
@pytest.mark.parametrize("replacement", ["", "001", "a,b\tc", 'quote "here"', "line\nbreak", "=SUM(A1)"])
def test_replacements_round_trip_without_changing_other_cells(settings: Settings, extension: str, delimiter: str, replacement: str) -> None:
    source = f"id{delimiter}value\nA{delimiter}old\nB{delimiter}keep\nC{delimiter}old\n".encode()
    parsed = parse_dataset(source, "data." + extension, settings)
    content, updated = replace_values(source, parsed, 1, {1, 3}, replacement, settings)
    assert updated.records == (("A", replacement), ("B", "keep"), ("C", replacement))
    assert updated.metadata.headers == parsed.metadata.headers
    assert updated.metadata.format == extension
    assert updated.metadata.content_sha256 == hashlib.sha256(content).hexdigest()
    assert parsed.records == (("A", "old"), ("B", "keep"), ("C", "old"))
