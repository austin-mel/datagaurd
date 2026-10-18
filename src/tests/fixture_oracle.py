"""Independent expected findings for the current numeric-constraint contract."""
import json
from datetime import date

from src.scripts.generate_fixtures import DEFAULT_SEED, REFERENCE_DATE, generate


def validation_fixture(row_count: int = 150, seed: int = DEFAULT_SEED,
                       reference_date: date = REFERENCE_DATE) -> tuple[bytes, bytes, bytes]:
    clean, dirty, manifest_bytes = generate(row_count, seed, reference_date)
    manifest = json.loads(manifest_bytes)
    # The shipped manifest lists the 21 injected errors. Numeric constraints now
    # additionally reject the three nonnumeric values; do not derive this from
    # the validator being tested, or change the production demo data to run tests.
    manifest["errors"].extend({"rule_id": "FAC_SCORE_RANGE", "record_number": number,
                               "column": "inspection_score"} for number in (10, 17, 19))
    return clean, dirty, json.dumps(manifest).encode("utf-8")
