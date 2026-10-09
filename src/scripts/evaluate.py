import argparse
import json
from collections import Counter

from src.rules import load_rules
from src.schemas import Finding
from src.scripts.generate_fixtures import REFERENCE_DATE, generate
from src.services.tabular import parse_dataset
from src.services.validation import check_dataset
from src.settings import PROJECT_ROOT, Settings

Detection = tuple[str, int | None]


def detections(findings: list[Finding]) -> set[Detection]:
    result: set[Detection] = set()
    for finding in findings:
        if finding.category != "validation":
            continue
        if finding.affected_record_numbers:
            result.update((finding.rule_id, number) for number in finding.affected_record_numbers)
        else:
            result.add((finding.rule_id, None))
    return result


def scores(expected: set[Detection], actual: set[Detection]) -> dict[str, int | float | None]:
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def evaluate(rows: int = 5000) -> dict[str, object]:
    settings = Settings(_env_file=None, reference_date=REFERENCE_DATE, max_rows=max(rows, 50_000),
                        rules_path=PROJECT_ROOT / "config" / "facilities.yaml")
    rules = load_rules(settings.rules_path)
    clean, dirty, manifest = generate(rows)
    expected: set[Detection] = {(entry["rule_id"], entry["record_number"]) for entry in json.loads(manifest)["errors"]}
    dirty_result = check_dataset(parse_dataset(dirty, "dirty.csv", settings), rules, settings)
    clean_result = check_dataset(parse_dataset(clean, "clean.csv", settings), rules, settings)
    actual = detections(dirty_result.findings)
    return {"rows": rows, "reference_date": REFERENCE_DATE.isoformat(), "implementation_version": dirty_result.implementation_version,
            "configuration_sha256": dirty_result.configuration_sha256, "settings": dirty_result.settings_snapshot,
            "expected_errors": len(expected), "detected_errors": len(actual),
            "expected_by_rule": dict(sorted(Counter(rule for rule, _ in expected).items())),
            "detected_by_rule": dict(sorted(Counter(rule for rule, _ in actual).items())),
            "dirty": scores(expected, actual), "clean": scores(set(), detections(clean_result.findings)),
            "statistical_findings_excluded": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate validation against a deterministic error manifest.")
    parser.add_argument("--rows", type=int, default=5000)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.rows), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
