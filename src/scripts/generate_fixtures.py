"""Generate fictional facilities and an independently specified error oracle."""

import argparse
import csv
import io
import json
import random
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SEED = 20261007
REFERENCE_DATE = date(2026, 10, 7)
HEADERS = ["facility_id", "facility_name", "county", "facility_type", "status",
           "inspection_score", "inspection_date"]
COUNTIES = ["Alder", "Birch", "Cedar", "Maple"]


def generate(row_count: int = 150, seed: int = DEFAULT_SEED,
             reference_date: date = REFERENCE_DATE) -> tuple[bytes, bytes, bytes]:
    if not 20 <= row_count <= 999_999:
        raise ValueError("row_count must be between 20 and 999999 for the complete error fixture")
    rng = random.Random(seed)
    clean: list[list[str]] = []
    for number in range(1, row_count + 1):
        clean.append([
            f"FAC-{number:06d}", f"Fictional Facility {number:03d}", rng.choice(COUNTIES),
            rng.choice(["Clinic", "Laboratory", "Care Center"]), rng.choice(["Active", "Inactive"]),
            str(rng.randint(0, 100)), (reference_date - timedelta(days=rng.randint(0, 730))).isoformat(),
        ])
    dirty = [row.copy() for row in clean]
    errors: list[dict[str, str | int]] = []

    def inject(record: int, column: str, value: str, rule_id: str) -> None:
        dirty[record - 1][HEADERS.index(column)] = value
        errors.append({"rule_id": rule_id, "record_number": record, "column": column})

    inject(1, "facility_id", "", "FAC_ID_REQUIRED")
    inject(2, "facility_id", "   ", "FAC_ID_REQUIRED")
    inject(4, "facility_id", dirty[2][0], "FAC_ID_UNIQUE")
    errors.append({"rule_id": "FAC_ID_UNIQUE", "record_number": 3, "column": "facility_id"})
    inject(5, "facility_name", "", "FAC_NAME_REQUIRED")
    inject(6, "facility_name", " \t ", "FAC_NAME_REQUIRED")
    inject(7, "county", "Unknown County", "FAC_COUNTY_ALLOWED")
    inject(8, "inspection_score", "101", "FAC_SCORE_RANGE")
    inject(9, "inspection_score", "-1", "FAC_SCORE_RANGE")
    inject(10, "inspection_score", "not-a-number", "FAC_SCORE_NUMERIC")
    inject(11, "inspection_date", "2026-02-30", "FAC_DATE_PARSE")
    inject(12, "inspection_date", (reference_date + timedelta(days=1)).isoformat(), "FAC_DATE_NOT_FUTURE")
    # Intentionally overlap two distinct rules on one record.
    inject(13, "facility_id", "BAD-000013", "FAC_ID_FORMAT")
    inject(13, "county", "Unknown County", "FAC_COUNTY_ALLOWED")
    inject(14, "inspection_score", "", "FAC_SCORE_REQUIRED")
    inject(15, "inspection_date", "", "FAC_DATE_REQUIRED")
    inject(16, "county", "  ", "FAC_COUNTY_REQUIRED")
    inject(17, "inspection_score", "NaN", "FAC_SCORE_NUMERIC")
    inject(18, "inspection_date", "10/07/2026", "FAC_DATE_PARSE")
    inject(19, "inspection_score", "Infinity", "FAC_SCORE_NUMERIC")
    inject(20, "facility_id", dirty[2][0], "FAC_ID_UNIQUE")

    def encode(rows: list[list[str]]) -> bytes:
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(HEADERS)
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")

    manifest = {
        "schema_version": 1, "seed": seed, "reference_date": reference_date.isoformat(),
        "row_count": row_count, "record_number_base": 1,
        "errors": sorted(errors, key=lambda error: (int(error["record_number"]), str(error["rule_id"]))),
    }
    return encode(clean), encode(dirty), (json.dumps(manifest, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=150)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reference-date", type=date.fromisoformat, default=REFERENCE_DATE)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    try:
        outputs = generate(args.rows, args.seed, args.reference_date)
    except ValueError as exc:
        parser.error(str(exc))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in zip(
        ["facilities_clean.csv", "facilities_dirty.csv", "facilities_errors.json"], outputs, strict=True
    ):
        (args.output_dir / filename).write_bytes(content)
    print(f"Generated {args.rows} fictional records in {args.output_dir}")


if __name__ == "__main__":
    main()

