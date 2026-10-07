from collections import Counter

from src.rules import RequiredRule, RuleSet
from src.schemas import Finding, Metric, QualityMetrics
from src.services.csv_parser import ParsedCsv, is_missing


def percentage(numerator: int, denominator: int) -> Metric:
    if denominator == 0:
        return Metric(numerator=numerator, denominator=0, reason="The denominator is zero.")
    return Metric(status="available", numerator=numerator, denominator=denominator,
                  percentage=100 * numerator / denominator, reason=None)


def quality_metrics(dataset: ParsedCsv, rules: RuleSet, findings: list[Finding]) -> QualityMetrics:
    if any(column not in dataset.metadata.headers for column in rules.required_columns):
        unavailable = Metric(reason="Required dataset structure is unavailable.")
        return QualityMetrics(completeness=unavailable, valid_row_rate=unavailable, duplicate_id_rate=unavailable)
    required_columns = {rule.column for rule in rules.rules if isinstance(rule, RequiredRule)}
    populated = sum(not is_missing(value) for column in required_columns for value in dataset.column(column))
    rows = len(dataset.records)
    invalid = {number for finding in findings if finding.category == "validation" and finding.severity == "error"
               for number in finding.affected_record_numbers}
    duplicate = Metric(reason="The facility_id column is unavailable.")
    if "facility_id" in dataset.metadata.headers:
        identifiers = [value for value in dataset.column("facility_id") if not is_missing(value)]
        counts = Counter(identifiers)
        duplicate = percentage(sum(count for count in counts.values() if count > 1), len(identifiers))
    return QualityMetrics(
        completeness=percentage(populated, rows * len(required_columns)),
        valid_row_rate=percentage(rows - len(invalid), rows), duplicate_id_rate=duplicate,
    )

