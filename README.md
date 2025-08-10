## Welcome to "Hello World" with GitHub Actions

This course will walk you through writing your first action and using it with a workflow file. 

**Ready to get started? Navigate to the first issue.**

## EDMCS Viewpoint Comparison Tool

A Python CLI to compare two Oracle EDMCS viewpoint CSV extracts for:
- missing nodes
- parent mismatches
- property value discrepancies

### Usage

```bash
python3 edmcs_compare.py \
  --left /absolute/path/to/left.csv \
  --right /absolute/path/to/right.csv \
  --key-cols "Node Code" \
  --parent-col "Parent Code" \
  --compare-cols auto \
  --na-equal \
  --output-dir /absolute/path/to/output
```

Flags:
- `--key-cols`: Comma-separated columns that uniquely identify a node (e.g., `Node Code` or `Node Name,Node Code`).
- `--parent-col`: Parent column name to compare (e.g., `Parent Code`). If omitted or missing in either file, parent comparison is skipped.
- `--compare-cols`: Columns to compare. Use `auto` to compare the intersection of columns excluding keys, parent, and ignored columns.
- `--ignore-cols`: Columns to ignore when using `auto` (default includes typical EDMCS metadata columns).
- `--delimiter`: CSV delimiter (default `,`).
- `--case-insensitive`: Case-insensitive comparisons.
- `--no-trim`: Disable trimming whitespace before comparisons.
- `--na-equal`: Treat blank/NA values as equal when both sides are blank.
- `--output-dir`: Directory for result CSVs.

Outputs written to `--output-dir`:
- `missing_in_right.csv`
- `missing_in_left.csv`
- `parent_mismatches.csv`
- `property_mismatches.csv`
- `left_duplicates.csv` (if found)
- `right_duplicates.csv` (if found)

Notes:
- The tool reads with `utf-8-sig` to tolerate BOM.
- Keys with missing components are listed as duplicates and skipped from matching.