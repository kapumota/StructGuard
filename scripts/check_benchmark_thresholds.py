from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# Este script valida un reporte de benchmark ya generado.
# La lógica se mantiene separada del workflow para que también pueda ejecutarse localmente.
def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el reporte de benchmark: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def collect_failures(report: dict[str, Any]) -> list[str]:
    thresholds = report.get("thresholds", {})
    failures: list[str] = []
    for metric, result in sorted(thresholds.items()):
        if bool(result.get("passed", False)):
            continue
        actual = result.get("actual")
        expected = result.get("expected")
        operator = result.get("operator", ">=")
        failures.append(f"{metric}: valor actual {actual} no cumple {operator} {expected}")
    return failures


def print_summary(report: dict[str, Any]) -> None:
    metrics = report.get("metrics", {})
    print("Resumen de benchmark")
    print("--------------------")
    for key in (
        "precision",
        "recall",
        "false_positive_rate",
        "false_positive_count",
        "false_negative_count",
        "analysis_time_ms_per_file",
        "mutation_detection_rate",
    ):
        if key in metrics:
            print(f"{key}: {metrics[key]}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida umbrales de un reporte de benchmark de StructGuard.")
    parser.add_argument("report", type=Path, help="Ruta a artifacts/benchmark-report.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = load_report(args.report)
    print_summary(report)
    failures = collect_failures(report)
    if failures:
        print("Umbrales no alcanzados")
        print("----------------------")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Todos los umbrales de benchmark fueron alcanzados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
