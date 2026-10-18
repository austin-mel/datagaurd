from datetime import date

import pytest

from src.services.value_parsing import parse_date, parse_number

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("text", "expected"), [
    ("0", 0), ("-0", 0), ("+12", 12), ("0012", 12), ("  -1.25\t", -1.25),
    (".5", .5), ("1.", 1), ("1e3", 1000), ("-2.5E-2", -.025), ("1e-9999", 0),
])
def test_finite_decimal_numbers(text: str, expected: float) -> None:
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", [
    "", " \t", ".", "+", "--1", "1 2", "1,000", "1_000", "0xff", "1e", "1e+",
    "NaN", "nan", "Infinity", "-inf", "1e309", "-1e309", "１２", "١٢", "12%", "$1",
])
def test_invalid_or_nonfinite_numbers(text: str) -> None:
    assert parse_number(text) is None


@pytest.mark.parametrize(("text", "formats", "expected"), [
    ("2024-02-29", ["%Y-%m-%d"], date(2024, 2, 29)),
    (" 2026-10-07\n", ["%Y-%m-%d"], date(2026, 10, 7)),
    ("10/07/2026", ["%m/%d/%Y", "%d/%m/%Y"], date(2026, 10, 7)),
    ("10/07/2026", ["%d/%m/%Y", "%m/%d/%Y"], date(2026, 7, 10)),
    ("31/12/2026", ["%m/%d/%Y", "%d/%m/%Y"], date(2026, 12, 31)),
])
def test_dates_respect_format_order(text: str, formats: list[str], expected: date) -> None:
    assert parse_date(text, formats) == expected


@pytest.mark.parametrize("text", [
    "", "today", "2023-02-29", "2026-02-30", "2026-13-01", "2026-00-01",
    "2026-1-07", "2026-10-7", "2026-10-07T00:00:00", "07/10/2026",
])
def test_dates_require_exact_calendar_format(text: str) -> None:
    assert parse_date(text, ["%Y-%m-%d"]) is None


def test_no_date_formats_means_no_match() -> None:
    assert parse_date("2026-10-07", []) is None
