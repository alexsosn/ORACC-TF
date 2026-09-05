#!/usr/bin/env python3
"""Generate deterministic TF feature reference pages while preserving manual regions."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from tf.fabric import Fabric

MANUAL = re.compile(r"<!-- manual:begin ([^ ]+) -->.*?<!-- manual:end -->", re.S)


def manual_regions(text: str) -> dict[str, str]:
    return {m.group(1): m.group(0) for m in MANUAL.finditer(text)}


def write_preserving(path: Path, generated: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    regions = manual_regions(old)
    for name, block in regions.items():
        marker = f"<!-- manual:begin {name} -->\n<!-- manual:end -->"
        if marker not in generated:
            raise RuntimeError(f"manual region {name!r} has no generated placeholder in {path}")
        generated = generated.replace(marker, block)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generated.rstrip() + "\n", encoding="utf-8")


def generate(tf_dir: Path, docs_dir: Path) -> None:
    tf = Fabric(locations=str(tf_dir), silent="deep")
    if not tf.loadAll(silent="deep") or tf.api is None:
        raise RuntimeError(f"cannot load Text-Fabric dataset at {tf_dir}")
    api = tf.api
    features = sorted(name for name in api.Fall() if name not in {"otype"})
    rows = ["# Feature reference", "", "Generated from TF metadata; do not hand-edit generated fields.", ""]
    for name in features:
        f = api.Fs(name)
        description = str(f.meta.get("description", "")).strip()
        value_type = str(f.meta.get("valueType", "str"))
        if not description:
            raise RuntimeError(f"feature {name!r} has an empty @description")
        node_types = sorted({api.F.otype.v(n) for n in f.items()})
        node_type = node_types[0] if len(node_types) == 1 else "mixed"
        rel = Path("features") / node_type / f"{name}.md"
        rows.append(f"- [`{name}`]({rel.as_posix()}) — {description}")
        page = f"""# `{name}`\n\n- node type: `{node_type}`\n- value type: `{value_type}`\n- description: {description}\n\n<!-- manual:begin interpretation -->\n<!-- manual:end -->\n"""
        write_preserving(docs_dir / rel, page)
    write_preserving(docs_dir / "features.md", "\n".join(rows) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tf_dir", type=Path)
    p.add_argument("--docs-dir", type=Path, default=Path("docs/reference"))
    a = p.parse_args()
    generate(a.tf_dir, a.docs_dir)


if __name__ == "__main__":
    main()
