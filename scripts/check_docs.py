#!/usr/bin/env python3
"""Fail when generated TF reference docs drift from the current dataset."""
from __future__ import annotations

import argparse
import filecmp
import tempfile
from pathlib import Path

from gen_docs import generate


def files(root: Path) -> set[Path]:
    return {p.relative_to(root) for p in root.rglob("*.md")}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tf_dir", type=Path)
    p.add_argument("--docs-dir", type=Path, default=Path("docs/reference"))
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        generated = Path(tmp)
        generate(a.tf_dir, generated)
        expected = {p for p in files(generated) if p == Path("features.md") or p.parts[:1] == ("features",)}
        actual = {p for p in files(a.docs_dir) if p == Path("features.md") or p.parts[:1] == ("features",)}
        if expected != actual:
            raise SystemExit(f"documentation feature set drift: expected={sorted(expected)!r} actual={sorted(actual)!r}")
        changed = [p for p in sorted(expected) if not filecmp.cmp(generated / p, a.docs_dir / p, shallow=False)]
        if changed:
            raise SystemExit(f"generated documentation drift: {changed!r}")


if __name__ == "__main__":
    main()
