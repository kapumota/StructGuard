#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-examples/stack_ok.h}"
mkdir -p report

PYTHONPATH=src python -m structguard.cli analyze "$ROOT" --headers-only \
  --html report/demo_analysis.html \
  --json report/demo_analysis.json \
  -v

PYTHONPATH=src python -m structguard.cli suggest "$ROOT" --headers-only \
  --patch report/demo_contracts.patch \
  --apply-to report/demo_annotated \
  --suggestions-json report/demo_suggestions.raw.json \
  --html report/demo_suggestions.html \
  -v

echo "Reportes generados en report/. Para ejecutar la demostración con falla intencional, usa scripts/demo_bug_detection.sh."