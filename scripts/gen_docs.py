#!/usr/bin/env python3
"""Generate deterministic TF feature reference pages while preserving manual regions."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tf.fabric import Fabric

MANUAL = re.compile(r"<!-- manual:begin ([^ ]+) -->.*?<!-- manual:end -->", re.S)
MANIFEST = ".manual-regions.json"


def manual_regions(text: str) -> dict[str, str]:
    return {m.group(1): m.group(0) for m in MANUAL.finditer(text)}


def _load_manifest(docs_dir: Path) -> dict[str, list[str]]:
    path = docs_dir / MANIFEST
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid manual-region manifest at {path}")
    return {
        str(rel): [str(name) for name in names]
        for rel, names in data.items()
        if isinstance(names, list)
    }


def write_preserving(
    path: Path,
    generated: str,
    *,
    expected_regions: tuple[str, ...] = (),
) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    regions = manual_regions(old)
    missing = sorted(set(expected_regions) - set(regions))
    if missing:
        raise RuntimeError(
            f"manual region(s) {missing!r} were deleted from {path}; restore them before regeneration"
        )
    for name, block in regions.items():
        marker = f"<!-- manual:begin {name} -->\n<!-- manual:end -->"
        if marker not in generated:
            raise RuntimeError(f"manual region {name!r} has no generated placeholder in {path}")
        generated = generated.replace(marker, block)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generated.rstrip() + "\n", encoding="utf-8")


def _feature_page(
    *,
    name: str,
    kind: str,
    scope: str,
    value_type: str,
    description: str,
    populated_values: int,
) -> str:
    return f"""# `{name}`\n\n- kind: `{kind}`\n- scope: `{scope}`\n- value type: `{value_type}`\n- populated values: `{populated_values}`\n- description: {description}\n\n<!-- manual:begin interpretation -->\n<!-- manual:end -->\n"""


def generate(tf_dir: Path, docs_dir: Path) -> set[Path]:
    tf = Fabric(locations=str(tf_dir), silent="deep")
    if not tf.loadAll(silent="deep") or tf.api is None:
        raise RuntimeError(f"cannot load Text-Fabric dataset at {tf_dir}")
    api = tf.api
    manifest = _load_manifest(docs_dir)
    generated_paths: set[Path] = set()
    next_manifest: dict[str, list[str]] = {}

    rows = ["# Feature reference", "", "Generated from TF metadata; do not hand-edit generated fields.", ""]

    for name in sorted(api.Fall()):
        feature = api.Fs(name)
        description = str(feature.meta.get("description", "")).strip()
        value_type = str(feature.meta.get("valueType", "str"))
        if not description:
            raise RuntimeError(f"feature {name!r} has an empty @description")
        node_types: set[str] = set()
        populated_values = 0
        for node, _ in feature.items():
            populated_values += 1
            node_types.add(api.F.otype.v(node))
        scope = next(iter(node_types)) if len(node_types) == 1 else "mixed"
        rel = Path("features") / scope / f"{name}.md"
        rows.append(f"- [`{name}`]({rel.as_posix()}) — {description}")
        page = _feature_page(
            name=name,
            kind="node",
            scope=scope,
            value_type=value_type,
            description=description,
            populated_values=populated_values,
        )
        write_preserving(
            docs_dir / rel,
            page,
            expected_regions=tuple(manifest.get(rel.as_posix(), ())),
        )
        generated_paths.add(rel)
        next_manifest[rel.as_posix()] = sorted(manual_regions((docs_dir / rel).read_text(encoding="utf-8")))

    for name in sorted(api.Eall()):
        feature = api.Es(name)
        description = str(feature.meta.get("description", "")).strip()
        value_type = str(feature.meta.get("valueType", "str"))
        if not description:
            raise RuntimeError(f"edge feature {name!r} has an empty @description")
        populated_values = sum(1 for _ in feature.items())
        rel = Path("features") / "edge" / f"{name}.md"
        rows.append(f"- [`{name}`]({rel.as_posix()}) — {description}")
        page = _feature_page(
            name=name,
            kind="edge",
            scope="edge",
            value_type=value_type,
            description=description,
            populated_values=populated_values,
        )
        write_preserving(
            docs_dir / rel,
            page,
            expected_regions=tuple(manifest.get(rel.as_posix(), ())),
        )
        generated_paths.add(rel)
        next_manifest[rel.as_posix()] = sorted(manual_regions((docs_dir / rel).read_text(encoding="utf-8")))

    feature_index = Path("features.md")
    write_preserving(
        docs_dir / feature_index,
        "\n".join(rows) + "\n",
        expected_regions=tuple(manifest.get(feature_index.as_posix(), ())),
    )
    generated_paths.add(feature_index)
    next_manifest[feature_index.as_posix()] = sorted(
        manual_regions((docs_dir / feature_index).read_text(encoding="utf-8"))
    )

    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / MANIFEST).write_text(
        json.dumps(next_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return generated_paths


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("tf_dir", type=Path)
    p.add_argument("--docs-dir", type=Path, default=Path("docs/reference"))
    a = p.parse_args()
    generate(a.tf_dir, a.docs_dir)


if __name__ == "__main__":
    main()
