import math
from decimal import Decimal
from statistics import fmean, pstdev
from typing import Literal

import pandas as pd

from src.rules import DateRule, RuleSet
from src.schemas import CategoryCount, ColumnProfile, DatasetProfile
from src.services.tabular import ParsedDataset, is_missing
from src.services.value_parsing import parse_date, parse_number


def finite(value: float) -> float | None:
    return value if math.isfinite(value) else None


def quartile(ordered: list[float], quarter: int) -> Decimal:
    position = Decimal(len(ordered) - 1) * quarter / 4
    index = int(position)
    left = Decimal(str(ordered[index]))
    right = Decimal(str(ordered[min(index + 1, len(ordered) - 1)]))
    return left + (right - left) * (position - index)


def profile_dataset(dataset: ParsedDataset, rules: RuleSet, top_count: int = 5) -> DatasetProfile:
    profiles: list[ColumnProfile] = []
    date_formats = {rule.column: rule.formats for rule in rules.rules if isinstance(rule, DateRule)}
    for column in dataset.metadata.headers:
        values = dataset.column(column)
        populated = [value for value in values if not is_missing(value)]
        series = pd.Series(populated, dtype="object")
        frequencies = sorted(
            [(str(value), int(count)) for value, count in series.value_counts().items()],
            key=lambda pair: (-pair[1], pair[0]),
        )
        observed: set[Literal["integer", "number", "date", "text"]] = set()
        numeric: list[float] = []
        dates = []
        for value in populated:
            number = parse_number(value)
            if number is not None:
                numeric.append(number)
                observed.add("integer" if number.is_integer() else "number")
            elif (day := parse_date(value, date_formats.get(column, ["%Y-%m-%d"]))) is not None:
                dates.append(day)
                observed.add("date")
            else:
                observed.add("text")
        ordered = sorted(numeric)
        scale = max((abs(number) for number in numeric), default=0) or 1
        normalized = [number / scale for number in numeric]
        categories = [CategoryCount(value=value, count=count, percentage=100 * count / len(populated))
                      for value, count in frequencies]
        profiles.append(ColumnProfile(
            column=column, observed_types=sorted(observed), missing_count=len(values) - len(populated),
            nonmissing_count=len(populated), distinct_count=int(series.nunique()), numeric_count=len(numeric),
            numeric_min=min(numeric) if numeric else None, numeric_max=max(numeric) if numeric else None,
            top_categories=categories[:top_count], category_frequencies=categories,
            missing_percentage=100 * (len(values) - len(populated)) / len(values) if values else None,
            numeric_mean=finite(fmean(normalized) * scale) if numeric else None,
            numeric_stddev=finite(pstdev(normalized) * scale) if numeric else None,
            numeric_q1=float(quartile(ordered, 1)) if numeric else None,
            numeric_median=float(quartile(ordered, 2)) if numeric else None,
            numeric_q3=float(quartile(ordered, 3)) if numeric else None,
            date_count=len(dates), date_min=min(dates) if dates else None, date_max=max(dates) if dates else None,
        ))
    return DatasetProfile(row_count=len(dataset.records), column_count=len(profiles), columns=profiles)

