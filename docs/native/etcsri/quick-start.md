# ETCSRI — installation, browsing and source-grounded queries

## Convert an ORACC JSON source directory

Install the **code-only** ORACC-TF package wheel built from this repository, and Text-Fabric 13.1.0. Supply your own `etcsri/corpusjson/*.json` source snapshot; the converter does not download or silently fix the data. No released ETCSRI TF archive is implied by the command below.

```bash
python -m pip install /path/to/oracc_tf-*.whl "text-fabric==13.1.0"
python -m oracc_tf build-etcsri --source-dir /path/to/etcsri --output ./etcsri-tf
python -m oracc_tf prepare-local-app --kind etcsri --tf-dir ./etcsri-tf --app-dir ./etcsri-app
python -m tf.browser.start "app:$PWD/etcsri-app" "--locations=$PWD/etcsri-tf" "--modules=" -noweb
```

For a small independent check, add `--text-id Q000935` to `build-etcsri`. A nonempty TF output directory is rejected to prevent accidental overwrites. The local app is labelled **preview** until a separately verified distribution is published.

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

The app's default text rendering `text-trans-full` displays transliteration. If a future release archive contains a sibling `tf/<version>/` and `app/`, use the included archive README to load that **versioned** path directly without rebuilding. Until publication, no stable download URL or translation coverage is claimed.

