#!/usr/bin/env python3
"""Check that all .py and .md files end with a single newline."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

bad_files = []
for pattern in ('*.py', '*.md'):
    for path in ROOT.rglob(pattern):
        if path.is_file():
            data = path.read_bytes()
            if not data.endswith(b"\n") or data.endswith(b"\n\n"):
                bad_files.append(path.relative_to(ROOT))

if bad_files:
    print("Files without single newline at EOF:")
    for bf in bad_files:
        print(bf)
    sys.exit(1)
else:
    print("All checked files end with a single newline.")
