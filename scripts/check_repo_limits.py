#!/usr/bin/env python3
"""Report files that GitHub will reject or warn about before you try to push.

GitHub blocks any single file over 100 MB and warns over 50 MB. Repository
size is advisory: under 1 GB is ideal, under 5 GB strongly recommended.
Those limits apply to the file as stored, so git's compression does not help.

Usage: scripts/check_repo_limits.py [ROOT]          (default: .)
"""

import os
import subprocess
import sys

HARD_MB = 100
WARN_MB = 50


def tracked_files(root):
    """Files git would actually store: respects .gitignore when in a repo."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True).stdout
        return [os.path.join(root, p) for p in out.splitlines() if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [os.path.join(dp, f)
                for dp, _, fs in os.walk(root) if ".git" not in dp
                for f in fs]


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    files = tracked_files(root)
    sizes = []
    total = 0
    for p in files:
        try:
            s = os.path.getsize(p)
        except OSError:
            continue
        total += s
        if s > WARN_MB * 1048576:
            sizes.append((s, os.path.relpath(p, root)))
    sizes.sort(reverse=True)

    blocked = [(s, p) for s, p in sizes if s > HARD_MB * 1048576]
    warned = [(s, p) for s, p in sizes if WARN_MB * 1048576 < s <= HARD_MB * 1048576]

    print(f"files: {len(files):,}   uncompressed total: {total/1073741824:.2f} GB")
    print(f"\nBLOCKED (>{HARD_MB} MB, push will be rejected): {len(blocked)}")
    for s, p in blocked:
        print(f"  {s/1048576:8.1f} MB  {p}")
    print(f"\nWARNING (>{WARN_MB} MB, allowed): {len(warned)}")
    for s, p in warned:
        print(f"  {s/1048576:8.1f} MB  {p}")
    if blocked:
        print("\nShard oversized ORACC index files with scripts/shard_index.py")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
