#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-examples}
mkdir -p report/v4_4
PYTHONPATH=src python -m structguard.cli fuzz "$ROOT" \
  --headers-only \
  --seeds 20 \
  --steps 50 \
  --fuzz-json report/v4_4/fuzz_cases.json \
  --fuzz-html report/v4_4/fuzz.html \
  --replay report/v4_4/replay_failures.py \
  --seed-corpus report/v4_4/corpus \
  --emit-tests \
  --test-dir report/v4_4/generated_tests \
  -v
