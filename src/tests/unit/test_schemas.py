from typing import Any

import pytest
from pydantic import ValidationError

from src.schemas import (
    ApprovalRequest, CellReviewRequest, RemediationRequest, RejectionRequest,
    ReplaceCellAction, ReviewRequest, VersionReviewState,
)
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("decision", ["accepted_as_is", "dismissed"])
@pytest.mark.parametrize("reason", [None, "", " \t\n"])
def test_acceptance_and_dismissal_require_explanation(decision: str, reason: str | None) -> None:
    with pytest.raises(ValidationError):
        ReviewRequest.model_validate({"decision": decision, "reason": reason})


@pytest.mark.parametrize("decision", ["needs_correction", "accepted_as_is", "dismissed"])
def test_review_reason_is_trimmed(decision: str) -> None:
    request = ReviewRequest.model_validate({"decision": decision, "reason": "  checked source \n"})
    assert request.reason == "checked source"


def test_correction_reason_is_optional_and_unknown_fields_are_rejected() -> None:
    assert ReviewRequest(decision="needs_correction", reason="  ").reason is None
    with pytest.raises(ValidationError):
        ReviewRequest.model_validate({"decision": "needs_correction", "actor": "forged"})


@pytest.mark.parametrize("value", [None, "0", " padded ", "line\nbreak", "é"])
def test_cell_replacement_preserves_exact_value(value: str | None) -> None:
    assert ReplaceCellAction(type="replace", value=value).value == value


@pytest.mark.parametrize("value", ["", " \n\t", "abc\x00def"])
def test_cell_replacement_rejects_blank_and_nul(value: str) -> None:
    with pytest.raises(ValidationError):
        ReplaceCellAction(type="replace", value=value)


@pytest.mark.parametrize("action", [{"type": "replace", "value": None}, {"type": "delete-row"}, {"type": "ignore"}])
def test_cell_review_action_discriminator(action: dict[str, Any]) -> None:
    request = CellReviewRequest.model_validate({"version": "v1", "groupId": "group", "rowNumber": 1,
                                               "scope": "all", "action": action})
    assert request.action.type == action["type"]


@pytest.mark.parametrize("change", [
    {"version": ""}, {"rowNumber": 0}, {"rowNumber": -1}, {"scope": "some"},
    {"action": {"type": "delete"}}, {"action": {"type": "replace"}},
    {"action": {"type": "delete-row", "value": "x"}},
    {"action": {"type": "ignore", "reason": "x" * 2001}},
])
def test_invalid_cell_reviews(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CellReviewRequest.model_validate({"version": "v1", "groupId": "group", "rowNumber": 1,
                                          "scope": "one", "action": {"type": "ignore"}, **change})


@pytest.mark.parametrize("change", [
    {"reason": " "}, {"reason": "x" * 2001}, {"replacement": "\x00"},
    {"source_sha256": "A" * 64}, {"source_sha256": "a" * 63}, {"source_sha256": "g" * 64},
    {"column": ""}, {"records": []}, {"action": "delete"},
    {"records": [{"record_number": 0, "expected_value": "old"}]},
    {"records": [{"record_number": 1, "expected_value": "a"}, {"record_number": 1, "expected_value": "b"}]},
])
def test_invalid_remediation_requests(remediation_payload: dict[str, Any], change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RemediationRequest.model_validate({**remediation_payload, **change})


def test_remediation_allows_empty_replacement_and_trims_reason(remediation_payload: dict[str, Any]) -> None:
    request = RemediationRequest.model_validate({**remediation_payload, "replacement": "", "reason": " checked "})
    assert request.replacement == ""
    assert request.reason == "checked"


@pytest.mark.parametrize("length", [0, 31, 33])
def test_approval_token_length(length: int) -> None:
    with pytest.raises(ValidationError):
        ApprovalRequest(preview_token="a" * length)


def test_approval_and_rejection() -> None:
    assert ApprovalRequest(preview_token="a" * 32).preview_token == "a" * 32
    assert RejectionRequest(reason="  wrong source  ").reason == "wrong source"
    with pytest.raises(ValidationError):
        RejectionRequest(reason=" \t")


def test_review_state_mutable_defaults_are_independent() -> None:
    first, second = VersionReviewState(), VersionReviewState()
    first.row_ids.append(42)
    assert second.row_ids == []
    assert first.ignored is not second.ignored


@pytest.mark.parametrize(("field", "value"), [
    ("max_rows", 0), ("max_columns", -1), ("max_cells", 0), ("max_upload_bytes", 0),
    ("max_decoded_bytes", 0), ("statistical_min_samples", 0), ("iqr_multiplier", -1),
    ("iqr_multiplier", float("nan")), ("row_count_change_percentage", float("inf")),
    ("missingness_increase_percentage_points", 101), ("category_share_change_percentage_points", -1),
    ("finding_sample_size", 1001), ("top_category_count", 0), ("actor", ""),
])
def test_settings_reject_invalid_limits(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
