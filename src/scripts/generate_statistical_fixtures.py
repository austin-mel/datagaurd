import argparse
import csv
import io
from pathlib import Path

from src.scripts.generate_fixtures import HEADERS


def encode(rows: list[list[str]], headers: list[str] = HEADERS) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def generate() -> dict[str, bytes]:
    rows = [[f"FAC-{number:06d}", f"Fictional Facility {number:03d}", "Alder" if number <= 20 else "Birch",
             "Clinic", "Active", str(40 + (number - 1) % 20), "2026-10-01"] for number in range(1, 41)]
    outlier = [row.copy() for row in rows]
    outlier[-1][5] = "100"
    shifted = [row.copy() for row in rows]
    shifted.extend([[f"FAC-{number:06d}", f"Fictional Facility {number:03d}", "Birch", "Clinic", "Active",
                     str(40 + (number - 1) % 20), "2026-10-01"] for number in range(41, 52)])
    for number, row in enumerate(shifted):
        row[2] = "Alder" if number < 40 else "Birch"
        if number < 4:
            row[4] = ""
    schema = [row[:5] + ["unparseable"] + row[6:] + ["new field"] for row in rows]
    return {"baseline.csv": encode(rows), "outlier.csv": encode(outlier),
            "shifted.csv": encode(shifted), "schema.csv": encode(schema, HEADERS + ["notes"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reproducible schema and statistical fixtures.")
    parser.add_argument("--output-dir", type=Path, default=Path("output/statistical-fixtures"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in generate().items():
        (args.output_dir / name).write_bytes(content)


if __name__ == "__main__":
    main()
