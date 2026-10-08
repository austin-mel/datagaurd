import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import assert_never

from pydantic import JsonValue

from src.rules import (
    AllowedRule, DateRule, NotFutureRule, NumericRule, PatternRule, RangeRule,
    RequiredRule, RuleSet, UniqueRule,
)
from src.schemas import CheckResponse, Finding, RecordSample, RuleResult
from src.services.tabular import ParsedDataset, is_missing
from src.services.profiling import profile_dataset
from src.services.metrics import quality_metrics
from src.services.value_parsing import parse_date, parse_number
from src.settings import Settings

IMPLEMENTATION_VERSION = "facilities-validation/1.1.0"


def check_dataset(dataset: ParsedDataset, rules: RuleSet, settings: Settings) -> CheckResponse:
    reference_date = settings.reference_date or date.today()
    findings: list[Finding] = []
    outcomes: list[RuleResult] = []
    missing_columns = [column for column in rules.required_columns if column not in dataset.metadata.headers]
    outcomes.append(RuleResult(
        rule_id=rules.structural_rule_id, column=None,
        status="failed" if missing_columns else "passed",
        evaluated_count=0, skipped_count=0,
    ))
    if missing_columns:
        findings.append(Finding(
            rule_id=rules.structural_rule_id, column=None, severity="error",
            explanation="All required columns must be present.",
            observed_result={"missing_columns": list(missing_columns)},
            threshold={"required_columns": list(rules.required_columns)},
            affected_count=0, record_samples=[], affected_record_numbers=[],
        ))

    numeric_values: dict[str, dict[int, float]] = {}
    date_values: dict[str, dict[int, date]] = {}
    for rule in rules.rules:
        if rule.column not in dataset.metadata.headers:
            outcomes.append(RuleResult(
                rule_id=rule.id, column=rule.column, status="skipped", evaluated_count=0,
                skipped_count=len(dataset.records), reason="Required column is missing.",
            ))
            continue
        values = dataset.column(rule.column)
        nonmissing = {number: value for number, value in enumerate(values, 1) if not is_missing(value)}
        candidates = list(nonmissing)
        affected: list[int]
        threshold: dict[str, JsonValue] = {}
        reason = "Missing values are evaluated by the required rule."
        observed: dict[str, JsonValue] = {}
        if isinstance(rule, RequiredRule):
            candidates = list(range(1, len(values) + 1))
            affected = [number for number, value in enumerate(values, 1) if is_missing(value)]
            threshold = {"required": True}
        elif isinstance(rule, UniqueRule):
            counts = Counter(nonmissing.values())
            affected = [number for number, value in nonmissing.items() if counts[value] > 1]
            threshold = {"maximum_occurrences": 1}
            observed["duplicate_group_count"] = sum(count > 1 for count in counts.values())
        elif isinstance(rule, PatternRule):
            pattern = re.compile(rule.pattern)
            affected = [number for number, value in nonmissing.items() if not pattern.fullmatch(value)]
            threshold = {"pattern": rule.pattern}
        elif isinstance(rule, AllowedRule):
            allowed = set(rule.values)
            affected = [number for number, value in nonmissing.items() if value not in allowed]
            threshold = {"allowed_values": list(rule.values)}
        elif isinstance(rule, NumericRule):
            parsed_numbers = {number: parsed for number, value in nonmissing.items()
                              if (parsed := parse_number(value)) is not None}
            numeric_values[rule.id] = parsed_numbers
            affected = [number for number in nonmissing if number not in parsed_numbers]
            threshold = {"finite_decimal_number": True}
        elif isinstance(rule, RangeRule):
            parsed_numbers = numeric_values[rule.prerequisite]
            candidates = list(parsed_numbers)
            affected = [number for number, value in parsed_numbers.items() if not rule.minimum <= value <= rule.maximum]
            threshold = {"minimum": rule.minimum, "maximum": rule.maximum, "inclusive": True}
            reason = f"Missing values or failed prerequisite {rule.prerequisite}."
        elif isinstance(rule, DateRule):
            parsed_dates = {number: parsed_day for number, value in nonmissing.items()
                            if (parsed_day := parse_date(value, rule.formats)) is not None}
            date_values[rule.id] = parsed_dates
            affected = [number for number in nonmissing if number not in parsed_dates]
            threshold = {"formats": list(rule.formats)}
        elif isinstance(rule, NotFutureRule):
            parsed_dates = date_values[rule.prerequisite]
            candidates = list(parsed_dates)
            affected = [number for number, value in parsed_dates.items() if value > reference_date]
            threshold = {"latest": reference_date.isoformat(), "inclusive": True}
            reason = f"Missing values or failed prerequisite {rule.prerequisite}."
        else:
            assert_never(rule)
        skipped = len(values) - len(candidates)
        outcomes.append(RuleResult(
            rule_id=rule.id, column=rule.column,
            status="failed" if affected else ("passed" if candidates else "skipped"),
            evaluated_count=len(candidates), skipped_count=skipped,
            reason=reason if skipped else None,
        ))
        if affected:
            observed["failure_count"] = len(affected)
            findings.append(Finding(
                rule_id=rule.id, column=rule.column, severity=rule.severity, explanation=rule.explanation,
                observed_result=observed, threshold=threshold, affected_count=len(affected),
                record_samples=[RecordSample(record_number=number, value=values[number - 1])
                                for number in affected[:settings.finding_sample_size]],
                affected_record_numbers=affected,
            ))

    configuration_bytes = json.dumps(rules.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return CheckResponse(
        metadata=dataset.metadata, profile=profile_dataset(dataset, rules, settings.top_category_count),
        metrics=quality_metrics(dataset, rules, findings),
        validation_status="failed" if any(f.severity == "error" for f in findings) else "passed",
        findings=findings, rule_results=outcomes, reference_date=reference_date,
        checked_at=datetime.now(timezone.utc), actor=settings.actor, implementation_version=IMPLEMENTATION_VERSION,
        configuration=rules.model_copy(deep=True), configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        settings_snapshot={"max_upload_bytes": settings.max_upload_bytes, "max_rows": settings.max_rows,
                           "finding_sample_size": settings.finding_sample_size,
                           "top_category_count": settings.top_category_count},
    )

