# ETCSRI — installation, browsing and source-grounded queries

## Use the published Text-Fabric corpus

Download [ETCSRI 0.1.0](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/etcsri-0.1.0.zip) and its
[SHA-256 checksum](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/etcsri-0.1.0.zip.sha256).
Check the digest, unpack the ZIP and install only `text-fabric==13.1.0`.
From the unpacked archive root run
`python -m tf.browser.start "app:$PWD/app" "--modules=" -noweb`.
The bundled `app/` discovers `tf/0.1.0/` without conversion or the ORACC-TF wheel.
TFQL is used for advanced browser queries; ordinary form search remains on the product backlog.

## Optional: convert an ORACC JSON source directory

Install the **code-only** ORACC-TF package wheel built from this repository, and Text-Fabric 13.1.0. Supply your own `etcsri/corpusjson/*.json` source snapshot; the converter does not download or silently fix the data. This optional conversion command does not use or modify the published archive.

```bash
python -m pip install /path/to/oracc_tf-*.whl "text-fabric==13.1.0"
python -m oracc_tf build-etcsri --source-dir /path/to/etcsri --output ./etcsri-tf
python -m oracc_tf prepare-local-app --kind etcsri --tf-dir ./etcsri-tf --app-dir ./etcsri-app
python -m tf.browser.start "app:$PWD/etcsri-app" "--locations=$PWD/etcsri-tf" "--modules=" -noweb
```

For a small independent check, add `--text-id Q000935` to `build-etcsri`. A nonempty TF output directory is rejected to prevent accidental overwrites. The locally generated app is a development preview, separate from the already published release.

## Query actual morphology

```python
from tf.fabric import Fabric

tf = Fabric(locations="./etcsri-tf", silent="deep")
assert tf.loadAll(silent="deep")
api = tf.api
docs = [n for n in api.F.otype.s("document")
        if api.F.document_key.v(n) == "etcsri:Q000935"]
assert len(docs) == 1

words = [n for n in api.F.otype.s("word")
         if api.F.document_key.v(n) == "etcsri:Q000935"]
for word in words[:5]:
    print(api.F.form.v(word), api.F.base.v(word),
          api.F.morph.v(word), api.F.morph2.v(word))
```

The app's default text rendering `text-trans-full` displays transliteration. The published ZIP already contains the sibling `tf/<version>/` and `app/` directories, install only Text-Fabric and follow the archive's `README.md` / `docs/reference/installation.md` without rebuilding. Confirm its checksum against the [public release](https://github.com/alexsosn/ORACC-TF/releases/tag/native-v0.1.0). The JSON-derived graph does not supply a running translation.

