from __future__ import annotations

import math

import pytest

from oracc_tf.archive_security import ArchiveLimits, ArchiveResourceLimitError


@pytest.mark.parametrize("ratio", [math.nan, math.inf, -math.inf])
def test_archive_limits_reject_non_finite_compression_ratio(ratio: float) -> None:
    """A non-finite ceiling must not disable compression-ratio enforcement."""
    with pytest.raises(ArchiveResourceLimitError):
        ArchiveLimits(
            max_download_bytes=1_000_000,
            max_members=100,
            max_member_uncompressed_bytes=100_000,
            max_total_uncompressed_bytes=500_000,
            max_compression_ratio=ratio,
        )
