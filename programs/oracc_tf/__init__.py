"""ORACC-TF: Text-Fabric datasets built from ORACC open data.

Three identities are kept apart on purpose (P-002 Phase 0.1):

    ORACC_STATE   what upstream published; ORACC has no version string of its
                  own, so this is the maximum UTC-timestamp across the
                  archives that fed a build. Set at build time, not here.
    TF_VERSION    this converter's schema version. Changes when the emitted
                  node types or features change.
    __version__   the Python package version.
"""

__version__ = "0.1.0"

TF_VERSION = "0.3.0"