import csv
import hashlib
import io
from dataclasses import dataclass
from pathlib import PurePath

from src.errors import InputError
from src.schemas import DatasetMetadata
from src.settings import Settings

# The total byte limit bounds each field; avoid csv's unrelated 128 KiB default.
csv.field_size_limit(2**31 - 1)
CSV_MEDIA_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel",
                   "application/octet-stream", "text/plain"}


@dataclass(frozen=True)
class ParsedCsv:
    metadata: DatasetMetadata
    records: tuple[tuple[str, ...], ...]

    def column(self, name: str) -> list[str]:
        index = self.metadata.headers.index(name)
        return [row[index] for row in self.records]


def is_missing(value: str) -> bool:
    return not value.strip()


def validate_file_type(filename: str | None, content_type: str | None) -> str:
    if not filename or PurePath(filename).suffix.lower() != ".csv":
        raise InputError("unsupported_file_type", "Upload a file with a .csv extension.", 415)
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type and media_type not in CSV_MEDIA_TYPES:
        raise InputError("unsupported_file_type", "The supplied media type is not CSV.", 415)
    return filename


def _check_quoting(text: str) -> None:
    # csv.reader(strict=True) still accepts quotes inside unquoted fields.
    state = "start"
    for char in text:
        if state == "quoted":
            if char == '"':
                state = "after_quote"
        elif state == "after_quote":
            if char == '"':
                state = "quoted"
            elif char in ",\r\n":
                state = "start"
            else:
                raise InputError("malformed_csv", "Unexpected text after a quoted field.")
        elif char == '"':
            if state != "start":
                raise InputError("malformed_csv", "Quotes must enclose the entire field.")
            state = "quoted"
        elif char in ",\r\n":
            state = "start"
        else:
            state = "unquoted"
    if state == "quoted":
        raise InputError("malformed_csv", "A quoted field is not closed.")


def parse_csv(
    content: bytes, filename: str | None, settings: Settings,
    content_type: str | None = "text/csv",
) -> ParsedCsv:
    original_filename = validate_file_type(filename, content_type)
    if len(content) > settings.max_upload_bytes:
        raise InputError("upload_too_large", "The file exceeds the upload byte limit.", 413,
                         {"max_upload_bytes": settings.max_upload_bytes})
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError("unsupported_encoding", "CSV must use UTF-8, with an optional BOM.", 415) from exc
    if not text.strip():
        raise InputError("empty_file", "The CSV file is empty.")
    if "\x00" in text:
        raise InputError("unsupported_encoding", "CSV must not contain NUL characters.", 415)
    _check_quoting(text)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    rows: list[tuple[str, ...]] = []
    try:
        headers = next(reader)
        if not headers or any(is_missing(header) for header in headers):
            raise InputError("blank_header", "Every column must have a nonblank header.")
        if len(set(headers)) != len(headers):
            raise InputError("duplicate_header", "Column headers must be unique.")
        for record_number, row in enumerate(reader, start=1):
            if record_number > settings.max_rows:
                raise InputError("too_many_rows", "The CSV exceeds the parsed-record limit.", 413,
                                 {"max_rows": settings.max_rows})
            if len(row) != len(headers):
                raise InputError("malformed_row", "A record has a different number of fields than the header.",
                                 details={"record_number": record_number, "expected_fields": len(headers),
                                          "actual_fields": len(row)})
            rows.append(tuple(row))
    except csv.Error as exc:
        raise InputError("malformed_csv", "CSV quoting or record syntax is invalid.") from exc
    if not rows:
        raise InputError("zero_rows", "The CSV contains a header but no data records.")
    metadata = DatasetMetadata(
        original_filename=original_filename, content_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content), row_count=len(rows), column_count=len(headers), headers=headers,
    )
    return ParsedCsv(metadata=metadata, records=tuple(rows))

