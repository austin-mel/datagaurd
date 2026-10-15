import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from typing import assert_never

from pydantic import JsonValue

from src.rules import (
    AllowedRule, DateBoundRule, DateBetweenRule, NumericRule, PatternRule, RangeRule, MinRule, MaxRule,
    RequiredRule, RuleSet, UniqueRule,
)
from src.schemas import CheckResponse, Finding, RecordSample, RuleResult, VersionReviewState
from src.services.cell_review import ignored_members
from src.services.tabular import ParsedDataset, is_missing
from src.services.profiling import profile_dataset
from src.services.metrics import quality_metrics
from src.services.identifiers import identifier_column, resolved_rules
from src.services.statistics import analyze
from src.services.value_parsing import parse_date, parse_number
from src.services.rule_syntax import portable_pattern
from src.settings import Settings

IMPLEMENTATION_VERSION = "tabular-validation/2.2.0"


def check_dataset(dataset: ParsedDataset, rules: RuleSet, settings: Settings,
                  baseline: ParsedDataset | None = None, baseline_id: str | None = None,
                  review_state: VersionReviewState | None = None) -> CheckResponse:
    if rules.statistics:
        settings = settings.model_copy(update=rules.statistics.model_dump())
    effective, identifier_reason = resolved_rules(rules, dataset.metadata.headers)
    ignored = ignored_members(dataset, rules, review_state or VersionReviewState())
    reference_date = settings.reference_date or date.today()
    findings: list[Finding] = []
    outcomes: list[RuleResult] = []
    missing_columns = [column for column in effective.required_columns if column not in dataset.metadata.headers]
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
            threshold={"required_columns": list(effective.required_columns)},
            affected_count=0, record_samples=[], affected_record_numbers=[],
        ))

    numeric_values: dict[str, dict[int, float]] = {}
    if rules.identifier_policy == "auto" and identifier_reason:
        outcomes.extend(RuleResult(rule_id=identity, column=None, status="skipped", evaluated_count=0,
                                   skipped_count=len(dataset.records), reason=identifier_reason)
                        for identity in ("GENERIC_ID_REQUIRED", "GENERIC_ID_UNIQUE"))
    for rule in effective.rules:
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
            pattern = re.compile(portable_pattern(rule.pattern), re.ASCII)
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
            affected.extend(number for number in nonmissing if number not in parsed_numbers)
            candidates = list(nonmissing)
            threshold = {"minimum": rule.minimum, "maximum": rule.maximum, "inclusive": True}
            reason = f"Missing values or failed prerequisite {rule.prerequisite}."
        elif isinstance(rule, (MinRule, MaxRule)):
            parsed_numbers = numeric_values[rule.prerequisite]
            candidates = list(parsed_numbers)
            if isinstance(rule, MinRule):
                affected = [number for number, value in parsed_numbers.items() if value < rule.minimum]
                threshold = {"minimum": rule.minimum, "inclusive": True}
            else:
                affected = [number for number, value in parsed_numbers.items() if value > rule.maximum]
                threshold = {"maximum": rule.maximum, "inclusive": True}
            affected.extend(number for number in nonmissing if number not in parsed_numbers)
            candidates = list(nonmissing)
            reason = f"Missing values or failed prerequisite {rule.prerequisite}."
        elif isinstance(rule, (DateBoundRule, DateBetweenRule)):
            parsed_dates = {number: parsed_day for number, value in nonmissing.items()
                            if (parsed_day := parse_date(value, rule.formats)) is not None}
            affected = [number for number in nonmissing if number not in parsed_dates]
            if isinstance(rule, DateBetweenRule):
                first, last = date.fromisoformat(rule.start_date), date.fromisoformat(rule.end_date)
                affected.extend(number for number, value in parsed_dates.items() if not first <= value <= last)
                threshold = {"start_date": rule.start_date, "end_date": rule.end_date, "inclusive": True}
            else:
                selected = date.fromisoformat(rule.date)
                affected.extend(number for number, value in parsed_dates.items()
                                if (value > selected if rule.kind == "on_or_before_date" else
                                    value < selected if rule.kind == "on_or_after_date" else
                                    value >= selected if rule.kind == "before_date" else value <= selected))
                threshold = {"date": rule.date, "condition": rule.kind}
            threshold["formats"] = list(rule.formats)
            affected.sort()
        else:
            assert_never(rule)
        exempt = ignored.get(("violation", rule.id, rule.column), set())
        if isinstance(rule, NumericRule) and rule.generated_for:
            exempt = ignored.get(("violation", rule.generated_for, rule.column), set())
        affected = sorted(number for number in affected if number not in exempt)
        candidates = [number for number in candidates if number not in exempt]
        skipped = len(values) - len(candidates)
        outcomes.append(RuleResult(
            rule_id=rule.id, column=rule.column,
            status="failed" if affected else ("passed" if candidates else "skipped"),
            evaluated_count=len(candidates), skipped_count=skipped,
            reason=reason if skipped else None,
        ))
        if affected and not (isinstance(rule, NumericRule) and rule.generated_for):
            observed["failure_count"] = len(affected)
            findings.append(Finding(
                rule_id=rule.id, column=rule.column, severity=rule.severity, explanation=rule.explanation,
                observed_result=observed, threshold=threshold, affected_count=len(affected),
                record_samples=[RecordSample(record_number=number, value=values[number - 1])
                                for number in affected[:settings.finding_sample_size]],
                affected_record_numbers=affected,
            ))

    configuration_bytes = json.dumps(rules.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    profile = profile_dataset(dataset, rules, settings.top_category_count)
    statistical_findings, analysis_results = analyze(dataset, profile, effective, settings, baseline, baseline_id)
    for finding in statistical_findings:
        exempt = ignored.get(("warning", finding.rule_id, finding.column or ""), set())
        if exempt and finding.affected_record_numbers:
            members = [number for number in finding.affected_record_numbers if number not in exempt]
            membership = set(members)
            ignored_count = finding.affected_count - len(members)
            evidence = {**finding.observed_result, "ignored_count": ignored_count,
                        "detected_outlier_count": finding.affected_count, "outlier_count": len(members)}
            for analysis in analysis_results:
                if analysis.check_id == finding.rule_id and analysis.column == finding.column:
                    analysis.observed_result = evidence
                    analysis.status = "review_required" if members else "passed"
            finding = finding.model_copy(update={"affected_record_numbers": members, "affected_count": len(members),
                "observed_result": evidence,
                "record_samples": [sample for sample in finding.record_samples if sample.record_number in membership]})
            if not members:
                continue
        findings.append(finding)
    return CheckResponse(
        metric_semantics="row-based-v1",
        metadata=dataset.metadata, profile=profile, baseline_id=baseline_id, analysis_results=analysis_results,
        metrics=quality_metrics(dataset, rules, findings,
            {rule.id: ignored.get(("violation", rule.id, rule.column), set()) for rule in effective.rules if isinstance(rule, UniqueRule)}),
        resolved_identifier_column=identifier_column(effective, dataset.metadata.headers)[0],
        validation_status="failed" if any(f.category == "validation" and f.severity == "error" for f in findings) else "passed",
        findings=findings, rule_results=outcomes, reference_date=reference_date,
        checked_at=datetime.now(timezone.utc), actor=settings.actor, implementation_version=IMPLEMENTATION_VERSION,
        configuration=rules.model_copy(deep=True), configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        settings_snapshot=settings.model_dump(mode="json", exclude={"rules_path", "storage_dir", "reference_date", "actor"}),
    )

