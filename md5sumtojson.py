#!/usr/bin/env python3
"""
md5sum_to_json.py — Convert a .md5sum file to the JSON database format
used by the MD5 checker system.

Usage:
  python md5sum_to_json.py input.md5sum
  python md5sum_to_json.py input.md5sum --output my_database.json
  python md5sum_to_json.py input.md5sum --merge existing_database.json
"""

import argparse
import json
import sys
from pathlib import Path


def parse_md5sum_file(md5sum_path: Path) -> dict:
    """
    Parse a .md5sum file into a {md5: filepath} dict.

    Supports both formats:
      <hash>  <filepath>   (two spaces, standard md5sum output)
      <hash> <filepath>    (one space)
    """
    entries = {}
    errors = []

    with open(md5sum_path, "r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue  # skip blank lines and comments

            # Standard md5sum format: 32 hex chars, then one or two spaces, then path
            if len(line) < 34 or not all(c in "0123456789abcdefABCDEF" for c in line[:32]):
                errors.append(f"Line {lineno}: skipped (unrecognised format): {line!r}")
                continue

            md5 = line[:32].lower()
            # Strip one or two separator spaces
            rest = line[32:]
            if rest.startswith("  "):
                filepath = rest[2:]
            elif rest.startswith(" "):
                filepath = rest[1:]
            else:
                errors.append(f"Line {lineno}: skipped (no space after hash): {line!r}")
                continue

            filepath = filepath.strip()
            if not filepath:
                errors.append(f"Line {lineno}: skipped (empty path after hash)")
                continue

            if md5 in entries:
                print(f"  WARNING line {lineno}: duplicate hash {md5}, "
                      f"keeping first entry ({entries[md5]!r})", file=sys.stderr)
            else:
                entries[md5] = filepath

    return entries, errors


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: dict, path: Path) -> None:
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md5sum_to_json",
        description="Convert a .md5sum file to the MD5 checker JSON database format.",
    )
    parser.add_argument("input", metavar="INPUT.md5sum",
                        help="Path to the source .md5sum file")
    parser.add_argument("-o", "--output", metavar="PATH",
                        help="Output JSON file (default: same name as input with .json extension)")
    parser.add_argument("-m", "--merge", metavar="EXISTING.json",
                        help="Merge into an existing JSON database instead of creating a new one")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress progress output")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".json")

    # Parse the .md5sum file
    if not args.quiet:
        print(f"Parsing: {input_path}")
    entries, errors = parse_md5sum_file(input_path)

    # Report parse errors
    for err in errors:
        print(f"  WARNING: {err}", file=sys.stderr)

    if not args.quiet:
        print(f"  Parsed {len(entries)} entries.")

    # Optionally merge with an existing database
    if args.merge:
        merge_path = Path(args.merge)
        if not merge_path.exists():
            print(f"ERROR: Merge target not found: {merge_path}", file=sys.stderr)
            sys.exit(1)
        existing = load_json(merge_path)
        before = len(existing)
        duplicates = sum(1 for k in entries if k in existing)
        existing.update(entries)          # new entries win on collision
        added = len(existing) - before
        if not args.quiet:
            print(f"  Merging into: {merge_path}")
            print(f"  Existing entries : {before}")
            print(f"  New entries added: {added}")
            print(f"  Duplicates (overwritten): {duplicates}")
        output_path = merge_path if not args.output else output_path
        save_json(existing, output_path)
    else:
        save_json(entries, output_path)

    if not args.quiet:
        print(f"  Saved → {output_path}")


if __name__ == "__main__":
    main()
