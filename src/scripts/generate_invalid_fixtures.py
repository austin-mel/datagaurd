from pathlib import Path


def main() -> None:
    directory = Path("output/manual-fixtures")
    directory.mkdir(parents=True, exist_ok=True)
    cases = {
        "empty.csv": b"",
        "zero_rows.csv": b"a,b\n",
        "blank_header.csv": b"a, \n1,2\n",
        "duplicate_header.csv": b"a,a\n1,2\n",
        "malformed_row.csv": b"a,b\n1\n",
        "malformed_quote.csv": b'a\n"unterminated',
        "unsupported.txt": b"a\n1\n",
        "invalid_utf8.csv": b"a\n\xff\n",
        "too_many_rows.csv": b"a\n" + b"1\n" * 50_001,
        "oversized.csv": b"a\n" + b"x" * 10_485_759,
        "bom.csv": b"\xef\xbb\xbfid,name\n001,Example\n",
        "missing_columns.csv": b"facility_name\nExample\n",
    }
    for name, content in cases.items():
        (directory / name).write_bytes(content)
    print(f"Wrote {len(cases)} Swagger input cases to {directory}")


if __name__ == "__main__":
    main()

