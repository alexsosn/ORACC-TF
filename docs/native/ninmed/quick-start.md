# NINMED — build, browse and query the source edition

## Use the published Text-Fabric corpus

Download [NINMED 0.1.0](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip) and the matching
[SHA-256 checksum](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip.sha256).
Check the digest, unpack the ZIP, and install only `text-fabric==13.1.0`.
From the extracted archive root use
`python -m tf.browser.start "app:$PWD/app" "--modules=" -noweb`.
No converter wheel, original JSON archive or Git repository clone is needed.
The browser supports advanced TFQL, while non-TFQL catalogue/form search is
still being developed in [issue #189](https://github.com/alexsosn/ORACC-TF/issues/189).

## Optional: rebuild from ORACC primary JSON

Install a locally built code-only ORACC-TF wheel with Text-Fabric 13.1.0, and supply a separate `asbp/ninmed/corpusjson/` source directory. The wheel does not contain third-party medical editions.

```bash
python -m pip install /path/to/oracc_tf-*.whl "text-fabric==13.1.0"
python -m oracc_tf build-ninmed --source-dir /path/to/asbp/ninmed --output ./ninmed-tf --skip-known-empty
python -m oracc_tf prepare-local-app --kind ninmed --tf-dir ./ninmed-tf --app-dir ./ninmed-app
python -m tf.browser.start "app:$PWD/ninmed-app" "--locations=$PWD/ninmed-tf" "--modules=" -noweb
```

The `--skip-known-empty` flag applies only to the full-source run and authorizes exclusion of exactly `P395407.json`. It does not make other malformed/empty JSON acceptable. To test a single real edition, omit the skip flag and use `--text-id P285136`. The converter refuses a nonempty output directory and rejects mismatched embedded source text IDs.

## Inspect the native ORACC lemmatisation

```python
from tf.fabric import Fabric

tf = Fabric(locations="./ninmed-tf", silent="deep")
assert tf.loadAll(silent="deep")
api = tf.api
words = [n for n in api.F.otype.s("word")
         if api.F.document_key.v(n) == "asbp/ninmed:P285136"]
example = next(n for n in words if api.F.source_id.v(n) == "P285136.l003f2")
print(api.F.form.v(example), api.F.cf.v(example),
      api.F.gw.v(example), api.F.pos.v(example))
for lex in api.E.word_lex.f(example):
    print(api.F.cf.v(lex), api.F.gw.v(lex), api.F.pos.v(lex))
```

Use TF's `text-trans-full` rendering for transliteration and inspect `sign` features for available Unicode cuneiform. The published 0.1.0 archive contains `tf/<version>/` and `app/` and can be used with only Text-Fabric. Verify the ZIP, SHA-256 and manifest from the [public release](https://github.com/alexsosn/ORACC-TF/releases/tag/native-v0.1.0). The `prepare-local-app` command above still creates a separate development preview.

