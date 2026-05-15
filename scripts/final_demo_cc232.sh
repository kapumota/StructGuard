#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/final_demo_cc232.sh /path/to/Libreria_cc232/Semana2/include" >&2
  exit 2
fi
TARGET="$1"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
OUT="report/demo_cc232"
mkdir -p "$OUT"
python -m structguard.cli analyze "$TARGET" --headers-only --dsl contracts/cc232_core.sgdsl --html "$OUT/analysis.html" --json "$OUT/analysis.json"
python -m structguard.cli docs "$TARGET" --headers-only --dsl contracts/cc232_core.sgdsl --docs-html "$OUT/docs.html" --markdown-dir "$OUT/docs_md" --docs-json "$OUT/docs.json"
python -m structguard.cli security "$TARGET" --headers-only --deep --html "$OUT/security.html" --security-json "$OUT/security.json" --rules-json "$OUT/security_rules.json"
python -m structguard.cli fuzz "$TARGET" --headers-only --fuzz-html "$OUT/fuzz.html" --fuzz-json "$OUT/fuzz.json" --replay "$OUT/replay.py" --seed-corpus "$OUT/seed_corpus" --emit-tests --test-dir "$OUT/generated_tests"
python -m structguard.cli perf "$TARGET" --headers-only --perf-html "$OUT/perf.html" --perf-json "$OUT/perf.json" --perf-md "$OUT/perf.md" --growth-json "$OUT/growth.json" --harness "$OUT/perf_harness.cpp"
python -m structguard.cli ci "$TARGET" --headers-only --policy structguard.yml --deep-security --html "$OUT/ci.html" --json "$OUT/ci.json" --junit "$OUT/junit.xml" --sarif "$OUT/structguard.sarif" --summary-md "$OUT/summary.md"
printf 'CC-232 demo artifacts written to %s\n' "$OUT"
