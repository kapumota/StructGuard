#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-examples}
mkdir -p report/v4_5
PYTHONPATH=src python -m structguard.cli perf "$ROOT" --headers-only \
  --perf-html report/v4_5/perf.html \
  --perf-json report/v4_5/perf.json \
  --perf-md report/v4_5/perf.md \
  --growth-json report/v4_5/growth.json \
  --harness report/v4_5/sg_perf_harness.cpp \
  -v
