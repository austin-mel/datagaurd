import argparse
import csv
import io
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq

from src.scripts.generate_fixtures import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate equivalent fictional CSV, TSV, XLSX, and Parquet datasets.")
    parser.add_argument("--output-dir", type=Path, default=Path("output/formats"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in zip(("facilities_clean", "facilities_dirty"), generate()[:2], strict=True):
        rows = list(csv.reader(io.StringIO(content.decode())))
        (args.output_dir / f"{name}.csv").write_bytes(content)
        with (args.output_dir / f"{name}.tsv").open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream, delimiter="\t").writerows(rows)
        book = openpyxl.Workbook()
        sheet = book.active
        assert sheet is not None
        sheet.title = "Records"
        for row in rows:
            sheet.append(row)
        book.save(args.output_dir / f"{name}.xlsx")
        book.close()
        table = pa.table({header: [row[index] for row in rows[1:]] for index, header in enumerate(rows[0])})
        pq.write_table(table, args.output_dir / f"{name}.parquet")
    print(f"Generated eight files in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
