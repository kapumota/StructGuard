#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

rm -rf .pytest_cache src/structguard/__pycache__ tests/__pycache__

STRICT_DEV="${STRUCTGUARD_STRICT_DEV:-0}"

run_dev_tool() {
  local module="$1"
  shift
  if python -c "import ${module}" >/dev/null 2>&1; then
    python -m "$module" "$@"
  elif [[ "$STRICT_DEV" == "1" ]]; then
    echo "ERROR: el módulo de Python '${module}' no está instalado. Instala las dependencias de desarrollo con: python -m pip install -e '.[dev]'" >&2
    exit 1
  else
    echo "ADVERTENCIA: se omite ${module}; instala las dependencias de desarrollo o define STRUCTGUARD_STRICT_DEV=1 para exigirlo." >&2
  fi
}

python -m structguard.cli --version
python -m structguard.cli doctor . --json report/doctor.json
python -m compileall -q src tests
run_dev_tool ruff check .
run_dev_tool mypy
python -m pytest -q

# Salidas canónicas de reporte estilo CI, equivalentes a los nombres de artefactos de GitHub Actions.
mkdir -p report
python -m structguard.cli ci examples/stack_ok.h \
  --headers-only \
  --deep-security \
  --html report/structguard-ci.html \
  --json report/structguard-ci.json \
  --junit report/structguard-junit.xml \
  --sarif report/structguard.sarif \
  --summary-md report/structguard-summary.md

python scripts/validate_outputs.py --profile ci --dir report

bash scripts/demo_clean_ci.sh examples/stack_ok.h
python scripts/validate_outputs.py --profile demo-clean --dir report/demo_clean

bash scripts/demo_bug_detection.sh examples/stack_bug.h
python scripts/validate_outputs.py --profile demo-bug --dir report/demo_bug

python scripts/validate_outputs.py --profile doctor --dir report

find report -maxdepth 3 -type f | sort

printf 'Validación de release completada. Usa STRUCTGUARD_STRICT_DEV=1 para hacer que la ausencia de ruff/mypy sea un error obligatorio.\n'