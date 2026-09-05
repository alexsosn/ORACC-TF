#!/usr/bin/env python3
"""Generate the ORACC-TF feature reference from a built Text-Fabric dataset.

Generated facts come only from TF. Researcher prose is allowed only inside
named ``manual:begin`` / ``manual:end`` blocks, which are preserved exactly
across regeneration. The output is deterministic: the same TF input and manual
regions produce byte-identical Markdown.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from tf.fabric import Fabric


BEGIN_RE = re.compile(r"^<!-- manual:begin ([A-Za-z0-9_.-]+) -->$")
END = "<!-- manual:end -->"


class DocsGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FeatureRecord:
    name: str
    kind: str
    node_types: tuple[str, ...]
    value_type: str
    description: str
    populated: int
    distinct_values: int


def manual_regions(text: str) -> tuple[str, ...]:
    lines = text.splitlines(keepends=True)
    regions: list[str] = []
    names: set[str] = set()
    i = 0
    while i < len(lines):
        stripped = lines[i].rstrip("\r\n")
        match = BEGIN_RE.match(stripped)
        if match is None:
            if stripped == END:
                raise DocsGenerationError("manual:end without matching manual:begin")
            i += 1
            continue
        name = match.group(1)
        if name in names:
            raise DocsGenerationError(f"duplicate manual region {name!r}")
        names.add(name)
        start = i
        i += 1
        while i < len(lines) and lines[i].rstrip("\r\n") != END:
            if BEGIN_RE.match(lines[i].rstrip("\r\n")):
                raise DocsGenerationError("nested manual regions are not supported")
            i += 1
        if i == len(lines):
            raise DocsGenerationError(f"manual region {name!r} has no manual:end")
        regions.append("".join(lines[start : i + 1]).rstrip("\r\n"))
        i += 1
    return tuple(regions)


def _description(meta: dict[str, object], feature: str) -> str:
    value = meta.get("description")
    if not isinstance(value, str) or not value.strip():
        raise DocsGenerationError(f"feature {feature!r} has no non-empty @description")
    return value.strip()


def _node_types(api, nodes) -> tuple[str, ...]:
    return tuple(sorted({api.F.otype.v(node) for node in nodes if api.F.otype.v(node)}))


def load_feature_records(location: Path) -> tuple[FeatureRecord, ...]:
    tf = Fabric(locations=str(location.resolve()), silent="deep")
    if not tf.loadAll(silent="deep") or tf.api is None:
        raise DocsGenerationError(f"cannot load Text-Fabric dataset at {location}")
    api = tf.api

    records: list[FeatureRecord] = []
    for name in sorted(api.Fall(warp=False)):
        feature = api.Fs(name)
        if feature is None:
            continue
        data = feature.data
        values = tuple(data.values())
        records.append(
            FeatureRecord(
                name=name,
                kind="node",
                node_types=_node_types(api, data),
                value_type=str(feature.meta.get("valueType", "str")),
                description=_description(feature.meta, name),
                populated=len(data),
                distinct_values=len(set(values)),
            )
        )

    for name in sorted(api.Eall(warp=False)):
        feature = api.Es(name)
        if feature is None:
            continue
        data = feature.data
        records.append(
            FeatureRecord(
                name=name,
                kind="edge",
                node_types=_node_types(api, data),
                value_type=str(feature.meta.get("valueType", "str")),
                description=_description(feature.meta, name),
                populated=len(data),
                distinct_values=0,
            )
        )
    return tuple(records)


def _slug_types(record: FeatureRecord) -> str:
    if record.kind == "edge":
        return "edge"
    if len(record.node_types) == 1:
        return record.node_types[0]
    if not record.node_types:
        return "configuration"
    return "mixed"


def _feature_page(record: FeatureRecord) -> str:
    node_types = ", ".join(record.node_types) if record.node_types else "configuration"
    rows = [
        "---",
        f"title: Feature {record.name}",
        "status: generated",
        "type: reference-feature",
        "---",
        "",
        f"# `{record.name}`",
        "",
        f"- Kind: `{record.kind}`",
        f"- Node/source type: {node_types}",
        f"- Value type: `{record.value_type}`",
        f"- Populated entries: {record.populated}",
    ]
    if record.kind == "node":
        rows.append(f"- Distinct values: {record.distinct_values}")
    rows.extend(("", record.description, ""))
    return "\n".join(rows)


def render_index(records: tuple[FeatureRecord, ...], preserved: tuple[str, ...]) -> str:
    rows = [
        "---",
        "title: Feature reference",
        "status: generated",
        "type: reference",
        "---",
        "",
        "# Feature reference",
        "",
        "Generated from the emitted Text-Fabric dataset. Do not hand-edit generated facts.",
        "",
        "| feature | kind | node/source type | value type | description |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        types = ", ".join(record.node_types) if record.node_types else "configuration"
        description = record.description.replace("|", "\\|")
        rows.append(
            f"| `{record.name}` | {record.kind} | {types} | `{record.value_type}` | {description} |"
        )
    rows.append("")
    if preserved:
        rows.extend(preserved)
        rows.append("")
    return "\n".join(rows)


def generate(tf_location: Path, output: Path, *, allow_empty_dataset: bool = False) -> None:
    preserved: tuple[str, ...] = ()
    if output.exists():
        preserved = manual_regions(output.read_text(encoding="utf-8"))

    if tf_location.is_dir() and any(tf_location.glob("*.tf")):
        records = load_feature_records(tf_location)
    elif allow_empty_dataset:
        records = ()
    else:
        raise DocsGenerationError(f"no Text-Fabric dataset at {tf_location}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_index(records, preserved), encoding="utf-8")

    feature_root = output.parent / "features"
    for record in records:
        page = feature_root / _slug_types(record) / f"{record.name}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        old_regions = manual_regions(page.read_text(encoding="utf-8")) if page.exists() else ()
        text = _feature_page(record)
        if old_regions:
            text = text.rstrip() + "\n\n" + "\n\n".join(old_regions) + "\n"
        page.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-empty-dataset", action="store_true")
    args = parser.parse_args()
    try:
        generate(args.tf, args.output, allow_empty_dataset=args.allow_empty_dataset)
    except DocsGenerationError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
