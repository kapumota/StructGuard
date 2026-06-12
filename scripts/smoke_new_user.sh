#!/usr/bin/env bash
set -euo pipefail

mkdir -p report

python -m pip install -e .

structguard doctor . --json report/smoke_new_user_doctor.json

structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset contracts \
  --headers-only \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --report-json report/smoke_new_user_report.json

python -m json.tool report/smoke_new_user_doctor.json > /dev/null
python -m json.tool report/smoke_new_user_report.json > /dev/null
