"""Assemble a clean researcher manual for one standalone ORACC-TF distribution.

Only canonical researcher-facing reference pages are copied. Distribution staging
already owns the digest/manifest and rollback of the resulting docs support root;
this helper deliberately does not duplicate that machinery.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit


class ManualAssemblyError(ValueError):
    """A local source tree cannot supply a safe, complete researcher manual."""


REQUIRED_REFERENCE_PAGES = (
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

_ALLOWED_REFERENCE_EXTENSIONS = frozenset(
    {".md", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".css"}
)


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _validate_manual_source(repository: Path) -> tuple[Path, tuple[Path, ...]]:
    docs = repository / "docs"
    reference = docs / "reference"
    if docs.is_symlink() or reference.is_symlink():
        raise ManualAssemblyError("canonical docs/reference ancestry contains symlink")
    if not docs.is_dir() or not reference.is_dir():
        raise ManualAssemblyError("missing regular docs/reference directory")
    repository_real = repository.resolve(strict=True)
    reference_real = reference.resolve(strict=True)
    if not _is_within(reference_real, repository_real):
        raise ManualAssemblyError("reference source escapes builder checkout")
    for name in REQUIRED_REFERENCE_PAGES:
        path = reference / name
        if path.is_symlink() or not path.is_file():
            raise ManualAssemblyError(f"required researcher page absent: {name}")
        if "\nstatus: skeleton\n" in path.read_text(encoding="utf-8"):
            raise ManualAssemblyError(f"required researcher page {name} remains skeleton")

    for name in ("CITATION.cff", "LICENSE_SCOPE.md"):
        path = repository / name
        if path.is_symlink() or not path.is_file():
            raise ManualAssemblyError(f"required source document absent: {name}")

    files: list[Path] = []
    for entry in sorted(reference.rglob("*")):
        rel = entry.relative_to(reference)
        if entry.is_symlink():
            raise ManualAssemblyError(f"reference source contains symlink: {rel}")
        if any(part.startswith(".") for part in rel.parts):
            raise ManualAssemblyError(f"reference source contains hidden entry: {rel}")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise ManualAssemblyError(f"reference source contains unsupported entry: {rel}")
        if entry.suffix.lower() not in _ALLOWED_REFERENCE_EXTENSIONS:
            raise ManualAssemblyError(f"reference source contains non-manual file: {rel}")
        files.append(entry)
    return reference, tuple(files)



_LINK_RE = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")


def _validate_internal_links(manual_root: Path) -> None:
    """Check ordinary Markdown file links after all copies, before publication."""
    root = manual_root.resolve(strict=True)
    for markdown in sorted(manual_root.rglob("*.md")):
        source = markdown.read_text(encoding="utf-8")
        for raw in _LINK_RE.findall(source):
            href = raw.strip().split(" ", 1)[0].strip("<>")
            parts = urlsplit(href)
            if parts.scheme in {"http", "https", "mailto"}:
                continue  # Portable external reference.
            if parts.scheme or parts.netloc:
                raise ManualAssemblyError(
                    f"unsupported local/nonportable manual link: {href}"
                )
            if not parts.path:
                continue  # Same-document #anchor.
            linked = (markdown.parent / unquote(parts.path)).resolve(strict=False)
            if not _is_within(linked, root) or not linked.is_file():
                raise ManualAssemblyError(
                    f"broken internal manual link: {markdown.relative_to(manual_root)} "
                    f"-> {href}"
                )


def assemble_manual(
    repository_root: Path | str,
    output_dir: Path | str,
    *,
    dataset: str,
) -> Path:
    """Build `docs/` for P-005's existing `support_roots` staging argument.

    The destination is replaced only after source validation and complete copy.
    A missing source page or a failed copy leaves the previous bundle intact.
    """
    if not isinstance(dataset, str) or not dataset.strip():
        raise ManualAssemblyError("dataset must be a non-empty string")
    repository = Path(repository_root)
    target = Path(output_dir)
    reference, source_files = _validate_manual_source(repository)

    source_real = repository.resolve(strict=True)
    target_real = target.resolve(strict=False)
    if _is_within(target_real, source_real) or _is_within(source_real, target_real):
        raise ManualAssemblyError("destination and builder source overlap")
    if target.is_symlink():
        raise ManualAssemblyError("destination is a symlink")
    if target.exists() and not target.is_dir():
        raise ManualAssemblyError("destination is not a directory")
    target.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-manual-", dir=target.parent))
    candidate = staging / "new"
    old = staging / "old"
    try:
        candidate_reference = candidate / "reference"
        candidate_reference.mkdir(parents=True)
        for src in source_files:
            rel = src.relative_to(reference)
            dest = candidate_reference / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)

        for filename in ("CITATION.cff", "LICENSE_SCOPE.md"):
            shutil.copyfile(repository / filename, candidate / filename)

        (candidate / "index.md").write_text(
            f"# {dataset} researcher manual\n\n"
            "Start with the [quick start](reference/quick-start.md) or "
            "[full reference](reference/index.md).\n\n"
            "The [query guide](reference/query-guide.md), "
            "[citation and source rights](reference/citation.md), "
            "[known issues](reference/known-issues.md), and "
            "[generated features](reference/features.md) are included.\n\n"
            "The [software-only citation record](CITATION.cff) and "
            "[software/data licence boundary](LICENSE_SCOPE.md) are bundled; "
            "upstream corpus content retains its source-specific rights.\n",
            encoding="utf-8",
        )

        _validate_internal_links(candidate)

        if target.exists():
            target.rename(old)
        try:
            candidate.rename(target)
        except OSError:
            if old.exists():
                old.rename(target)
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def main(argv: list[str] | None = None) -> int:
    """Maintainer staging CLI; consuming the released corpus needs no builder."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", default="assyrian-royal-inscriptions")
    args = parser.parse_args(argv)
    result = assemble_manual(
        args.repository_root, args.output, dataset=args.dataset
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
