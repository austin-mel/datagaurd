from src.schemas import Finding
from src.scripts.evaluate import detections, evaluate, scores


def test_five_thousand_record_manifest() -> None:
    result = evaluate()
    assert result["rows"] == 5000
    assert result["expected_errors"] == result["detected_errors"] == 21
    assert result["expected_by_rule"] == result["detected_by_rule"]
    assert result["dirty"] == {"true_positive": 21, "false_positive": 0, "false_negative": 0,
                               "precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert result["clean"] == {"true_positive": 0, "false_positive": 0, "false_negative": 0,
                               "precision": None, "recall": None, "f1": None}


def test_structural_keys_statistics_exclusion_and_zero_denominators() -> None:
    structural = Finding(rule_id="STRUCTURE", column=None, severity="error", explanation="Missing column.",
                         observed_result={}, threshold={}, affected_count=0, record_samples=[], affected_record_numbers=[])
    statistical = structural.model_copy(update={"rule_id": "STAT_ROW_COUNT", "category": "statistical", "severity": "warning"})
    assert detections([structural, statistical]) == {("STRUCTURE", None)}
    assert scores({("STRUCTURE", None)}, set()) == {"true_positive": 0, "false_positive": 0, "false_negative": 1,
                                                     "precision": None, "recall": 0.0, "f1": 0.0}
