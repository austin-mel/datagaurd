from fastapi.testclient import TestClient

from src.rules import load_rules
from src.services.csv_parser import parse_csv
from src.services.profiling import profile_dataset
from src.settings import Settings


def test_profile_counts_and_nonfinite_values(settings: Settings) -> None:
    dataset = parse_csv(b'id,value,empty\n001,1,\n002,2.5, \n001,NaN,\n003, ,\n004,1,\n', "x.csv", settings)
    result = profile_dataset(dataset, load_rules(settings.rules_path), top_count=2)
    identifier, numeric, empty = result.columns
    assert identifier.distinct_count == 4
    assert identifier.top_categories[0].value == "001"
    assert identifier.top_categories[0].count == 2
    assert numeric.observed_types == ["integer", "number", "text"]
    assert numeric.missing_count == 1
    assert numeric.nonmissing_count == 4
    assert numeric.distinct_count == 3
    assert numeric.numeric_count == 3
    assert numeric.numeric_min == 1
    assert numeric.numeric_max == 2.5
    assert len(numeric.top_categories) == 2
    assert empty.missing_count == 5
    assert empty.distinct_count == 0
    assert empty.numeric_min is None
    assert empty.top_categories == []
    assert dataset.records[0][0] == "001"


def test_profile_api_and_date_types(client: TestClient) -> None:
    response = client.post("/datasets/profile", files={"file": ("x.csv", b"date\n2026-10-07\n2026-02-30\n", "text/csv")})
    assert response.status_code == 200
    assert response.json()["profile"]["columns"][0]["observed_types"] == ["date", "text"]

