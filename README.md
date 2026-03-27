# MD5 Checker

A portable, zero-dependency MD5 file checker.  
Requires **Python 3.10+** (uses the `match`-free walrus operator, stdlib only).

```
md5checker/
├── core.py            # shared logic — import this in any frontend
├── cli.py             # command-line interface
├── gui.py             # (coming next) tkinter GUI
└── md5_database.json  # hash database (auto-created if missing)
```

---

## CLI usage

```bash
# Check a file
python cli.py check archive.zip

# Check verbosely (shows md5 + path)
python cli.py check archive.zip -v

# Check multiple files at once
python cli.py check *.zip

# Add a file to the database
python cli.py add archive.zip --label "My Archive v1"

# Add multiple files (label ignored for multi-file)
python cli.py add *.zip

# Remove a hash
python cli.py remove d41d8cd98f00b204e9800998ecf8427e

# List all known hashes
python cli.py list

# Use a custom database path
python cli.py --db /path/to/custom.json check archive.zip
```

---

## Database format

Plain JSON — easy to edit by hand or sync with version control:

```json
{
  "d41d8cd98f00b204e9800998ecf8427e": "Empty file",
  "9e107d9d372bb6826bd81d3542a419d6": "Some archive"
}
```

---

## Using `core.py` directly

```python
from core import check_file, add_to_database

result = check_file("archive.zip")

if result.in_library:
    print("In library", result.label)
else:
    print("NEW ARCHIVE — md5:", result.md5)
    # optionally add it
    add_to_database(result.md5, label="archive.zip")
```
