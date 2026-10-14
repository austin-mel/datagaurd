from collections import Counter

from src.rules import RuleSet, UniqueRule
from src.services.identifiers import identifier_column, resolved_rules
from src.schemas import Finding, Metric, QualityMetrics
from src.services.tabular import ParsedDataset, is_missing


def percentage(numerator: int, denominator: int) -> Metric:
    if denominator == 0:
        return Metric(numerator=numerator, denominator=0, reason="The denominator is zero.")
    return Metric(status="available", numerator=numerator, denominator=denominator,
                  percentage=100 * numerator / denominator, reason=None)


def quality_metrics(dataset: ParsedDataset, rules: RuleSet, findings: list[Finding]) -> QualityMetrics:
    rules, _ = resolved_rules(rules, dataset.metadata.headers)
    if any(column not in dataset.metadata.headers for column in rules.required_columns):
        unavailable = Metric(reason="Required dataset structure is unavailable.")
        return QualityMetrics(completeness=unavailable, valid_row_rate=unavailable,
                              duplicate_id_rate=unavailable, uniqueness=unavailable)
    populated = sum(all(not is_missing(value) for value in row) for row in dataset.records)
    rows = len(dataset.records)
    invalid = {number for finding in findings if finding.category == "validation" and finding.severity == "error"
               for number in finding.affected_record_numbers}
    identifier, reason = identifier_column(rules, dataset.metadata.headers)
    duplicate = Metric(reason=reason or "The identifier column is unavailable.")
    if identifier and identifier in dataset.metadata.headers:
        identifiers = [value for value in dataset.column(identifier) if not is_missing(value)]
        counts = Counter(identifiers)
        duplicate = percentage(sum(count for count in counts.values() if count > 1), len(identifiers))
    unique_columns = {rule.column for rule in rules.rules if isinstance(rule, UniqueRule)}
    uniqueness = Metric(reason="No enabled uniqueness rules are configured.")
    if unique_columns:
        nonunique: set[int] = set()
        for column in unique_columns:
            values = dataset.column(column)
            counts = Counter(value for value in values if not is_missing(value))
            nonunique.update(number for number, value in enumerate(values, 1)
                             if is_missing(value) or counts[value] != 1)
        uniqueness = percentage(rows - len(nonunique), rows)
    return QualityMetrics(
        completeness=percentage(populated, rows), uniqueness=uniqueness,
        valid_row_rate=percentage(rows - len(invalid), rows), duplicate_id_rate=duplicate,
    )

