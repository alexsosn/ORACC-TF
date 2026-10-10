"""Package one already-validated standalone ORACC-TF stage for manual release.

The registered corpus builder, app generator and manual assembler run before
this step. This module never converts data, rewrites the manifest, publishes
a GitHub Release, or claims that a candidate ZIP is publicly downloadable.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


class ReleasePackageError(ValueError):
    """A staged distribution is not ready to be zipped as a reader release."""


REQUIRED_DOCUMENTS = (
    "index.md",
    "quick-start.md",
    "query-guide.md",
    "reproducibility.md",
    "installation.md",
    "model.md",
    "signs.md",
    "words-and-lexemes.md",
    "identity.md",
    "translations.md",
    "features.md",
    "data-audit.md",
    "citation.md",
    "known-issues.md",
    "scope.md",
    "text-formats.md",
    "browser.md",
    "references.md",
    "acknowledgements.md",
)

_RELEASE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}\Z")
_OWNED_STAGE_ROOTS = frozenset({"README.md", "manifest.json", "tf", "app", "docs"})
_FORBIDDEN_DOCS = frozenset({"task-state", "research", "plans"})


def _required_file(root: Path, relative: str) -> None:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ReleasePackageError(f"missing regular release file: {relative}")
    if not path.stat().st_size:
        raise ReleasePackageError(f"missing content in release file: {relative}")


def _stage_files(root: Path) -> tuple[str, str, tuple[Path, ...]]:
    if root.is_symlink() or not root.is_dir():
        raise ReleasePackageError("stage root must be an ordinary directory")
    for entry in root.iterdir():
        if entry.name not in _OWNED_STAGE_ROOTS:
            raise ReleasePackageError(f"forbidden unowned release root: {entry.name}")
    for name in _FORBIDDEN_DOCS:
        if (root / "docs" / name).exists():
            raise ReleasePackageError(f"forbidden development docs path: {name}")

    _required_file(root, "README.md")
    _required_file(root, "manifest.json")
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleasePackageError("unreadable distribution manifest") from exc
    if not isinstance(manifest, dict):
        raise ReleasePackageError("distribution manifest is not an object")
    dataset = manifest.get("dataset")
    release_id = manifest.get("release_id")
    version = manifest.get("tf_version")
    tf_root = manifest.get("tf_root")
    if not isinstance(dataset, str) or not _RELEASE_RE.fullmatch(dataset):
        raise ReleasePackageError("invalid dataset identity in manifest")
    if not isinstance(release_id, str) or not _RELEASE_RE.fullmatch(release_id):
        raise ReleasePackageError("invalid release_id in manifest")
    if not isinstance(version, str) or not _RELEASE_RE.fullmatch(version):
        raise ReleasePackageError("invalid tf_version in manifest")
    if tf_root != f"tf/{version}":
        raise ReleasePackageError("manifest tf_root must match tf/<tf_version>")
    if not isinstance(manifest.get("builder_commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["builder_commit"]
    ):
        raise ReleasePackageError("invalid builder_commit in manifest")
    if not isinstance(manifest.get("source_state"), str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", manifest["source_state"]
    ):
        raise ReleasePackageError("missing source_state SHA-256 in manifest")
    support = manifest.get("support_roots")
    if not isinstance(support, dict) or not {"app", "docs"} <= set(support):
        raise ReleasePackageError("missing app/docs support_roots in manifest")

    for path in ("otype.tf", "oslots.tf"):
        _required_file(root, f"{tf_root}/{path}")
    _required_file(root, "app/config.yaml")
    _required_file(root, "docs/index.md")
    _required_file(root, "docs/CITATION.cff")
    _required_file(root, "docs/LICENSE_SCOPE.md")
    for doc in REQUIRED_DOCUMENTS:
        _required_file(root, f"docs/reference/{doc}")

    files: list[Path] = []
    for item in sorted(root.rglob("*")):
        rel = item.relative_to(root)
        if item.is_symlink():
            raise ReleasePackageError(f"symlink forbidden in release: {rel}")
        if any(part.startswith(".") for part in rel.parts):
            raise ReleasePackageError(f"hidden release payload forbidden: {rel}")
        if item.is_dir():
            continue
        if not item.is_file():
            raise ReleasePackageError(f"unsupported release path: {rel}")
        files.append(item)
    return dataset, release_id, tuple(files)


def package_release(
    staged_root: str | Path, output_dir: str | Path
) -> tuple[Path, Path]:
    """Create a complete reader ZIP plus sha256sum-compatible sidecar.

    The stage must already have been built, validated and assigned its final
    release identity. Publication and independent download verification are
    later manual steps under issue #23.
    """
    root = Path(staged_root)
    out = Path(output_dir)
    resolved_root = root.resolve(strict=False)
    resolved_out = out.resolve(strict=False)
    if (
        resolved_out == resolved_root
        or resolved_root in resolved_out.parents
        or resolved_out in resolved_root.parents
    ):
        raise ReleasePackageError("archive output overlaps staged corpus source")
    dataset, release_id, files = _stage_files(root)
    archive = out / f"{dataset}-{release_id}.zip"
    checksum = out / f"{dataset}-{release_id}.zip.sha256"
    if archive.exists() or checksum.exists():
        raise ReleasePackageError("release archive or checksum already exists")
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".release-archive-", dir=out) as temp:
        pending = Path(temp)
        temp_zip = pending / archive.name
        temp_sha = pending / checksum.name
        with ZipFile(temp_zip, "w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
            for file in files:
                info = ZipInfo(
                    file.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16  # stable regular-file permissions
                info.file_size = file.stat().st_size
                with file.open("rb") as source, zf.open(info, "w") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
        digest = sha256()
        with temp_zip.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        temp_sha.write_text(
            f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8"
        )
        temp_zip.replace(archive)
        try:
            temp_sha.replace(checksum)
        except OSError:
            archive.unlink(missing_ok=True)
            raise
    return archive, checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    archive, checksum = package_release(args.stage, args.output_dir)
    print(archive)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
