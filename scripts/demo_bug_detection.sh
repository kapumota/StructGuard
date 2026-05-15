#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

TARGET="${1:-examples/stack_bug.h}"
OUT="report/demo_bug"
mkdir -p "$OUT"

STRICT_ARGS=()
if command -v clang++ >/dev/null 2>&1 || command -v clang >/dev/null 2>&1; then
  STRICT_ARGS=(--strict-ast --std c++17)
else
  echo "ADVERTENCIA: no se encontró clang/clang++; la demostración del bug se ejecutará sin --strict-ast." >&2
fi

echo "Ejecutando demostración con bug intencional sobre ${TARGET}."
echo "Resultado esperado: salida distinta de cero porque BuggyStack::pop viola el invariante size_ >= 0."

set +e
python -m structguard.cli analyze "$TARGET" --headers-only "${STRICT_ARGS[@]}" \
  --html "$OUT/bug_analysis.html" \
  --json "$OUT/bug_analysis.json" \
  > "$OUT/bug_analysis.txt" 2>&1
STATUS=$?
set -e

cat "$OUT/bug_analysis.txt"

if [[ "$STATUS" -eq 0 ]]; then
  echo "ERROR: se esperaba que la demostración del bug fallara, pero StructGuard terminó correctamente." >&2
  exit 1
fi

python - <<'PY'
import json
from pathlib import Path

path = Path('report/demo_bug/bug_analysis.json')
data = json.loads(path.read_text(encoding='utf-8'))
diags = data.get('diagnostics', [])

expected = [
    d for d in diags
    if d.get('level') == 'FAILED'
    and d.get('code') == 'INVARIANT_NOT_PRESERVED'
    and d.get('symbol') == 'BuggyStack::pop'
]

if not expected:
    raise SystemExit(
        'No se encontró en bug_analysis.json la falla esperada del invariante en BuggyStack::pop'
    )

print('Bug intencional confirmado: BuggyStack::pop viola el invariante size_ >= 0.')
PY

printf 'Demostración de detección de bugs completada correctamente. Reportes generados en %s\n' "$OUT"