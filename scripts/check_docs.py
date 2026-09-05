#!/usr/bin/env python3
"""Fail when generated TF reference docs drift from the current dataset."""
from __future__ import annotations

import argparse
import filecmp
import shutil
import tempfile
from pathlib import Path

from gen_docs import MANIFEST, generate


def feature_files(root: Path) -> set[Path]:
    return {
        p.relative_to(root)
        for p in root.rglob("*.md")
        if p.name == "features.md" or p.relative_to(root).parts[:1] == ("features",)
    }


def check(tf_dir: Path, docs_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        generated_root = Path(tmp) / "reference"
        if docs_dir.exists():
            shutil.copytree(docs_dir, generated_root)
        else:
            generated_root.mkdir(parents=True)

        expected = generate(tf_dir, generated_root)
        actual = feature_files(docs_dir) if docs_dir.exists() else set()
        if expected != actual:
            raise RuntimeError(
                f"documentation feature set drift: expected={sorted(expected)!r} actual={sorted(actual)!r}"
            )

        changed = [
            path
            for path in sorted(expected)
            if not filecmp.cmp(generated_root / path, docs_dir / path, shallow=False)
        ]
        if changed:
            raise RuntimeError(f"generated documentation drift: {changed!r}")

        generated_manifest = generated_root / MANIFEST
        actual_manifest = docs_dir / MANIFEST
        if not actual_manifest.exists() or not filecmp.cmp(
            generated_manifest, actual_manifest, shallow=False
        ):
            raise RuntimeError("generated documentation manual-region manifest drift")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tf_dir", type=Path)
    p.add_argument("--docs-dir", type=Path, default=Path("docs/reference"))
    a = p.parse_args()
    try:
        check(a.tf_dir, a.docs_dir)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
