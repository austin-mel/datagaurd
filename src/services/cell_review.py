"""Complete cell groups and persistent, value/rule-scoped ignore decisions."""
import hashlib
import json
from collections import defaultdict
from typing import Literal

from src.rules import BaseRule, NumericRule, RuleSet
from src.schemas import CellReviewGroup, CheckResponse, ReviewedCell, VersionReviewState
from src.services.identifiers import resolved_rules
from src.services.tabular import ParsedDataset


def rule_signature(rule: BaseRule) -> str:
    document = json.dumps(rule.model_dump(mode="json", exclude={"id", "explanation"}),
                          sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(document.encode()).hexdigest()


def cell_value(value: str) -> str | None:
    return value if value != "" else None


def ignored_members(dataset: ParsedDataset, rules: RuleSet, state: VersionReviewState) -> dict[tuple[str, str, str], set[int]]:
    members: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    if not state.ignored:
        return members
    effective, _ = resolved_rules(rules, dataset.metadata.headers)
    signatures = {rule.id: rule_signature(rule) for rule in effective.rules}
    positions = {identity: number for number, identity in enumerate(state.row_ids, 1)} if state.row_ids else None
    columns = {name: index for index, name in enumerate(dataset.metadata.headers)}
    for ignored in state.ignored:
        number = positions.get(ignored.row_id) if positions is not None else ignored.row_id
        column = columns.get(ignored.column)
        if number is None or number < 1 or number > len(dataset.records) or column is None:
            continue
        if cell_value(dataset.records[number - 1][column]) != ignored.value:
            continue
        if ignored.kind == "violation" and signatures.get(ignored.rule_id) != ignored.signature:
            continue
        members[(ignored.kind, ignored.rule_id, ignored.column)].add(number)
    return members


def rule_type(rule: BaseRule) -> str:
    kind = getattr(rule, "kind", "")
    if kind == "pattern":
        return "regex"
    if kind == "allowed_values":
        return "allowed"
    if kind in {"before_date", "after_date", "on_or_before_date", "on_or_after_date", "between_dates"}:
        return "date"
    return str(kind)


def cell_groups(dataset: ParsedDataset, result: CheckResponse) -> list[CellReviewGroup]:
    effective, _ = resolved_rules(result.configuration, dataset.metadata.headers)
    rules = {rule.id: rule for rule in effective.rules}
    columns = {name: index for index, name in enumerate(dataset.metadata.headers)}
    identifier = columns.get(result.resolved_identifier_column or "")
    groups: dict[str, CellReviewGroup] = {}
    for finding in result.findings:
        if finding.column is None or finding.column not in columns:
            continue
        rule = rules.get(finding.rule_id)
        if isinstance(rule, NumericRule) and rule.generated_for:
            continue
        kind: Literal["violation", "warning"] = "violation" if finding.category == "validation" else "warning"
        column_index = columns[finding.column]
        for number in finding.affected_record_numbers:
            row = dataset.records[number - 1]
            value = cell_value(row[column_index])
            identity = json.dumps([kind, finding.rule_id, finding.column, value], ensure_ascii=False, separators=(",", ":"))
            if identity not in groups:
                groups[identity] = CellReviewGroup(id=identity, column=finding.column, ruleId=finding.rule_id,
                    rule=rule_type(rule) if rule else finding.rule_id, kind=kind,
                    reason=finding.explanation, currentValue=value, cells=[])
            groups[identity].cells.append(ReviewedCell(rowNumber=number,
                identifier=cell_value(row[identifier]) if identifier is not None else None))
    return list(groups.values())
