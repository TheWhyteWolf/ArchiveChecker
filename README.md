# MD5 Checker

A portable, zero-dependency MD5 file checker for linux.  
Requires **Python 3.10+** (uses the `match`-free walrus operator, stdlib only).
---
**Platform**	Action Required  

**Windows**	  Install Pillow; optionally install tkinterdnd2 for drag-and-drop; run via python gui.py not ./gui.py
**macOS**	    Install Pillow; optionally install tkinterdnd2; Python 3.10+ required

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
