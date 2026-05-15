#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "La demostración final de StructGuard está dividida en dos fases explícitas:"
echo "  1. demostración CI limpia: debe finalizar correctamente"
echo "  2. demostración con bug intencional: el comando debe fallar y el script verificará la falla esperada"

bash scripts/demo_clean_ci.sh examples/stack_ok.h
bash scripts/demo_bug_detection.sh examples/stack_bug.h

printf 'Demostración final completada. Revisa report/demo_clean y report/demo_bug.\n'