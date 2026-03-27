#!/usr/bin/env python3

import os
import json
import hashlib
import sys
from pathlib import Path

def md5_of_file(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def select_folder():
    print("\n=== MD5 Database Crawler ===")
    folder = input("Target folder (Enter = current directory): ").strip()
    folder = os.path.abspath(folder) if folder else os.getcwd()
    if not os.path.isdir(folder):
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)
    print(f"Target folder: {folder}")
    return folder

def select_database():
    db_path = input("Database JSON path (Enter = 'md5_database.json' in current dir): ").strip()
    return os.path.abspath(db_path) if db_path else os.path.join(os.getcwd(), "md5_database.json")

def load_database(db_path):
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_database(db_path, data):
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def crawl_and_hash(folder, db):
    base = Path(folder)
    all_files = [p for p in base.rglob("*") if p.is_file()]
    total = len(all_files)
    print(f"\nFound {total} files. Starting MD5 generation...\n")

    updated = skipped = 0

    for i, filepath in enumerate(all_files, 1):
        rel_path = str(filepath.relative_to(base))
        try:
            md5 = md5_of_file(filepath)
        except Exception as e:
            print(f"[{i}/{total}] ERROR: {rel_path} — {e}")
            continue

        if md5 in db:
            print(f"[{i}/{total}] SKIP (hash exists): {rel_path}")
            skipped += 1
        else:
            # Value is the relative path, used as the label in cli.py
            db[md5] = rel_path
            print(f"[{i}/{total}] ADDED: {rel_path}")
            updated += 1

    return db, updated, skipped

def main():
    folder = select_folder()
    db_path = select_database()
    print(f"\nLoading database: {db_path}")
    db = load_database(db_path)
    print(f"Existing entries: {len(db)}")
    db, updated, skipped = crawl_and_hash(folder, db)
    save_database(db_path, db)
    print(f"\n=== Complete ===")
    print(f"New entries : {updated}")
    print(f"Skipped     : {skipped}")
    print(f"Total       : {len(db)}")
    print(f"Saved to    : {db_path}")

if __name__ == "__main__":
    main()
