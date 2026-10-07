from pathlib import Path

import pytest
from pydantic import ValidationError

from src.main import create_app
from src.rules import ConfigurationError, RuleSet, load_rules
from src.services.csv_parser import parse_csv
from src.services.validation import check_dataset
from src.settings import Settings


def test_python_to_yaml_regression(tmp_path: Path, settings: Settings) -> None:
    # Independent Python definition locks in the initial rule behavior from 3.2.
    definition = {
        "schema_version": 1, "name": "migration", "structural_rule_id": "STRUCTURE",
        "required_columns": ["score"], "rules": [
            {"id": "NUMERIC", "kind": "numeric", "column": "score", "explanation": "Must be numeric."},
            {"id": "RANGE", "kind": "range", "column": "score", "explanation": "Must be in range.",
             "prerequisite": "NUMERIC", "minimum": 0, "maximum": 100},
        ],
    }
    config_path = tmp_path / "rules.yaml"
    config_path.write_text(
        "schema_version: 1\nname: migration\nstructural_rule_id: STRUCTURE\nrequired_columns: [score]\nrules:\n"
        "  - {id: NUMERIC, kind: numeric, column: score, explanation: Must be numeric.}\n"
        "  - {id: RANGE, kind: range, column: score, explanation: Must be in range., prerequisite: NUMERIC, minimum: 0, maximum: 100}\n",
        encoding="utf-8",
    )
    dataset = parse_csv(b"score\n100\n101\ninvalid\n", "x.csv", settings)
    python_result = check_dataset(dataset, RuleSet.model_validate(definition), settings)
    yaml_result = check_dataset(dataset, load_rules(config_path), settings)
    assert python_result.model_dump(exclude={"checked_at"}) == yaml_result.model_dump(exclude={"checked_at"})


@pytest.mark.parametrize("content", [
    "schema_version: 1\nschema_version: 1", "[broken", "null", "rules: []",
    "!!python/object/apply:os.getcwd []",
])
def test_bad_yaml_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Invalid rule configuration"):
        load_rules(path)


@pytest.mark.parametrize("change", ["duplicate_id", "unknown_kind", "bad_regex", "bad_bounds", "bad_dependency", "unknown_column", "extra", "bad_date_format"])
def test_invalid_rule_configuration(settings: Settings, change: str) -> None:
    raw = load_rules(settings.rules_path).model_dump()
    if change == "duplicate_id":
        raw["rules"][1]["id"] = raw["rules"][0]["id"]
    elif change == "unknown_kind":
        raw["rules"][0]["kind"] = "unknown"
    elif change == "bad_regex":
        raw["rules"][2]["pattern"] = "["
    elif change == "bad_bounds":
        raw["rules"][8]["minimum"] = 101
    elif change == "bad_dependency":
        raw["rules"][8]["prerequisite"] = "FAC_DATE_PARSE"
    elif change == "unknown_column":
        raw["rules"][0]["column"] = "unknown"
    elif change == "extra":
        raw["rules"][0]["typo"] = True
    elif change == "bad_date_format":
        raw["rules"][10]["formats"] = ["%x"]
    with pytest.raises(ValidationError):
        RuleSet.model_validate(raw)


def test_bad_configuration_stops_startup(tmp_path: Path, settings: Settings) -> None:
    with pytest.raises(ConfigurationError):
        create_app(settings.model_copy(update={"rules_path": tmp_path / "missing.yaml"}))

