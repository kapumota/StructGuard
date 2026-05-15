#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p report
python -m structguard.cli --version
python -m structguard.cli analyze examples/stack_ok.h --headers-only --html report/smoke_analysis.html --json report/smoke_analysis.json
python -m structguard.cli docs examples/stack_ok.h --headers-only --docs-html report/smoke_docs.html --markdown-dir report/smoke_docs_md --docs-json report/smoke_docs.json
python -m structguard.cli security examples/stack_ok.h --headers-only --deep --html report/smoke_security.html --security-json report/smoke_security.json
python -m structguard.cli perf examples/stack_ok.h --headers-only --perf-html report/smoke_perf.html --perf-json report/smoke_perf.json --growth-json report/smoke_growth.json
pytest -q
