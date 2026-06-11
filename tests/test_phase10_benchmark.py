from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "benchmarks" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("phase10_benchmark_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_mutators():
    path = Path(__file__).resolve().parents[1] / "benchmarks" / "mutations" / "mutators.py"
    spec = importlib.util.spec_from_file_location("phase10_mutators", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ground_truth_yaml_subset_loads_cases() -> None:
    runner = _load_runner()
    root = Path(__file__).resolve().parents[1]
    data = runner.load_yaml_subset(root / "benchmarks" / "ground_truth.yaml")

    assert "SG-STACK-POP-EMPTY" in data["tracked_rules"]
    assert len(data["cases"]) >= 8
    assert len(data["mutations"]) >= 5


def test_mutation_changes_stack_guard() -> None:
    mutators = _load_mutators()
    source = Path("benchmarks/corpus/correct/ArrayStackOk.hpp").read_text(encoding="utf-8")
    result = mutators.apply_mutation(
        "ArrayStackOk.hpp",
        source,
        "remove_empty_guard_from_stack_pop",
        ["SG-STACK-POP-EMPTY"],
    )

    assert result.changed
    assert "return data[--n];" in result.content
    assert "SG-STACK-POP-EMPTY" in result.expected_findings


def test_additional_mutations_are_available() -> None:
    mutators = _load_mutators()

    assert "remove_capacity_guard_from_stack_push" in mutators.available_mutations()
    assert "omit_queue_size_decrement" in mutators.available_mutations()


def test_metrics_count_precision_recall_and_mutations() -> None:
    runner = _load_runner()
    results = [
        runner.CaseResult(
            case_id="ok",
            path="ok.hpp",
            kind="correct",
            expected_findings=[],
            actual_findings=[],
            true_positives=[],
            false_positives=[],
            false_negatives=[],
            analysis_time_ms=10,
            return_code=0,
            generated=False,
            mutation=None,
        ),
        runner.CaseResult(
            case_id="bug",
            path="bug.hpp",
            kind="buggy",
            expected_findings=["A", "B"],
            actual_findings=["A", "C"],
            true_positives=["A"],
            false_positives=["C"],
            false_negatives=["B"],
            analysis_time_ms=20,
            return_code=1,
            generated=False,
            mutation=None,
        ),
        runner.CaseResult(
            case_id="mut",
            path="mut.hpp",
            kind="mutation",
            expected_findings=["M"],
            actual_findings=["M"],
            true_positives=["M"],
            false_positives=[],
            false_negatives=[],
            analysis_time_ms=30,
            return_code=1,
            generated=True,
            mutation="demo",
        ),
    ]

    metrics = runner.compute_metrics(results)

    assert metrics["precision"] == 0.6667
    assert metrics["recall"] == 0.6667
    assert metrics["false_positive_count"] == 1
    assert metrics["false_negative_count"] == 1
    assert metrics["mutation_detection_rate"] == 1.0
