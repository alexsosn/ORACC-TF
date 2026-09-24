#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 OUTPUT_ZIP" >&2
  exit 2
fi

output=$1
intermediate=.github/certs/sectigo-incommon-rsa-server-ca-2.pem
fingerprint=$(openssl x509 -in "$intermediate" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')
test "$fingerprint" = "87E01CC4DD0C9D92A3DBD49092FF13F9CD387445CDC57E5B984E1B7721B5B029"
root_bundle=/etc/ssl/certs/ca-certificates.crt
if [[ ! -f "$root_bundle" ]]; then
  root_bundle=/etc/ssl/cert.pem
fi
test -f "$root_bundle"
openssl verify -CAfile "$root_bundle" "$intermediate"
cat "$root_bundle" "$intermediate" > "${RUNNER_TEMP:?}/oracc-ca-bundle.pem"

curl --cacert "$RUNNER_TEMP/oracc-ca-bundle.pem" --fail --location --retry 3 \
  --proto '=https' --tlsv1.2 \
  https://oracc.museum.upenn.edu/riao/downloads/riao-teiCorpus-20241202.zip \
  --output "$output"
python - "$output" <<'PY'
import hashlib
import sys
from pathlib import Path

expected = "b793d8920db58908e3a044b7f2d1a204c1ba0784e880007e0cd7941333e841bd"
actual = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit(f"SHA-256 mismatch: expected {expected}, got {actual}")
print(f"{actual}  {sys.argv[1]}: OK")
PY
