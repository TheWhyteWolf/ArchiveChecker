#!/usr/bin/env python3
"""
cli.py — Command-line frontend for the MD5 checker.

Usage examples:
  python cli.py check path/to/file.zip
  python cli.py check path/to/file.zip --db ~/my_hashes.json
  python cli.py add   path/to/file.zip --label "My Archive v1"
  python cli.py remove <md5hex>
  python cli.py list
"""

import argparse
import sys
from pathlib import Path

from core import (
    check_file,
    hash_file,
    add_to_database,
    remove_from_database,
    load_database,
    DEFAULT_DB,
    CheckResult,
)

# ── ANSI colours (disabled automatically on Windows without ANSI support) ────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"


def _supports_colour() -> bool:
    return sys.stdout.isatty() and sys.platform != "win32"


def coloured(text: str, colour: str) -> str:
    return f"{colour}{text}{RESET}" if _supports_colour() else text


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_check(args):
    for filepath in args.files:
        try:
            result = check_file(filepath, db_path=Path(args.db))
        except FileNotFoundError as e:
            print(coloured(f"ERROR: {e}", RED))
            continue

        if result.in_library:
            label_info = f" ({result.label})" if result.label else ""
            print(coloured(f"✔  In library{label_info}", GREEN))
        else:
            print(coloured("✦  NEW ARCHIVE", YELLOW))

        if args.verbose:
            print(f"   File : {result.filepath}")
            print(f"   MD5  : {result.md5}")


def cmd_add(args):
    for filepath in args.files:
        try:
            md5 = hash_file(filepath)
        except FileNotFoundError as e:
            print(coloured(f"ERROR: {e}", RED))
            continue

        label = args.label or Path(filepath).name
        add_to_database(md5, label, db_path=Path(args.db))
        print(f"Added  {md5}  →  {label}")


def cmd_remove(args):
    for md5 in args.hashes:
        removed = remove_from_database(md5, db_path=Path(args.db))
        if removed:
            print(f"Removed {md5}")
        else:
            print(coloured(f"Not found: {md5}", RED))


def cmd_list(args):
    db = load_database(db_path=Path(args.db))
    if not db:
        print("Database is empty.")
        return
    width = max(len(k) for k in db)
    print(f"{'MD5'.ljust(width)}  Label")
    print("-" * (width + 30))
    for md5, label in sorted(db.items()):
        print(f"{md5.ljust(width)}  {label}")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md5checker",
        description="Check files against a local MD5 hash database.",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        metavar="PATH",
        help=f"Path to the JSON database (default: {DEFAULT_DB})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Check one or more files")
    p_check.add_argument("files", nargs="+", metavar="FILE")
    p_check.add_argument("-v", "--verbose", action="store_true")
    p_check.set_defaults(func=cmd_check)

    # add
    p_add = sub.add_parser("add", help="Add file(s) to the database")
    p_add.add_argument("files", nargs="+", metavar="FILE")
    p_add.add_argument("--label", default="", help="Friendly label (single file only)")
    p_add.set_defaults(func=cmd_add)

    # remove
    p_remove = sub.add_parser("remove", help="Remove hash(es) from the database")
    p_remove.add_argument("hashes", nargs="+", metavar="MD5")
    p_remove.set_defaults(func=cmd_remove)

    # list
    p_list = sub.add_parser("list", help="List all hashes in the database")
    p_list.set_defaults(func=cmd_list)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
