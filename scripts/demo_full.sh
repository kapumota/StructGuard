#!/usr/bin/env bash
set -euo pipefail

ROOT=${1:-examples/stack_ok.h}
mkdir -p report/demo

PYTHONPATH=src python -m structguard.cli analyze "$ROOT" --headers-only --html report/demo/analyze.html --json report/demo/analyze.json
PYTHONPATH=src python -m structguard.cli bench "$ROOT" --headers-only --html report/demo/bench.html --json report/demo/bench.json --metrics-json report/demo/bench_metrics.json --harness report/demo/bench_harness.cpp
PYTHONPATH=src python -m structguard.cli trace "$ROOT" --headers-only --ops 'push:1,push:2,pop,top' --trace-json report/demo/trace_events.json --html report/demo/trace.html --json report/demo/trace.json
PYTHONPATH=src python -m structguard.cli security "$ROOT" --headers-only --html report/demo/security.html --security-json report/demo/security.json
PYTHONPATH=src python -m structguard.cli fuzz "$ROOT" --headers-only --html report/demo/fuzz.html --fuzz-json report/demo/fuzz.json
PYTHONPATH=src python -m structguard.cli ci "$ROOT" --headers-only --html report/demo/ci.html --json report/demo/ci.json
