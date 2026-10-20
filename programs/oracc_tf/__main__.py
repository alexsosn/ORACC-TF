"""Minimal local-source converter entry point for researchers.

The installed `oracc-tf` Python distribution contains converter code only,
not upstream ORACC source texts or a prebuilt corpus.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import etcsri


def _build_etcsri(args: argparse.Namespace) -> int:
    source_root = Path(args.source_dir).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError(f"ORACC source directory does not exist: {source_root}")
    data_dir = source_root / "corpusjson" if (source_root / "corpusjson").is_dir() else source_root
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ValueError("TF output must be outside the supplied source directory")
    if output_root.exists():
        if not output_root.is_dir():
            raise ValueError(f"TF output is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise ValueError(f"TF output must be empty, refusing to overwrite: {output_root}")

    available = {p.stem: p for p in sorted(data_dir.glob("*.json")) if p.is_file()}
    if not available:
        raise ValueError(f"No ORACC corpusjson files found in {data_dir}")
    if args.text_id:
        missing = sorted(set(args.text_id) - set(available))
        if missing:
            raise ValueError(f"Requested ETCSRI text IDs not found: {', '.join(missing)}")
        sources = [available[text_id] for text_id in sorted(set(args.text_id))]
        # The scholarly identity is embedded in ORACC JSON, not guaranteed
        # by its filename. Do not report that we built a different edition.
        for requested, path in zip(sorted(set(args.text_id)), sources, strict=True):
            try:
                source_doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError) as exc:
                raise ValueError(f"Cannot read requested ETCSRI text {requested}: {path}") from exc
            embedded = source_doc.get("textid") if isinstance(source_doc, dict) else None
            if embedded != requested:
                raise ValueError(
                    f"Requested ETCSRI text {requested} from {path.name}, "
                    f"but embedded source textid is {embedded!r}"
                )
    else:
        sources = [available[key] for key in sorted(available)]

    report = etcsri.build_tf(output_root, source_paths=sources)
    selected = ", ".join(args.text_id) if args.text_id else "all provided sources"
    print(
        f"Built ETCSRI Text-Fabric: {report.documents} documents, "
        f"{report.words} words, {report.semantic_signs} source signs "
        f"({selected}) at {output_root}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m oracc_tf",
        description="Convert user-supplied ORACC source JSON to Text-Fabric; no data is downloaded.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    etcsri_command = commands.add_parser(
        "build-etcsri",
        help="Convert ETCSRI corpusjson editions to an independent TF graph.",
    )
    etcsri_command.add_argument(
        "--source-dir", required=True,
        help="Path to ETCSRI corpusjson directory or its parent containing corpusjson/.",
    )
    etcsri_command.add_argument(
        "--output", required=True,
        help="New/empty destination directory for generated *.tf files.",
    )
    etcsri_command.add_argument(
        "--text-id", action="append",
        help="Select one text ID (e.g. Q000935); repeat to select multiple. Default: all files.",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "build-etcsri":
            return _build_etcsri(args)
    except (ValueError, OSError, etcsri.ETCSRISourceError) as exc:
        print(f"ORACC-TF: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
