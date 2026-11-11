"""Minimal local-source converter entry point for researchers.

The installed `oracc-tf` Python distribution contains converter code only,
not upstream ORACC source texts or a prebuilt corpus.
"""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
import sys

from . import app_generation, etcsri, ninmed


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


def _build_ninmed(args: argparse.Namespace) -> int:
    """Build from explicitly supplied primary ORACC asbp/ninmed source data."""
    source_root = Path(args.source_dir).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError(f"ORACC NINMED source directory does not exist: {source_root}")
    data_dir = source_root / "corpusjson" if (source_root / "corpusjson").is_dir() else source_root
    if output_root == source_root or output_root.is_relative_to(source_root):
        raise ValueError("TF output must be outside the supplied source directory")
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError(f"TF output must be a new/empty directory: {output_root}")

    available = {p.stem: p for p in sorted(data_dir.glob("*.json")) if p.is_file()}
    if not available:
        raise ValueError(f"No ORACC NINMED corpusjson files found in {data_dir}")
    if args.text_id:
        selected = sorted(set(args.text_id))
        missing = sorted(set(selected) - set(available))
        if missing:
            raise ValueError(f"Requested NINMED text IDs not found: {', '.join(missing)}")
    else:
        selected = sorted(available)
    sources = []
    skipped = []
    for text_id in selected:
        path = available[text_id]
        if path.stat().st_size == 0:
            if args.skip_known_empty and not args.text_id and text_id == "P395407":
                skipped.append(text_id)
                continue
            raise ValueError(
                f"NINMED zero-byte source {text_id} ({path.name}); "
                "use --skip-known-empty to explicitly exclude known P395407 in a full build"
            )
        if args.text_id:
            try:
                source_doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError) as exc:
                raise ValueError(f"Cannot read requested NINMED text {text_id}: {path}") from exc
            embedded = source_doc.get("textid") if isinstance(source_doc, dict) else None
            if embedded != text_id:
                raise ValueError(
                    f"Requested NINMED text {text_id} from {path.name}, "
                    f"but embedded source textid is {embedded!r}"
                )
        sources.append(path)
    if not sources:
        raise ValueError("No readable NINMED source editions selected")
    report = ninmed.build_tf(output_root, source_paths=sources)
    print(
        f"Built NINMED Text-Fabric: {report.documents} documents, "
        f"{report.words} words, {report.signs} source signs at {output_root}"
    )
    if skipped:
        print(f"Explicitly excluded known zero-byte NINMED source: {', '.join(skipped)}")
    return 0


def _prepare_local_app(args: argparse.Namespace) -> int:
    tf_root = Path(args.tf_dir).expanduser().resolve()
    app_root = Path(args.app_dir).expanduser().resolve()
    app_generation.generate_local_app(tf_root, app_root, corpus_kind=args.kind)
    print(f"Prepared unpublished {args.kind} local TF app at {app_root}")
    print(
        "Launch Text-Fabric browser with: python -m tf.browser.start "
        + shlex.quote(f"app:{app_root}")
        + " "
        + shlex.quote(f"--locations={tf_root}")
        + " --modules= -noweb"
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
    ninmed_command = commands.add_parser(
        "build-ninmed",
        help="Convert user-supplied ORACC ASBP/NINMED corpusjson to Text-Fabric.",
    )
    ninmed_command.add_argument(
        "--source-dir", required=True,
        help="Directory with NINMED corpusjson/*.json or corpusjson/ parent.",
    )
    ninmed_command.add_argument(
        "--output", required=True,
        help="New/empty destination for generated *.tf files.",
    )
    ninmed_command.add_argument(
        "--text-id", action="append",
        help="Select one native source ID (e.g. P285136); repeat as needed.",
    )
    ninmed_command.add_argument(
        "--skip-known-empty", action="store_true",
        help="For full-corpus input only: explicitly exclude known zero-byte P395407.json.",
    )
    preview = commands.add_parser(
        "prepare-local-app",
        help="Prepare a local (unpublished) native ORACC Text-Fabric browser app.",
    )
    preview.add_argument("--kind", required=True, choices=("etcsri", "ninmed"))
    preview.add_argument("--tf-dir", required=True, help="Directory of generated native TF features.")
    preview.add_argument("--app-dir", required=True, help="Separate target directory for local app config.")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-local-app":
            return _prepare_local_app(args)
        if args.command == "build-etcsri":
            return _build_etcsri(args)
        if args.command == "build-ninmed":
            return _build_ninmed(args)
    except (ValueError, OSError, etcsri.ETCSRISourceError) as exc:
        print(f"ORACC-TF: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
