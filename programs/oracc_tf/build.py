"""Public P-001 M6 build API.

The integrated source graph and the Text-Fabric projection are deliberately
separate. ``build_core`` owns source-faithful cardinalities and the explicit
anchor projection required by TF's warp constraints; ``tfprojection`` owns
serialization/runtime configuration. Keeping the latter out of the source
graph makes TF-specific workarounds auditable instead of source semantics.
"""

from .build_core import (
    BuildError,
    CorpusGraph,
    CorpusInvariantCensus,
    DocumentNode,
    DuplicateGraphNode,
    ExportResult,
    build_editions,
    census,
)
from .tfprojection import export_tf, export_tf_editions

__all__ = (
    "BuildError",
    "CorpusGraph",
    "CorpusInvariantCensus",
    "DocumentNode",
    "DuplicateGraphNode",
    "ExportResult",
    "build_editions",
    "census",
    "export_tf",
    "export_tf_editions",
)
