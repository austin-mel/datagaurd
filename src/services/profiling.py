from typing import Literal

import pandas as pd

from src.rules import DateRule, RuleSet
from src.schemas import CategoryCount, ColumnProfile, DatasetProfile
from src.services.csv_parser import ParsedCsv, is_missing
from src.services.value_parsing import parse_date, parse_number


def profile_dataset(dataset: ParsedCsv, rules: RuleSet, top_count: int = 5) -> DatasetProfile:
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
        for value in populated:
            number = parse_number(value)
            if number is not None:
                numeric.append(number)
                observed.add("integer" if number.is_integer() else "number")
            elif parse_date(value, date_formats.get(column, ["%Y-%m-%d"])) is not None:
                observed.add("date")
            else:
                observed.add("text")
        profiles.append(ColumnProfile(
            column=column, observed_types=sorted(observed), missing_count=len(values) - len(populated),
            nonmissing_count=len(populated), distinct_count=int(series.nunique()), numeric_count=len(numeric),
            numeric_min=min(numeric) if numeric else None, numeric_max=max(numeric) if numeric else None,
            top_categories=[CategoryCount(value=value, count=count) for value, count in frequencies[:top_count]],
        ))
    return DatasetProfile(row_count=len(dataset.records), column_count=len(profiles), columns=profiles)

