from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BENCHMARKS_DIR = Path(__file__).resolve().parent
if str(BENCHMARKS_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS_DIR))

from mutations import apply_mutation


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    path: Path
    kind: str
    expected_findings: set[str]
    generated: bool = False
    mutation: str | None = None


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    path: str
    kind: str
    expected_findings: list[str]
    actual_findings: list[str]
    true_positives: list[str]
    false_positives: list[str]
    false_negatives: list[str]
    analysis_time_ms: int
    return_code: int
    generated: bool
    mutation: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path": self.path,
            "kind": self.kind,
            "expected_findings": self.expected_findings,
            "actual_findings": self.actual_findings,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "analysis_time_ms": self.analysis_time_ms,
            "return_code": self.return_code,
            "generated": self.generated,
            "mutation": self.mutation,
        }


# Este parser cubre solo el subconjunto YAML usado por benchmarks/ground_truth.yaml.
# Se mantiene sin dependencias externas para que el benchmark pueda correr en CI mínimo.
def load_yaml_subset(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    result: dict[str, Any] = {}
    section: str | None = None
    current_item: dict[str, Any] | None = None
    pending_list_key: str | None = None

    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            result[section] = [] if section in {"tracked_rules", "cases", "mutations"} else {}
            current_item = None
            pending_list_key = None
            continue

        if section is None:
            raise ValueError(f"Línea fuera de sección en {path}: {raw_line}")

        if section == "tracked_rules":
            if line.startswith("- "):
                result[section].append(line[2:].strip())
            continue

        if section == "settings":
            key, value = _split_key_value(line, path)
            result[section][key] = _parse_scalar(value)
            continue

        if section in {"cases", "mutations"}:
            if indent == 2 and line.startswith("- "):
                current_item = {}
                result[section].append(current_item)
                pending_list_key = None
                first = line[2:].strip()
                if first:
                    key, value = _split_key_value(first, path)
                    current_item[key] = _parse_scalar(value)
                continue
            if current_item is None:
                raise ValueError(f"Elemento YAML inválido en {path}: {raw_line}")
            if indent == 4:
                key, value = _split_key_value(line, path)
                if value == "":
                    current_item[key] = []
                    pending_list_key = key
                else:
                    current_item[key] = _parse_scalar(value)
                    pending_list_key = None
                continue
            if indent == 6 and line.startswith("- ") and pending_list_key:
                current_item[pending_list_key].append(line[2:].strip())
                continue
        raise ValueError(f"No se pudo interpretar línea YAML en {path}: {raw_line}")
    return result


def _split_key_value(line: str, path: Path) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"Se esperaba clave: valor en {path}: {line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value.strip('"\'')


def load_thresholds(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    data: dict[str, float] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = _split_key_value(line, path)
        data[key] = float(value)
    return data


def build_cases(root: Path, ground_truth: dict[str, Any], generated_dir: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for item in ground_truth.get("cases", []):
        cases.append(
            BenchmarkCase(
                case_id=str(item["id"]),
                path=root / str(item["path"]),
                kind=str(item.get("kind", "manual")),
                expected_findings=set(item.get("expected_findings") or []),
            )
        )

    generated_dir.mkdir(parents=True, exist_ok=True)
    for item in ground_truth.get("mutations", []):
        source_path = root / str(item["source"])
        source = source_path.read_text(encoding="utf-8")
        expected = list(item.get("expected_findings") or [])
        mutation = apply_mutation(source_path.name, source, str(item["mutation"]), expected)
        out_path = generated_dir / f"{item['id']}.hpp"
        out_path.write_text(mutation.content, encoding="utf-8")
        cases.append(
            BenchmarkCase(
                case_id=str(item["id"]),
                path=out_path,
                kind="mutation",
                expected_findings=set(expected),
                generated=True,
                mutation=str(item["mutation"]),
            )
        )
    return cases


def run_case(root: Path, case: BenchmarkCase, tracked_rules: set[str], profile: str, preset: str, output_dir: Path, timeout: int) -> CaseResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    findings_path = output_dir / f"{case.case_id}.findings.json"
    command = [
        sys.executable,
        "-m",
        "structguard.cli",
        "scan",
        str(case.path),
        "--profile",
        profile,
        "--preset",
        preset,
        "--headers-only",
        "--findings-json",
        str(findings_path),
    ]
    env = os.environ.copy()
    src_path = str(root / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, timeout=timeout, check=False)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    actual = read_actual_findings(findings_path, tracked_rules)
    expected = set(case.expected_findings)
    return CaseResult(
        case_id=case.case_id,
        path=str(case.path.relative_to(root) if case.path.is_relative_to(root) else case.path),
        kind=case.kind,
        expected_findings=sorted(expected),
        actual_findings=sorted(actual),
        true_positives=sorted(expected & actual),
        false_positives=sorted(actual - expected),
        false_negatives=sorted(expected - actual),
        analysis_time_ms=elapsed_ms,
        return_code=completed.returncode,
        generated=case.generated,
        mutation=case.mutation,
    )


def read_actual_findings(path: Path, tracked_rules: set[str]) -> set[str]:
    if not path.exists():
        return set()
    document = json.loads(path.read_text(encoding="utf-8"))
    actual: set[str] = set()
    for finding in document.get("findings", []):
        rule_id = str(finding.get("rule_id", ""))
        if rule_id in tracked_rules:
            actual.add(rule_id)
    return actual


def compute_metrics(results: list[CaseResult]) -> dict[str, Any]:
    true_positive_count = sum(len(result.true_positives) for result in results)
    false_positive_count = sum(len(result.false_positives) for result in results)
    false_negative_count = sum(len(result.false_negatives) for result in results)
    precision_denominator = true_positive_count + false_positive_count
    recall_denominator = true_positive_count + false_negative_count
    precision = true_positive_count / precision_denominator if precision_denominator else 1.0
    recall = true_positive_count / recall_denominator if recall_denominator else 1.0
    mutation_results = [result for result in results if result.kind == "mutation"]
    detected_mutations = [result for result in mutation_results if result.true_positives]
    mutation_detection_rate = len(detected_mutations) / len(mutation_results) if mutation_results else 0.0
    rules_triggered = Counter(rule for result in results for rule in result.actual_findings)
    total_time = sum(result.analysis_time_ms for result in results)
    return {
        "case_count": len(results),
        "true_positive_count": true_positive_count,
        "false_positive_count": false_positive_count,
        "false_negative_count": false_negative_count,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_positive_rate": round(false_positive_count / max(1, true_positive_count + false_positive_count), 4),
        "analysis_time_ms_total": total_time,
        "analysis_time_ms_per_file": round(total_time / max(1, len(results)), 2),
        "mutation_detection_rate": round(mutation_detection_rate, 4),
        "rules_triggered": dict(sorted(rules_triggered.items())),
    }


def evaluate_thresholds(metrics: dict[str, Any], thresholds: dict[str, float]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for key, expected in thresholds.items():
        if key not in metrics:
            continue
        actual = float(metrics[key])
        if key in {"false_positive_rate", "analysis_time_ms_per_file"}:
            passed = actual <= expected
            operator = "<="
        else:
            passed = actual >= expected
            operator = ">="
        results[key] = {"actual": actual, "expected": expected, "operator": operator, "passed": passed}
    return results


def build_report(root: Path, args: argparse.Namespace) -> dict[str, Any]:
    ground_truth = load_yaml_subset(args.ground_truth)
    settings = ground_truth.get("settings", {})
    profile = args.profile or str(settings.get("profile", "generic-cpp"))
    preset = args.preset or str(settings.get("preset", "security"))
    tracked_rules = set(str(rule) for rule in ground_truth.get("tracked_rules", []))
    generated_dir = args.generated_dir
    cases = build_cases(root, ground_truth, generated_dir)
    case_output_dir = args.output.parent / "benchmark-cases"
    results = [run_case(root, case, tracked_rules, profile, preset, case_output_dir, args.timeout) for case in cases]
    metrics = compute_metrics(results)
    thresholds = load_thresholds(args.thresholds)
    threshold_results = evaluate_thresholds(metrics, thresholds)
    return {
        "schema_version": "structguard-benchmark/v1",
        "tool": "StructGuard",
        "phase": "10",
        "description": "Corpus mínimo y benchmark de regresión",
        "profile": profile,
        "preset": preset,
        "ground_truth": str(args.ground_truth.relative_to(root) if args.ground_truth.is_relative_to(root) else args.ground_truth),
        "tracked_rules": sorted(tracked_rules),
        "metrics": metrics,
        "thresholds": threshold_results,
        "cases": [result.as_dict() for result in results],
    }


def print_summary(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    print("Benchmark de regresión StructGuard")
    print(f"Casos evaluados: {metrics['case_count']}")
    print(f"Precision: {metrics['precision']}")
    print(f"Recall: {metrics['recall']}")
    print(f"Falsos positivos: {metrics['false_positive_count']}")
    print(f"Falsos negativos: {metrics['false_negative_count']}")
    print(f"Tiempo medio por archivo: {metrics['analysis_time_ms_per_file']} ms")
    print(f"Mutation detection rate: {metrics['mutation_detection_rate']}")
    print("Reglas activadas:")
    for rule, count in metrics["rules_triggered"].items():
        print(f"  {rule}: {count}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Ejecuta el corpus mínimo de regresión de StructGuard.")
    parser.add_argument("--ground-truth", type=Path, default=root / "benchmarks" / "ground_truth.yaml")
    parser.add_argument("--thresholds", type=Path, default=root / "benchmarks" / "thresholds.yml")
    parser.add_argument("--output", type=Path, default=root / "artifacts" / "benchmark-report.json")
    parser.add_argument("--generated-dir", type=Path, default=root / "artifacts" / "generated_mutations")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--preset", default=None)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--fail-on-threshold", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(root, args)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print_summary(report)
    print(f"Reporte escrito en: {args.output}")
    if args.fail_on_threshold and any(not item["passed"] for item in report["thresholds"].values()):
        print("Uno o más umbrales no fueron alcanzados.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
