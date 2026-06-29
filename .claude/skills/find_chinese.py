#!/usr/bin/env python3
"""Find CJK Han characters in code and print file:line:column: line content.

By default, scan all git-tracked files (automatically respecting .gitignore / node_modules / .venv, etc.).
Pass paths to scan only selected files or directories:

  python3 find_chinese.py                 # scan the whole repo
  python3 find_chinese.py backend         # scan only backend/
  python3 find_chinese.py app.py utils.ts # scan specific files

# ponytail: only match CJK Unified Ideographs (including Extension A). To count CJK punctuation too,
#           add the relevant Unicode punctuation ranges to HAN below.
"""
import re
import subprocess
import sys
from pathlib import Path

HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")  # CJK Unified Ideographs, including Extension A.
SKIP_SUFFIXES = {".csv", ".tsv"}                   # CJK in data files is data, not code.


def _files(args: list[str]) -> list[Path]:
    # Git-tracked files automatically respect .gitignore; args restrict the path scope.
    cmd = ["git", "ls-files", "--", *args] if args else ["git", "ls-files"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        return [Path(x) for x in r.stdout.splitlines()]
    # Outside a git repo: fall back to recursive scanning.
    roots = [Path(a) for a in args] or [Path(".")]
    out: list[Path] = []
    for p in roots:
        out += [p] if p.is_file() else [q for q in p.rglob("*") if q.is_file()]
    return out


def find(files: list[Path]) -> int:
    hits = 0
    for f in files:
        if f.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue                           # Binary/unreadable; skip.
        for n, line in enumerate(lines, 1):
            m = HAN.search(line)
            if m:
                print(f"{f}:{n}:{m.start() + 1}: {line.strip()}")
                hits += 1
    return hits


def _selftest() -> None:
    assert HAN.search("\u4e2d\u6587") and HAN.search("\u4e2d\u6587").start() == 0
    assert not HAN.search("plain ascii 123")
    assert HAN.search("def f(): # \u6ce8\u91ca").start() == 11  # Column location is accurate.
    print("selftest OK")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        _selftest()
    else:
        n = find(_files(sys.argv[1:]))
        print(f"\n{n} lines contain CJK Han characters", file=sys.stderr)
