#!/usr/bin/env python3
"""Stage native ETCSRI/NINMED corpus ZIP candidates from pinned local ORACC JSON.

Maintainer-only tool. Reuses the existing converter, P-005 distribution,
native Text-Fabric app, manual assembler, and release_archive. It does not
download upstream sources, create GitHub releases, or pretend a CI candidate
has already been published.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import re
import shutil
import time

from tf.fabric import Fabric

from oracc_tf import app_generation, distribution, etcsri, manual, ninmed, release_archive


SOURCE_RELATIVE = {
    "etcsri": Path("data/etcsri/corpusjson"),
    "ninmed": Path("data/asbp/ninmed/corpusjson"),
}
SOURCE_COUNT = {"etcsri": 1456, "ninmed": 160}
KNOWN_EMPTY = "P395407.json"
TF_VERSION = "0.1.0"
RELEASE_ID = "0.1.0-rc1"


def _source_snapshot(checkout: Path, kind: str) -> tuple[list[Path], str]:
    """Verify the actual snapshot partition and digest every original file.

    The single NINMED zero-byte member is a source hazard, never a TF
    document, and is included in the content digest despite exclusion from
    the list of editions passed to the converter.
    """
    if kind not in SOURCE_RELATIVE:
        raise ValueError(f"unknown native corpus {kind!r}")
    root = checkout / SOURCE_RELATIVE[kind]
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"missing source directory: {root}")
    members = sorted(root.glob("*.json"))
    if len(members) != SOURCE_COUNT[kind]:
        raise ValueError(
            f"{kind} source membership changed: expected {SOURCE_COUNT[kind]}, "
            f"observed {len(members)}; inspect the input before publication"
        )
    hazard = root / KNOWN_EMPTY
    if kind == "ninmed" and (not hazard.is_file() or hazard.is_symlink() or hazard.stat().st_size != 0):
        raise ValueError("NINMED known P395407.json hazard changed; inspect source before publication")
    selected: list[Path] = []
    state = sha256()
    for path in members:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"unreadable or symlinked primary source: {path.name}")
        raw = path.read_bytes()
        if not raw and not (kind == "ninmed" and path.name == KNOWN_EMPTY):
            raise ValueError(f"unexpected zero-byte {kind} source: {path.name}")
        state.update(path.name.encode("utf-8"))
        state.update(b"\0")
        state.update(sha256(raw).digest())
        if raw:
            selected.append(path)
    if len(selected) != (1456 if kind == "etcsri" else 159):
        raise ValueError(f"{kind} readable primary source partition changed")
    return selected, "sha256:" + state.hexdigest()


def build_candidate(
    checkout: Path,
    output_base: Path,
    *,
    kind: str,
    builder_commit: str,
    release_id: str = RELEASE_ID,
) -> tuple[Path, Path]:
    """Create a deterministic corpus ZIP without publication side effects."""
    if not isinstance(release_id, str) or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-rc[1-9][0-9]*)?", release_id
    ):
        raise ValueError(f"invalid release_id: {release_id!r}")
    if not isinstance(builder_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", builder_commit):
        raise ValueError("builder commit must be a real 40-digit lowercase git revision")
    checkout = checkout.resolve(strict=True)
    output_base = output_base.resolve(strict=False)
    if output_base == checkout or checkout in output_base.parents or output_base in checkout.parents:
        raise ValueError("candidate output must not overlap its source checkout")
    if output_base.exists() and any(output_base.iterdir()):
        raise ValueError(f"candidate output must be empty: {output_base}")

    sources, source_state = _source_snapshot(checkout, kind)
    tf_root = output_base / "work" / "tf-source"
    started = time.monotonic()
    report = (
        etcsri.build_tf(tf_root, source_paths=sources)
        if kind == "etcsri" else ninmed.build_tf(tf_root, source_paths=sources)
    )
    expected_docs = 1456 if kind == "etcsri" else 159
    expected_words = 29573 if kind == "etcsri" else 65089
    if report.documents != expected_docs or report.words != expected_words:
        raise ValueError(
            f"{kind} source-to-TF count mismatch: "
            f"{report.documents} docs, {report.words} words"
        )
    if kind == "etcsri" and report.semantic_signs != 68403:
        raise ValueError("ETCSRI semantic source-sign count differs from pinned census")
    if kind == "ninmed" and (
        report.sign_word_membership_errors or report.word_line_membership_errors
    ):
        raise ValueError("NINMED sign/word or word/line locality differs from source")

    # Reconcile *every* source edition with the emitted TF document identity
    # and SHA-256 before the release stage can be labelled source-complete.
    fabric = Fabric(locations=str(tf_root), silent="deep")
    if not fabric.loadAll(silent="deep") or fabric.api is None:
        raise ValueError(f"{kind} whole-source TF cannot be loaded")
    api = fabric.api
    actual = {
        api.F.document_key.v(d): api.F.source_sha256.v(d)
        for d in api.F.otype.s("document")
    }
    prefix = "etcsri:" if kind == "etcsri" else "asbp/ninmed:"
    expected = {
        prefix + p.stem: sha256(p.read_bytes()).hexdigest()
        for p in sources
    }
    if actual != expected:
        raise ValueError(f"{kind} TF document membership/source SHA mismatches primary JSON")

    app = app_generation.generate_app(
        tf_root, output_base / "work" / "app",
        dataset=kind, tf_version=TF_VERSION, native_kind=kind,
        repository_org="alexsosn", docs_ref=builder_commit,
        datasets_path=checkout / "datasets.toml",
    )
    docs = manual.assemble_native_manual(
        checkout, output_base / "work" / "docs", dataset=kind,
    )
    # Our full-corpus SHA reconciliation uses Fabric.loadAll(), which creates
    # a volatile .tf cache beside the source TF files. Distribution digests
    # must cover only portable .tf feature files, never platform-specific
    # binary caches. Preserve the archive packager's hidden-path guard.
    cache = tf_root / ".tf"
    if cache.is_symlink() or (cache.exists() and not cache.is_dir()):
        raise ValueError("unexpected non-directory or symlinked Text-Fabric cache")
    if cache.is_dir():
        shutil.rmtree(cache)
    stage = output_base / "stage"
    manifest = distribution.stage_distribution(
        tf_root, stage,
        dataset=kind, release_id=release_id,
        tf_version=TF_VERSION, builder_commit=builder_commit,
        source_state=source_state, support_roots={"app": app, "docs": docs},
    )
    if manifest["tf_root"] != f"tf/{TF_VERSION}":
        raise ValueError("native stage has an unexpected TF root")
    archive, checksum = release_archive.package_release(
        stage, output_base / "assets",
    )
    digest = sha256(archive.read_bytes()).hexdigest()
    if checksum.read_text(encoding="utf-8").strip() != f"{digest}  {archive.name}":
        raise ValueError("candidate archive checksum mismatch")

    print(
        f"{kind}: {report.documents} primary texts, {report.words} source words, "
        f"source_state={source_state}, elapsed={time.monotonic()-started:.3f}s, "
        f"zip_bytes={archive.stat().st_size}, zip_sha256={digest}"
    )
    return archive, checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, choices=tuple(SOURCE_RELATIVE))
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--output-base", type=Path, required=True)
    parser.add_argument("--builder-commit", required=True)
    parser.add_argument(
        "--release-id", default=RELEASE_ID,
        help="Explicit release version (e.g. 0.1.0 final, default 0.1.0-rc1 candidate)",
    )
    args = parser.parse_args(argv)
    archive, checksum = build_candidate(
        args.checkout, args.output_base, kind=args.corpus,
        builder_commit=args.builder_commit, release_id=args.release_id,
    )
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
