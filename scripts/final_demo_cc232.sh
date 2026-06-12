#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: scripts/final_demo_cc232.sh /ruta/a/Libreria_cc232/Semana2/include" >&2
  exit 2
fi

TARGET="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

OUT="report/demo_cc232"
mkdir -p "$OUT"

python -m structguard.cli scan "$TARGET" \
  --profile cc232 \
  --preset ci \
  --headers-only \
  --report-json "$OUT/report.json" \
  --lockfile "$OUT/structguard.lock"

python -m structguard.cli report derive "$OUT/report.json" \
  --sarif "$OUT/structguard.sarif"

python -m structguard.cli testgen "$TARGET" \
  --headers-only \
  --contract profiles/cc232/contracts/cc232_core.sgdsl \
  --output-json "$OUT/testgen.json" \
  --output-html "$OUT/testgen.html" \
  --replay-script "$OUT/replay.py" \
  --test-dir "$OUT/generated_tests"

printf 'Artefactos de demostración CC-232 escritos en %s\n' "$OUT"
