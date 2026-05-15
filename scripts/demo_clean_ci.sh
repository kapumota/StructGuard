#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

TARGET="${1:-examples/stack_ok.h}"
OUT="report/demo_clean"
mkdir -p "$OUT"

STRICT_ARGS=()
if command -v clang++ >/dev/null 2>&1 || command -v clang >/dev/null 2>&1; then
  STRICT_ARGS=(--strict-ast --std c++17)
else
  echo "ADVERTENCIA: no se encontró clang/clang++; la demostración limpia se ejecutará sin --strict-ast." >&2
fi

python -m structguard.cli analyze "$TARGET" --headers-only "${STRICT_ARGS[@]}" \
  --html "$OUT/analyze.html" \
  --json "$OUT/analyze.json"

python -m structguard.cli docs "$TARGET" --headers-only \
  --docs-html "$OUT/docs.html" \
  --markdown-dir "$OUT/docs_md" \
  --docs-json "$OUT/docs.json"

python -m structguard.cli security "$TARGET" --headers-only --deep \
  --html "$OUT/security.html" \
  --security-json "$OUT/security.json" \
  --rules-json "$OUT/security_rules.json"

python -m structguard.cli ci "$TARGET" --headers-only "${STRICT_ARGS[@]}" \
  --policy structguard.yml \
  --deep-security \
  --html "$OUT/ci.html" \
  --json "$OUT/ci.json" \
  --junit "$OUT/junit.xml" \
  --sarif "$OUT/structguard.sarif" \
  --summary-md "$OUT/summary.md"

printf 'Demostración limpia completada correctamente. Reportes generados en %s\n' "$OUT"