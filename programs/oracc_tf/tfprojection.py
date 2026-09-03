"""Text-Fabric serialization for the integrated P-001 M6 graph.

Text-Fabric 13.1 requires every non-slot node to map to at least one slot.
``build_core`` therefore keeps synthetic anchors explicit and separate from
semantic source signs. This module adds only TF runtime configuration; it
must not reinterpret source cardinalities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from . import build_core as core
from . import loader, metadata


def _tf_payload(graph: core.CorpusGraph):
    """Return a loadable TF payload without changing graph semantics."""
    node_features, edge_features, meta_data = core._tf_payload(graph)

    # A present-but-empty otext config makes TF 13.1 attempt __characters__
    # without a text format and Fabric.load() fails. M6 only requires the warp
    # to load; one Unicode format is sufficient and mirrors the cuneiform
    # convention used by Nino-cunei/oldbabylonian. Section API configuration
    # remains separate because metadata-only stubs have no physical face/line
    # path by design.
    meta_data["otext"] = {
        "fmt:text-orig-unicode": "{utf8}",
    }
    return node_features, edge_features, meta_data


def export_tf_editions(
    editions: Sequence[loader.Edition] | Iterable[loader.Edition],
    output_dir: Path,
    *,
    metadata_index: metadata.MetadataIndex | None = None,
) -> core.ExportResult:
    """Build and write a TF dataset, returning graph and invariant census."""
    from tf.fabric import Fabric

    graph = core.build_editions(editions, metadata_index=metadata_index)
    result = core._census_graph(graph)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    node_features, edge_features, meta_data = _tf_payload(graph)
    TF = Fabric(locations=str(output_dir), modules=[""], silent="deep")
    good = bool(
        TF.save(
            nodeFeatures=node_features,
            edgeFeatures=edge_features,
            metaData=meta_data,
            location=str(output_dir),
            module="",
            silent="deep",
        )
    )
    return core.ExportResult(
        graph=graph,
        census=result,
        output_dir=output_dir,
        good=good,
    )


def export_tf(data: Path, output_dir: Path) -> core.ExportResult:
    """Build the complete in-scope RIAO+RINAP TF graph and write it to disk."""
    index = metadata.load_index(data)
    return export_tf_editions(
        loader.iter_editions(data, skip_unreadable=True),
        output_dir,
        metadata_index=index,
    )
