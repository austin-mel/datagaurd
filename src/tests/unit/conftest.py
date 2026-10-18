from typing import Any

import pytest

from src.rules import RuleSet


@pytest.fixture
def simple_rules() -> RuleSet:
    return RuleSet.model_validate({
        "schema_version": 1, "name": "Orders", "structural_rule_id": "COLUMNS",
        "required_columns": ["id", "value"], "identifier_column": "id",
        "rules": [
            {"id": "ID_REQUIRED", "kind": "required", "column": "id", "explanation": "ID required."},
            {"id": "ID_UNIQUE", "kind": "unique", "column": "id", "explanation": "ID unique."},
            {"id": "VALUE_REQUIRED", "kind": "required", "column": "value", "explanation": "Value required."},
        ],
    })


@pytest.fixture
def remediation_payload() -> dict[str, Any]:
    return {"source_version_id": "version-1", "source_sha256": "a" * 64,
            "column": "value", "records": [{"record_number": 1, "expected_value": "old"}],
            "replacement": "new", "reason": "Verified against source"}
