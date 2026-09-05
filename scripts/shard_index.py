#!/usr/bin/env python3
"""Split oversized ORACC index JSON files with bounded memory, and rejoin them.

Source/shard payloads are parsed incrementally. A temporary stdlib SQLite spool
provides disk-backed ordering, duplicate detection, and digest sorting, so heap
usage depends on parser buffers and the largest single JSON value rather than
on total corpus size.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

MANIFEST = "_index.json"
KEYS_PREFIX = "keys-"
MAP_FILE = "map.json"
DEFAULT_MAX_MB = 90
STREAM_CHUNK_CHARS = 1 << 20


class ShardIndexError(ValueError):
    pass


class IndexFormatError(ShardIndexError):
    pass


class ShardSizeError(ShardIndexError):
    pass


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def digest_keys(entries):
    """Legacy v1 order-independent digest of a materialized keys iterable."""
    parts = sorted(hashlib.sha1(canon(e).encode()).hexdigest() for e in entries)
    return hashlib.sha1("".join(parts).encode()).hexdigest()


def digest_map(mapping):
    """Legacy v1 canonical map digest."""
    return hashlib.sha1(canon(mapping).encode()).hexdigest()


def bucket_of(key, depth=1):
    """Lowercased ASCII-alphanumeric prefix, else ``other``."""
    if not key:
        return "other"
    out = ""
    for ch in key[:depth].lower():
        if not (ch.isascii() and ch.isalnum()):
            return "other"
        out += ch
    return out or "other"


def dump(obj, path):
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, indent=2, ensure_ascii=False)


class _JsonStream:
    """Incremental JSON reader around ``JSONDecoder.raw_decode``."""

    def __init__(self, fp, *, chunk_chars=STREAM_CHUNK_CHARS):
        self.fp = fp
        self.chunk_chars = max(4, int(chunk_chars))
        self.decoder = json.JSONDecoder()
        self.buf = ""
        self.pos = 0
        self.eof = False

    def _fill(self):
        if self.eof:
            return False
        if self.pos and (self.pos >= self.chunk_chars or self.pos > len(self.buf) // 2):
            self.buf = self.buf[self.pos :]
            self.pos = 0
        chunk = self.fp.read(self.chunk_chars)
        if chunk:
            self.buf += chunk
            return True
        self.eof = True
        return False

    def _ensure(self):
        while self.pos >= len(self.buf):
            if not self._fill():
                return False
        return True

    def skip_ws(self):
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos].isspace():
                self.pos += 1
            if self.pos < len(self.buf) or not self._fill():
                return

    def peek(self):
        self.skip_ws()
        return self.buf[self.pos] if self._ensure() else None

    def consume(self, wanted):
        got = self.peek()
        if got != wanted:
            raise IndexFormatError(f"expected {wanted!r}, got {got!r}")
        self.pos += 1

    def value(self):
        self.skip_ws()
        while True:
            if not self._ensure():
                raise IndexFormatError("unexpected end of JSON input")
            try:
                value, end = self.decoder.raw_decode(self.buf, self.pos)
            except json.JSONDecodeError as exc:
                incomplete = (
                    exc.pos >= len(self.buf) - 1
                    or exc.msg.startswith("Unterminated string")
                    or exc.msg.startswith("Invalid \\uXXXX escape")
                )
                if self.eof or not incomplete:
                    raise IndexFormatError(
                        f"invalid JSON near character {exc.pos}: {exc.msg}"
                    ) from exc
                self._fill()
                continue
            self.pos = end
            return value

    def array(self, callback):
        self.consume("[")
        if self.peek() == "]":
            self.pos += 1
            return
        while True:
            callback(self.value())
            got = self.peek()
            if got == ",":
                self.pos += 1
            elif got == "]":
                self.pos += 1
                return
            else:
                raise IndexFormatError(f"expected ',' or ']' in array, got {got!r}")

    def obj(self, callback):
        self.consume("{")
        if self.peek() == "}":
            self.pos += 1
            return
        while True:
            key = self.value()
            if not isinstance(key, str):
                raise IndexFormatError("JSON object key must be a string")
            self.consume(":")
            callback(key, self.value())
            got = self.peek()
            if got == ",":
                self.pos += 1
            elif got == "}":
                self.pos += 1
                return
            else:
                raise IndexFormatError(f"expected ',' or '}}' in object, got {got!r}")

    def finish(self):
        self.skip_ws()
        if self._ensure():
            raise IndexFormatError("trailing data after top-level JSON object")


def _stream_index(path, on_key=None, on_map=None, *, require_keys=True):
    """Stream top-level ``keys``/``map`` while retaining ordinary metadata."""
    meta = {}
    seen = set()
    saw_keys = False
    has_map = False
    with open(path, encoding="utf-8") as fp:
        r = _JsonStream(fp)
        r.consume("{")
        if r.peek() == "}":
            r.pos += 1
        else:
            while True:
                field = r.value()
                if not isinstance(field, str):
                    raise IndexFormatError("top-level JSON key must be a string")
                if field in seen:
                    raise IndexFormatError(f"duplicate top-level field: {field}")
                seen.add(field)
                r.consume(":")
                if field == "keys":
                    saw_keys = True
                    r.array(on_key or (lambda _x: None))
                elif field == "map":
                    has_map = True
                    r.obj(on_map or (lambda _k, _v: None))
                else:
                    meta[field] = r.value()
                got = r.peek()
                if got == ",":
                    r.pos += 1
                elif got == "}":
                    r.pos += 1
                    break
                else:
                    raise IndexFormatError(
                        f"expected ',' or '}}' at top level, got {got!r}"
                    )
        r.finish()
    if require_keys and not saw_keys:
        raise IndexFormatError(f"{path}: no top-level 'keys' array")
    return meta, saw_keys, has_map


class _Spool:
    """Disk-backed state; payload storage is optional for verify/join."""

    def __init__(self, path, *, keep_payload=False):
        self.keep_payload = keep_payload
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=OFF")
        self.conn.execute("PRAGMA synchronous=OFF")
        self.conn.execute("PRAGMA temp_store=FILE")
        self.conn.execute("PRAGMA cache_size=-8192")
        self.conn.execute(
            "CREATE TABLE keys (seq INTEGER PRIMARY KEY, payload TEXT, digest TEXT NOT NULL, "
            "b1 TEXT, b2 TEXT, final_label TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE map (seq INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, "
            "value_json TEXT NOT NULL)"
        )
        self.key_count = 0
        self.map_count = 0

    def add_key(self, entry, *, route=False):
        if not isinstance(entry, dict):
            raise IndexFormatError("keys array entries must be JSON objects")
        key = entry.get("key", "")
        if not isinstance(key, str):
            raise IndexFormatError("keys[].key must be a string when present")
        payload = canon(entry)
        self.key_count += 1
        self.conn.execute(
            "INSERT INTO keys(seq,payload,digest,b1,b2) VALUES(?,?,?,?,?)",
            (
                self.key_count,
                payload if self.keep_payload else None,
                hashlib.sha1(payload.encode()).hexdigest(),
                bucket_of(key) if route else None,
                bucket_of(key, 2) if route else None,
            ),
        )

    def add_map(self, key, value):
        self.map_count += 1
        try:
            self.conn.execute(
                "INSERT INTO map(seq,key,value_json) VALUES(?,?,?)",
                (self.map_count, key, canon(value)),
            )
        except sqlite3.IntegrityError as exc:
            raise IndexFormatError(f"duplicate map key: {key}") from exc

    def finish(self):
        self.conn.commit()

    def keys_digest(self):
        h = hashlib.sha1()
        for (part,) in self.conn.execute("SELECT digest FROM keys ORDER BY digest"):
            h.update(part.encode("ascii"))
        return h.hexdigest()

    def map_digest(self):
        h = hashlib.sha1(b"{")
        first = True
        for key, value in self.conn.execute(
            "SELECT key,value_json FROM map ORDER BY key COLLATE BINARY"
        ):
            if not first:
                h.update(b", ")
            h.update(canon(key).encode())
            h.update(b": ")
            h.update(value.encode())
            first = False
        h.update(b"}")
        return h.hexdigest()

    def state(self, has_map):
        self.finish()
        return (
            self.key_count,
            self.keys_digest(),
            self.map_count if has_map else 0,
            self.map_digest() if has_map else None,
        )

    def close(self):
        self.conn.close()


def _field_size(key, value):
    return len(
        (
            json.dumps(key, ensure_ascii=False, separators=(",", ":"))
            + ":"
            + json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        ).encode()
    )


def _shard_size(meta, label, payload_bytes, count):
    fields = list(meta.items()) + [("section", "keys"), ("shard", label)]
    size = 2 + len(b'"keys":[]') + payload_bytes + max(0, count - 1)
    if fields:
        size += sum(_field_size(k, v) for k, v in fields) + len(fields)
    return size


def _plan_shards(spool, meta, limit):
    groups = spool.conn.execute(
        "SELECT b1,COUNT(*),COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) "
        "FROM keys GROUP BY b1 ORDER BY b1"
    ).fetchall()
    for b1, count, payload_bytes in groups:
        if _shard_size(meta, b1, payload_bytes, count) <= limit:
            spool.conn.execute("UPDATE keys SET final_label=? WHERE b1=?", (b1, b1))
            continue
        if b1 == "other":
            raise ShardSizeError(f"keys-other.json exceeds shard size limit {limit} bytes")
        subgroups = spool.conn.execute(
            "SELECT b2,COUNT(*),COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) "
            "FROM keys WHERE b1=? GROUP BY b2 ORDER BY b2",
            (b1,),
        ).fetchall()
        for b2, sub_count, sub_bytes in subgroups:
            actual = _shard_size(meta, b2, sub_bytes, sub_count)
            if actual > limit:
                raise ShardSizeError(
                    f"keys-{b2}.json would be {actual} bytes, exceeding shard size "
                    f"limit {limit} bytes"
                )
        spool.conn.execute("UPDATE keys SET final_label=b2 WHERE b1=?", (b1,))
    spool.conn.commit()
    return [
        x[0]
        for x in spool.conn.execute(
            "SELECT DISTINCT final_label FROM keys ORDER BY final_label"
        )
    ]


def _write_fields(fp, fields):
    first = True
    for key, value in fields:
        if not first:
            fp.write(",")
        fp.write(json.dumps(key, ensure_ascii=False, separators=(",", ":")))
        fp.write(":")
        fp.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        first = False
    return first


def _write_key_shard(path, meta, label, spool):
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("{")
        empty = _write_fields(fp, [*meta.items(), ("section", "keys"), ("shard", label)])
        if not empty:
            fp.write(",")
        fp.write('"keys":[')
        first = True
        for (payload,) in spool.conn.execute(
            "SELECT payload FROM keys WHERE final_label=? ORDER BY seq", (label,)
        ):
            if not first:
                fp.write(",")
            fp.write(payload)
            first = False
        fp.write("]}")


def _write_map_shard(path, meta, spool):
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("{")
        empty = _write_fields(fp, [*meta.items(), ("section", "map")])
        if not empty:
            fp.write(",")
        fp.write('"map":{')
        first = True
        for key, value in spool.conn.execute(
            "SELECT key,value_json FROM map ORDER BY seq"
        ):
            if not first:
                fp.write(",")
            fp.write(json.dumps(key, ensure_ascii=False, separators=(",", ":")))
            fp.write(":")
            fp.write(value)
            first = False
        fp.write("}}")


def _publish_dir(staged, outdir):
    """Replace a completed directory; restore the old one on immediate failure."""
    staged = Path(staged)
    outdir = Path(outdir)
    if not outdir.exists():
        os.replace(staged, outdir)
        return
    backup = outdir.parent / f".{outdir.name}.backup-{os.getpid()}"
    if backup.exists():
        shutil.rmtree(backup)
    os.replace(outdir, backup)
    try:
        os.replace(staged, outdir)
    except Exception:
        os.replace(backup, outdir)
        raise
    else:
        shutil.rmtree(backup)


def _manifest(indir):
    with open(Path(indir) / MANIFEST, encoding="utf-8") as fp:
        result = json.load(fp)
    if not isinstance(result.get("split"), dict):
        raise IndexFormatError(f"{indir}: invalid shard manifest")
    return result


def split(src, outdir, max_mb=DEFAULT_MAX_MB, dry_run=False):
    src = Path(src)
    outdir = Path(outdir)
    if max_mb <= 0:
        raise ShardSizeError("max_mb must be positive")
    limit = int(max_mb * 1024 * 1024)
    outdir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".shard-index-", dir=outdir.parent) as td:
        work = Path(td)
        spool = _Spool(work / "spool.sqlite", keep_payload=True)
        try:
            meta, _saw_keys, has_map = _stream_index(
                src,
                lambda e: spool.add_key(e, route=True),
                spool.add_map,
            )
            spool.finish()
            shards = _plan_shards(spool, meta, limit)
            manifest = {
                **meta,
                "split": {
                    "tool": "scripts/shard_index.py",
                    "scheme": "keys[] sharded by lowercased alphanumeric key prefix; 'other' = non-alphanumeric or empty key",
                    "source_file": src.name,
                    "shards": shards,
                    "has_map": has_map,
                    "note": "join reorders keys by shard; ORACC's original order is hash order and carries no meaning",
                    "verify": {
                        "keys_count": spool.key_count,
                        "keys_digest": spool.keys_digest(),
                        "map_count": spool.map_count if has_map else 0,
                        "map_digest": spool.map_digest() if has_map else None,
                    },
                },
            }
            if dry_run:
                print(f"{len(shards)} shards (dry run, nothing written)")
                for label in shards:
                    count, size = spool.conn.execute(
                        "SELECT COUNT(*),COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) "
                        "FROM keys WHERE final_label=?",
                        (label,),
                    ).fetchone()
                    print(
                        f"  {KEYS_PREFIX}{label}.json  "
                        f"{_shard_size(meta,label,size,count)/1048576:7.1f} MB  "
                        f"{count:>9,} entries"
                    )
                return
            publish = work / "publish"
            publish.mkdir()
            dump(manifest, publish / MANIFEST)
            if has_map:
                _write_map_shard(publish / MAP_FILE, meta, spool)
            for label in shards:
                _write_key_shard(publish / f"{KEYS_PREFIX}{label}.json", meta, label, spool)
            oversized = [p.name for p in publish.iterdir() if p.stat().st_size > limit]
            if oversized:
                raise ShardSizeError(
                    f"output exceeds shard size limit {limit} bytes: {', '.join(oversized)}"
                )
        finally:
            spool.close()

        if verify(publish, quiet=True):
            raise ShardIndexError("staged shards failed manifest verification")
        files = list(publish.iterdir())
        total = sum(p.stat().st_size for p in files)
        biggest = max(files, key=lambda p: p.stat().st_size).name
        _publish_dir(publish, outdir)

    print(f"split {src} -> {outdir}")
    print(f"  {len(shards)} key shards{' + map.json' if has_map else ''} + {MANIFEST}")
    print(
        f"  {src.stat().st_size/1048576:.1f} MB -> {total/1048576:.1f} MB "
        f"in {len(files)} files"
    )
    print(f"  largest: {biggest} ({(outdir/biggest).stat().st_size/1048576:.1f} MB)")


def _stream_key_shard(path, label, callback):
    meta, saw_keys, has_map = _stream_index(path, callback, require_keys=True)
    if has_map or meta.get("section") != "keys" or meta.get("shard") != label:
        raise IndexFormatError(f"{path}: key shard metadata does not match {label!r}")
    return saw_keys


def _stream_map_shard(path, callback):
    meta, saw_keys, has_map = _stream_index(
        path, on_map=callback, require_keys=False
    )
    if saw_keys or not has_map or meta.get("section") != "map":
        raise IndexFormatError(f"{path}: invalid map shard")


def _shard_state(indir, spec, db_path):
    spool = _Spool(db_path)
    try:
        for label in spec.get("shards", []):
            _stream_key_shard(
                Path(indir) / f"{KEYS_PREFIX}{label}.json", label, spool.add_key
            )
        has_map = bool(spec.get("has_map"))
        if has_map:
            _stream_map_shard(Path(indir) / MAP_FILE, spool.add_map)
        return spool.state(has_map)
    finally:
        spool.close()


def _source_state(path, db_path):
    spool = _Spool(db_path)
    try:
        _meta, _saw_keys, has_map = _stream_index(path, spool.add_key, spool.add_map)
        return spool.state(has_map)
    finally:
        spool.close()


def verify(indir, against=None, *, quiet=False):
    indir = Path(indir)
    manifest = _manifest(indir)
    spec = manifest["split"]
    want = spec.get("verify", {})
    expected = (
        want.get("keys_count"),
        want.get("keys_digest"),
        want.get("map_count"),
        want.get("map_digest"),
    )
    with tempfile.TemporaryDirectory(prefix=".shard-verify-", dir=indir.parent) as td:
        got = _shard_state(indir, spec, Path(td) / "shards.sqlite")
        original = _source_state(against, Path(td) / "source.sqlite") if against else None
    labels = ("keys count ", "keys digest", "map count  ", "map digest ")
    ok = got == expected
    if not quiet:
        for label, actual, exp in zip(labels, got, expected):
            shown = f"{actual:,}" if isinstance(actual, int) else actual
            print(f"  [{'ok  ' if actual == exp else 'FAIL'}] {label}  {shown}")
    if original is not None:
        same_keys, same_map = original[:2] == got[:2], original[2:] == got[2:]
        ok = ok and same_keys and same_map
        if not quiet:
            print(f"  [{'ok  ' if same_keys else 'FAIL'}] keys match {against}")
            print(f"  [{'ok  ' if same_map else 'FAIL'}] map  match {against}")
    if not quiet:
        print("VERIFIED" if ok else "VERIFICATION FAILED")
    return 0 if ok else 1


def join(indir, out):
    indir = Path(indir)
    out = Path(out)
    manifest = _manifest(indir)
    spec = manifest["split"]
    want = spec.get("verify", {})
    expected = (
        want.get("keys_count"), want.get("keys_digest"),
        want.get("map_count"), want.get("map_digest"),
    )
    meta = {k: v for k, v in manifest.items() if k != "split"}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".shard-join-", dir=out.parent) as td:
        work = Path(td)
        tmp = work / "joined.json"
        spool = _Spool(work / "state.sqlite")
        try:
            with open(tmp, "w", encoding="utf-8") as fp:
                fp.write("{")
                empty = _write_fields(fp, meta.items())
                if not empty:
                    fp.write(",")
                fp.write('"keys":[')
                first = True

                def emit_key(entry):
                    nonlocal first
                    if not first:
                        fp.write(",")
                    fp.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
                    first = False
                    spool.add_key(entry)

                for label in spec.get("shards", []):
                    _stream_key_shard(indir / f"{KEYS_PREFIX}{label}.json", label, emit_key)
                fp.write("]")
                has_map = bool(spec.get("has_map"))
                if has_map:
                    fp.write(',"map":{')
                    first_map = True

                    def emit_map(key, value):
                        nonlocal first_map
                        if not first_map:
                            fp.write(",")
                        fp.write(json.dumps(key, ensure_ascii=False, separators=(",", ":")))
                        fp.write(":")
                        fp.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
                        first_map = False
                        spool.add_map(key, value)

                    _stream_map_shard(indir / MAP_FILE, emit_map)
                    fp.write("}")
                fp.write("}")
            got = spool.state(has_map)
        finally:
            spool.close()
        if got != expected:
            print(f"join {indir} -> {out}  ({got[0]:,} keys, staged digest mismatch)")
            print("WARNING: digest mismatch")
            return 1
        size = tmp.stat().st_size
        os.replace(tmp, out)
    print(f"join {indir} -> {out}  ({got[0]:,} keys, {size/1048576:.1f} MB)")
    print("VERIFIED against manifest")
    return 0


def load_shards(indir):
    """Compatibility helper; unlike CLI operations this intentionally materializes."""
    indir = Path(indir)
    manifest = _manifest(indir)
    spec = manifest["split"]
    entries = []
    for label in spec.get("shards", []):
        _stream_key_shard(indir / f"{KEYS_PREFIX}{label}.json", label, entries.append)
    mapping = None
    if spec.get("has_map"):
        mapping = {}

        def add_map(key, value):
            if key in mapping:
                raise IndexFormatError(f"duplicate map key: {key}")
            mapping[key] = value

        _stream_map_shard(indir / MAP_FILE, add_map)
    return manifest, spec, entries, mapping


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("input")
    s.add_argument("-o", "--outdir")
    s.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--replace", action="store_true")
    j = sub.add_parser("join")
    j.add_argument("indir")
    j.add_argument("-o", "--output", required=True)
    v = sub.add_parser("verify")
    v.add_argument("indir")
    v.add_argument("--against")
    args = ap.parse_args()
    try:
        if args.cmd == "split":
            default = args.input[:-5] if args.input.endswith(".json") else args.input + ".shards"
            outdir = args.outdir or default
            split(args.input, outdir, args.max_mb, args.dry_run)
            if args.replace and not args.dry_run:
                if verify(outdir):
                    raise ShardIndexError("shards did not verify; source file left in place")
                os.remove(args.input)
                print(f"removed {args.input}")
            return 0
        if args.cmd == "join":
            return join(args.indir, args.output)
        return verify(args.indir, args.against)
    except ShardIndexError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    sys.exit(main())
