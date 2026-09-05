"""Issue #45: deterministic bounded-buffer regression for shard_index."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_memory", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_split_parser_buffer_does_not_scale_with_total_input(tmp_path, monkeypatch):
    """A many-entry input must not accumulate earlier parser chunks in RAM.

    This is deliberately a structural memory regression rather than an RSS
    threshold: process RSS is noisy across Python/runner versions, while the
    parser buffer is the part of the algorithm that previously risked growing
    with total JSON size.  The SQLite spool is separately configured with a
    bounded cache and stores corpus-sized state on disk.
    """
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    chunk_chars = 4096
    entries = [
        {
            "key": f"p{i:06d}",
            "count": "1",
            "instances": [f"P{i:06d}.1"],
            "payload": "x" * 256,
        }
        for i in range(12_000)
    ]
    src.write_text(
        json.dumps(
            {
                "type": "index",
                "project": "memory-fixture",
                "keys": entries,
                "map": {f"raw-{i:05d}": f"norm-{i:05d}" for i in range(2_000)},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert src.stat().st_size > 4 * 1024 * 1024

    stream_cls = module._JsonStream
    real_init = stream_cls.__init__
    real_fill = stream_cls._fill
    max_buffer_chars = 0

    def forced_init(self, fp, *args, **kwargs):
        return real_init(self, fp, chunk_chars=chunk_chars)

    def measured_fill(self):
        nonlocal max_buffer_chars
        result = real_fill(self)
        max_buffer_chars = max(max_buffer_chars, len(self.buf))
        return result

    monkeypatch.setattr(stream_cls, "__init__", forced_init)
    monkeypatch.setattr(stream_cls, "_fill", measured_fill)

    module.split(src, outdir, max_mb=1)

    assert module.verify(outdir) == 0
    # Individual entries are well below 1 KiB, so a 64 KiB ceiling leaves
    # generous implementation headroom while still being independent of the
    # >4 MiB total input size. A whole-file/ever-growing buffer fails clearly.
    assert max_buffer_chars < 64 * 1024
