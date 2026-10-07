import math
import re
from collections.abc import Sequence
from datetime import date, datetime

NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def parse_number(value: str) -> float | None:
    stripped = value.strip()
    if not NUMBER.fullmatch(stripped):
        return None
    number = float(stripped)
    return number if math.isfinite(number) else None


def parse_date(value: str, formats: Sequence[str]) -> date | None:
    stripped = value.strip()
    for date_format in formats:
        try:
            parsed = datetime.strptime(stripped, date_format).date()
            # strptime accepts non-zero-padded fields; our contract does not.
            if parsed.strftime(date_format) == stripped:
                return parsed
        except ValueError:
            continue
    return None

