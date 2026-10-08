from collections import Counter
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from pydantic import JsonValue

from src.rules import NumericRule, RuleSet
from src.schemas import AnalysisResult, ColumnProfile, DatasetProfile, Finding, RecordSample
from src.services.tabular import ParsedDataset, is_missing
from src.services.profiling import finite, profile_dataset, quartile
from src.services.value_parsing import parse_number
from src.settings import Settings


def types(column: ColumnProfile) -> set[str]:
    return {"number" if value == "integer" else value for value in column.observed_types}


def exceeds(numerator: int, denominator: int, threshold: float) -> bool:
    return Fraction(100 * numerator, denominator) > Fraction(str(threshold))


def analyze(dataset: ParsedDataset, profile: DatasetProfile, rules: RuleSet, settings: Settings,
            baseline: ParsedDataset | None = None, baseline_id: str | None = None) -> tuple[list[Finding], list[AnalysisResult]]:
    findings: list[Finding] = []
    results: list[AnalysisResult] = []
    current = {column.column: column for column in profile.columns}
    previous = {column.column: column for column in profile_dataset(baseline, rules, settings.top_category_count).columns} if baseline else {}
    minimum = settings.statistical_min_samples

    def emit(check: str, column: str | None, explanation: str, *, flag: bool = False,
             reason: str | None = None, observed: dict[str, JsonValue] | None = None,
             threshold: dict[str, JsonValue] | None = None, members: list[int] | None = None,
             category: Literal["schema", "statistical"] = "statistical", comparative: bool = True) -> None:
        result = AnalysisResult(check_id=check, column=column, category=category,
                                status="not_evaluated" if reason else "review_required" if flag else "passed",
                                reason=reason, observed_result=observed or {}, threshold=threshold or {},
                                baseline_id=baseline_id if comparative else None)
        results.append(result)
        if flag and not reason:
            numbers = members or []
            values = dataset.column(column) if column is not None and numbers else []
            findings.append(Finding(
                rule_id=check, column=column, category=category, severity="warning", explanation=explanation,
                observed_result=result.observed_result, threshold=result.threshold, affected_count=len(numbers),
                affected_record_numbers=numbers, baseline_id=result.baseline_id,
                record_samples=[RecordSample(record_number=number, value=values[number - 1])
                                for number in numbers[:settings.finding_sample_size]],
            ))

    incompatible = {name for name in current.keys() & previous.keys()
                    if types(current[name]) and types(previous[name]) and types(current[name]) != types(previous[name])}
    added, removed = sorted(current.keys() - previous.keys()), sorted(previous.keys() - current.keys())
    emit("SCHEMA_COLUMNS", None, "Dataset columns or observed value types changed.", category="schema",
         reason=None if baseline else "No preceding version is available.",
         flag=bool(added or set(removed) - set(rules.required_columns) or incompatible) if baseline else False,
         observed={"added_columns": list(added) if baseline else [], "removed_columns": list(removed),
                   "incompatible_columns": [{"column": name, "baseline_types": list(sorted(types(previous[name]))),
                                              "current_types": list(sorted(types(current[name])))}
                                             for name in sorted(incompatible)]},
         threshold={"compatible_types_required": True, "required_columns": list(rules.required_columns)})

    old_rows, new_rows = len(baseline.records) if baseline else 0, len(dataset.records)
    emit("STAT_ROW_COUNT", None, "The record count changed beyond the configured threshold.",
         reason="No preceding version is available." if baseline is None else "The baseline has zero records." if old_rows == 0 else None,
         flag=exceeds(abs(new_rows - old_rows), old_rows, settings.row_count_change_percentage) if old_rows else False,
         observed={"baseline_rows": old_rows if baseline else None, "current_rows": new_rows,
                   "change_percentage": 100 * abs(new_rows - old_rows) / old_rows if old_rows else None},
         threshold={"change_percentage": settings.row_count_change_percentage, "comparison": "strictly_greater"})

    numeric_columns = {rule.column for rule in rules.rules if isinstance(rule, NumericRule)}
    declared_columns = {rule.column for rule in rules.rules}
    for name, column in current.items():
        numbers = {index: number for index, value in enumerate(dataset.column(name), 1)
                   if (number := parse_number(value)) is not None}
        numeric = name in numeric_columns or (name not in declared_columns and types(column) == {"number"})
        threshold: dict[str, JsonValue] = {"iqr_multiplier": settings.iqr_multiplier, "minimum_usable_values": minimum,
                                           "comparison": "strictly_outside"}
        observed: dict[str, JsonValue] = {"usable_values": len(numbers)}
        outliers: list[int] = []
        reason = None
        if not numeric:
            reason = "The column is not numeric."
        elif len(numbers) < minimum:
            reason = "Insufficient usable numeric values."
        else:
            ordered = sorted(numbers.values())
            q1, q3 = quartile(ordered, 1), quartile(ordered, 3)
            spread = q3 - q1
            lower, upper = q1 - Decimal(str(settings.iqr_multiplier)) * spread, q3 + Decimal(str(settings.iqr_multiplier)) * spread
            observed.update({"q1": float(q1), "q3": float(q3), "iqr": finite(float(spread)),
                             "lower_fence": finite(float(lower)), "upper_fence": finite(float(upper))})
            if spread == 0:
                reason = "The interquartile range is zero."
            elif any(observed[key] is None for key in ("iqr", "lower_fence", "upper_fence")):
                reason = "The fences exceed the supported finite numeric range."
            else:
                outliers = [index for index, number in numbers.items() if Decimal(str(number)) < lower or Decimal(str(number)) > upper]
        observed["outlier_count"] = len(outliers)
        emit("STAT_IQR", name, "Values lie outside the configured interquartile fences; review their validity.",
             flag=bool(outliers), reason=reason, observed=observed, threshold=threshold, members=outliers, comparative=False)

        old = previous.get(name)
        shared_reason = ("No preceding version is available." if baseline is None else
                         "The column is absent from the baseline." if old is None else
                         "The observed column types are incompatible." if name in incompatible else None)
        missing_reason = shared_reason or ("Both versions require the minimum record count."
                                          if min(old_rows, new_rows) < minimum else None)
        missing_numerator = column.missing_count * old_rows - (old.missing_count if old else 0) * new_rows
        denominator = old_rows * new_rows
        emit("STAT_MISSINGNESS", name, "The missing-value percentage increased beyond the configured threshold.",
             reason=missing_reason,
             flag=exceeds(missing_numerator, denominator, settings.missingness_increase_percentage_points) if denominator else False,
             observed={"baseline_missing": old.missing_count if old else None, "current_missing": column.missing_count,
                       "baseline_rows": old_rows if baseline else None, "current_rows": new_rows,
                       "increase_percentage_points": 100 * missing_numerator / denominator if denominator else None},
             threshold={"increase_percentage_points": settings.missingness_increase_percentage_points,
                        "minimum_records_per_version": minimum, "comparison": "strictly_greater"})

        category_reason = shared_reason
        combined_types = types(column) | (types(old) if old else set())
        if not category_reason and combined_types != {"text"}:
            category_reason = "Category comparisons require compatible text columns."
        if not category_reason and min(column.nonmissing_count, old.nonmissing_count if old else 0) < minimum:
            category_reason = "Both versions require the minimum nonmissing value count."
        evidence: dict[str, JsonValue] = {"current_nonmissing": column.nonmissing_count,
                                          "baseline_nonmissing": old.nonmissing_count if old else None}
        category_flag = False
        if category_reason is None and baseline is not None and old is not None:
            new_counts = Counter(value for value in dataset.column(name) if not is_missing(value))
            old_counts = Counter(value for value in baseline.column(name) if not is_missing(value))
            differences = {value: abs(new_counts[value] * old.nonmissing_count - old_counts[value] * column.nonmissing_count)
                           for value in new_counts.keys() | old_counts.keys()}
            largest = min(differences, key=lambda value: (-differences[value], value))
            denominator = column.nonmissing_count * old.nonmissing_count
            category_flag = exceeds(differences[largest], denominator, settings.category_share_change_percentage_points)
            evidence.update({"category": largest, "baseline_count": old_counts[largest], "current_count": new_counts[largest],
                             "maximum_change_percentage_points": 100 * differences[largest] / denominator})
        emit("STAT_CATEGORY_MIX", name, "The category distribution changed beyond the configured threshold.",
             reason=category_reason, flag=category_flag, observed=evidence,
             threshold={"share_change_percentage_points": settings.category_share_change_percentage_points,
                        "minimum_nonmissing_per_version": minimum, "comparison": "strictly_greater"})
    return findings, results
