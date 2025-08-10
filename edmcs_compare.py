#!/usr/bin/env python3

import argparse
import csv
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Iterable, Optional, Set


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two Oracle EDMCS viewpoint CSV extracts for missing nodes, "
            "parent mismatches, and property discrepancies."
        )
    )
    parser.add_argument("--left", required=True, help="Path to the LEFT (baseline) CSV extract")
    parser.add_argument("--right", required=True, help="Path to the RIGHT (target) CSV extract")
    parser.add_argument(
        "--key-cols",
        required=True,
        help=(
            "Comma-separated list of column names that uniquely identify a node (e.g. 'Node Code' or 'Node Name,Node Code')."
        ),
    )
    parser.add_argument(
        "--parent-col",
        default=None,
        help=(
            "Name of the parent column to compare (e.g. 'Parent Code' or 'Parent Name'). "
            "If omitted or not present, parent comparison is skipped."
        ),
    )
    parser.add_argument(
        "--compare-cols",
        default="auto",
        help=(
            "Comma-separated list of property columns to compare. "
            "Use 'auto' to compare the intersection of columns (excluding key and parent and ignored columns)."
        ),
    )
    parser.add_argument(
        "--ignore-cols",
        default="Level,Display Order,Is Leaf,Leaf,Action,Occurrence,Request ID,Request,Change Action,Change Reason,Change Note",
        help="Comma-separated list of columns to ignore during 'auto' comparison.",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter character. Default is ','.",
    )
    parser.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Treat string comparisons as case-insensitive (values are casefolded).",
    )
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="Do not trim whitespace before comparisons. By default whitespace is stripped.",
    )
    parser.add_argument(
        "--na-equal",
        action="store_true",
        help="Treat NA/blank values as equal when both sides are missing/blank.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write result CSV files. Defaults to current directory.",
    )
    return parser.parse_args()


def normalize_value(value: Optional[str], *, trim: bool, case_insensitive: bool) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value
        if trim:
            v = v.strip()
        if case_insensitive:
            v = v.casefold()
        return v
    return value  # type: ignore[return-value]


def read_csv_as_records(
    path: str,
    *,
    delimiter: str,
) -> Tuple[List[str], List[Dict[str, Optional[str]]]]:
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = [h for h in reader.fieldnames] if reader.fieldnames else []
        records: List[Dict[str, Optional[str]]] = []
        for row in reader:
            # Ensure all headers present; DictReader may omit missing fields
            normalized_row: Dict[str, Optional[str]] = {h: row.get(h) for h in headers}
            records.append(normalized_row)
    return headers, records


def build_key(record: Dict[str, Optional[str]], key_cols: List[str], *, trim: bool, case_insensitive: bool) -> Tuple[Optional[str], ...]:
    return tuple(
        normalize_value(record.get(col), trim=trim, case_insensitive=case_insensitive)
        for col in key_cols
    )


def has_missing_in_key(key: Tuple[Optional[str], ...]) -> bool:
    return any(v is None or v == "" for v in key)


def index_by_key(
    records: List[Dict[str, Optional[str]]],
    key_cols: List[str],
    *,
    trim: bool,
    case_insensitive: bool,
) -> Tuple[Dict[Tuple[Optional[str], ...], Dict[str, Optional[str]]], List[Tuple[Tuple[Optional[str], ...], Dict[str, Optional[str]]]]]:
    index: Dict[Tuple[Optional[str], ...], Dict[str, Optional[str]]] = {}
    duplicates: List[Tuple[Tuple[Optional[str], ...], Dict[str, Optional[str]]]] = []
    for rec in records:
        key = build_key(rec, key_cols, trim=trim, case_insensitive=case_insensitive)
        if has_missing_in_key(key):
            # Skip indexing records with incomplete keys but keep them in duplicates list for visibility
            duplicates.append((key, rec))
            continue
        if key in index:
            duplicates.append((key, rec))
        else:
            index[key] = rec
    return index, duplicates


def write_csv(path: str, headers: List[str], rows: Iterable[Iterable[object]]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(list(row))


def main() -> int:
    args = parse_args()

    left_headers, left_records = read_csv_as_records(args.left, delimiter=args.delimiter)
    right_headers, right_records = read_csv_as_records(args.right, delimiter=args.delimiter)

    key_cols = [c.strip() for c in args.key_cols.split(",") if c.strip()]
    if not key_cols:
        print("ERROR: --key-cols must specify at least one column.", file=sys.stderr)
        return 2

    trim = not args.no_trim
    case_insensitive = args.case_insensitive

    left_index, left_dups = index_by_key(left_records, key_cols, trim=trim, case_insensitive=case_insensitive)
    right_index, right_dups = index_by_key(right_records, key_cols, trim=trim, case_insensitive=case_insensitive)

    # Report duplicates if any
    if left_dups:
        write_csv(
            os.path.join(args.output_dir, "left_duplicates.csv"),
            headers=[*key_cols, *left_headers],
            rows=[
                [*key, *[rec.get(h, "") for h in left_headers]]
                for key, rec in left_dups
            ],
        )
    if right_dups:
        write_csv(
            os.path.join(args.output_dir, "right_duplicates.csv"),
            headers=[*key_cols, *right_headers],
            rows=[
                [*key, *[rec.get(h, "") for h in right_headers]]
                for key, rec in right_dups
            ],
        )

    left_keys: Set[Tuple[Optional[str], ...]] = set(left_index.keys())
    right_keys: Set[Tuple[Optional[str], ...]] = set(right_index.keys())

    missing_in_right = sorted(list(left_keys - right_keys))
    missing_in_left = sorted(list(right_keys - left_keys))

    write_csv(
        os.path.join(args.output_dir, "missing_in_right.csv"),
        headers=key_cols,
        rows=missing_in_right,
    )
    write_csv(
        os.path.join(args.output_dir, "missing_in_left.csv"),
        headers=key_cols,
        rows=missing_in_left,
    )

    # Parent comparison
    parent_mismatches: List[List[object]] = []
    parent_col = args.parent_col
    if parent_col and (parent_col in left_headers) and (parent_col in right_headers):
        for key in sorted(list(left_keys & right_keys)):
            l_parent = normalize_value(left_index[key].get(parent_col), trim=trim, case_insensitive=case_insensitive)
            r_parent = normalize_value(right_index[key].get(parent_col), trim=trim, case_insensitive=case_insensitive)
            if args.na_equal and ((l_parent in (None, "")) and (r_parent in (None, ""))):
                continue
            if l_parent != r_parent:
                parent_mismatches.append([*key, left_index[key].get(parent_col, ""), right_index[key].get(parent_col, "")])

        write_csv(
            os.path.join(args.output_dir, "parent_mismatches.csv"),
            headers=[*key_cols, f"left:{parent_col}", f"right:{parent_col}"],
            rows=parent_mismatches,
        )
    else:
        # Create an empty file to make it explicit that parent comparison was skipped
        write_csv(
            os.path.join(args.output_dir, "parent_mismatches.csv"),
            headers=[*key_cols, "left:parent", "right:parent"],
            rows=[],
        )

    # Property comparison
    ignore_cols = {c.strip() for c in args.ignore_cols.split(",") if c.strip()}
    if args.compare_cols.strip().lower() == "auto":
        left_cols = set(left_headers)
        right_cols = set(right_headers)
        auto_cols = sorted(list((left_cols & right_cols) - set(key_cols) - ({parent_col} if parent_col else set()) - ignore_cols))
        compare_cols = auto_cols
    else:
        compare_cols = [c.strip() for c in args.compare_cols.split(",") if c.strip()]

    property_mismatches: List[List[object]] = []
    for key in sorted(list(left_keys & right_keys)):
        lrec = left_index[key]
        rrec = right_index[key]
        for col in compare_cols:
            lval = normalize_value(lrec.get(col), trim=trim, case_insensitive=case_insensitive)
            rval = normalize_value(rrec.get(col), trim=trim, case_insensitive=case_insensitive)
            if args.na_equal and ((lval in (None, "")) and (rval in (None, ""))):
                continue
            if lval != rval:
                property_mismatches.append([*key, col, lrec.get(col, ""), rrec.get(col, "")])

    write_csv(
        os.path.join(args.output_dir, "property_mismatches.csv"),
        headers=[*key_cols, "column", "left:value", "right:value"],
        rows=property_mismatches,
    )

    # Summary to stdout
    print("Comparison complete.")
    print(f"Left records (unique keys): {len(left_keys)}")
    print(f"Right records (unique keys): {len(right_keys)}")
    print(f"Missing in right: {len(missing_in_right)}")
    print(f"Missing in left: {len(missing_in_left)}")
    if parent_col and (parent_col in left_headers) and (parent_col in right_headers):
        print(f"Parent mismatches: {len(parent_mismatches)}")
    else:
        print("Parent mismatches: skipped (parent column not provided or not present in both files)")
    print(f"Property mismatches: {len(property_mismatches)} across {len(compare_cols)} compared columns")
    print(f"Compared columns: {', '.join(compare_cols) if compare_cols else '(none)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())