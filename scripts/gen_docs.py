#!/usr/bin/env python3
"""Generate deterministic TF feature reference pages while preserving manual regions."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from tf.fabric import Fabric

MANUAL = re.compile(r"<!-- manual:begin ([^ ]+) -->.*?<!-- manual:end -->", re.S)
MANIFEST = ".manual-regions.json"
MAX_FREQUENCY_ROWS = 20
MAX_RENDERED_VALUE = 120


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


def _md_code(value: object) -> str:
    raw = str(value)
    text = raw.replace("\n", "\\n").replace("|", "\\|").replace("`", "\\`")
    if len(text) > MAX_RENDERED_VALUE:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        text = f"{text[:MAX_RENDERED_VALUE]}… sha256:{digest}"
    return f"`{text}`"


def _frequency_rows(counts: Counter[object]) -> list[tuple[object, int]]:
    return sorted(
        counts.items(),
        key=lambda item: (-item[1], type(item[0]).__name__, str(item[0])),
    )[:MAX_FREQUENCY_ROWS]


def _frequency_table(counts: Counter[object]) -> str:
    rows = ["| value | count |", "|---|---:|"]
    rows.extend(f"| {_md_code(value)} | {count} |" for value, count in _frequency_rows(counts))
    intro = ""
    if len(counts) > MAX_FREQUENCY_ROWS:
        intro = f"Showing the {MAX_FREQUENCY_ROWS} most frequent values.\n\n"
    return intro + "\n".join(rows)


def _node_feature_page(
    *,
    name: str,
    scope: str,
    value_type: str,
    description: str,
    populated_values: int,
    value_counts: Counter[object],
) -> str:
    return f"""# `{name}`

- kind: `node`
- scope: `{scope}`
- value type: `{value_type}`
- populated values: `{populated_values}`
- distinct values: `{len(value_counts)}`
- description: {description}

## Value frequencies

{_frequency_table(value_counts)}

<!-- manual:begin interpretation -->
<!-- manual:end -->
"""


def _targets(value: object) -> tuple[int, ...]:
    if isinstance(value, Mapping):
        raw: Iterable[object] = value.keys()
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        raw = value
    else:
        raw = (value,)
    targets: list[int] = []
    for target in raw:
        if not isinstance(target, int):
            raise RuntimeError(f"edge target is not a node id: {target!r}")
        targets.append(target)
    return tuple(targets)


def _type_list(types: set[str]) -> str:
    if not types:
        return "(none)"
    return ", ".join(_md_code(item) for item in sorted(types))


def _edge_feature_page(
    *,
    name: str,
    value_type: str,
    description: str,
    populated_sources: int,
    link_count: int,
    source_types: set[str],
    target_types: set[str],
    degree_counts: Counter[int],
) -> str:
    degree_rows = ["| out-degree | sources |", "|---:|---:|"]
    degree_rows.extend(
        f"| {degree} | {count} |" for degree, count in sorted(degree_counts.items())
    )
    return f"""# `{name}`

- kind: `edge`
- scope: `edge`
- value type: `{value_type}`
- populated values: `{populated_sources}`
- populated sources: `{populated_sources}`
- links: `{link_count}`
- source node types: {_type_list(source_types)}
- target node types: {_type_list(target_types)}
- description: {description}

## Out-degree frequencies

{chr(10).join(degree_rows)}

<!-- manual:begin interpretation -->
<!-- manual:end -->
"""


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
        value_counts: Counter[object] = Counter()
        populated_values = 0
        for node, value in feature.items():
            populated_values += 1
            node_types.add(api.F.otype.v(node))
            value_counts[value] += 1
        scope = next(iter(node_types)) if len(node_types) == 1 else "mixed"
        rel = Path("features") / scope / f"{name}.md"
        rows.append(f"- [`{name}`]({rel.as_posix()}) — {description}")
        page = _node_feature_page(
            name=name,
            scope=scope,
            value_type=value_type,
            description=description,
            populated_values=populated_values,
            value_counts=value_counts,
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
        source_types: set[str] = set()
        target_types: set[str] = set()
        degree_counts: Counter[int] = Counter()
        populated_sources = 0
        link_count = 0
        for source, raw_targets in feature.items():
            targets = _targets(raw_targets)
            populated_sources += 1
            source_types.add(api.F.otype.v(source))
            degree_counts[len(targets)] += 1
            link_count += len(targets)
            for target in targets:
                target_types.add(api.F.otype.v(target))
        rel = Path("features") / "edge" / f"{name}.md"
        rows.append(f"- [`{name}`]({rel.as_posix()}) — {description}")
        page = _edge_feature_page(
            name=name,
            value_type=value_type,
            description=description,
            populated_sources=populated_sources,
            link_count=link_count,
            source_types=source_types,
            target_types=target_types,
            degree_counts=degree_counts,
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
