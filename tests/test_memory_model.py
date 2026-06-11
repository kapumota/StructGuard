from __future__ import annotations

from pathlib import Path

from structguard.analyzers.memory_safety import analyze_memory_safety_project
from structguard.memory import build_memory_models


def _write_header(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "MemoryCases.hpp"
    path.write_text(text, encoding="utf-8")
    return path


def _codes(root: Path) -> set[str]:
    report = analyze_memory_safety_project(root)
    return {diagnostic.code for diagnostic in report.diagnostics}


def test_memory_model_detects_correct_new_array_pair(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class CorrectArray {
    int* data;
    int size_;
    int capacity_;
public:
    CorrectArray(int capacity) : data(new int[capacity]), size_(0), capacity_(capacity) {}
    ~CorrectArray() { delete[] data; data = nullptr; }
    void push(int value) {
        if (size_ < capacity_) {
            data[size_] = value;
            size_++;
        }
    }
};
""",
    )

    codes = _codes(path)

    assert "MEM_ARRAY_OWNERSHIP_OK" in codes
    assert "MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY" not in codes
    assert "MEM_DELETE_KIND_MISMATCH" not in codes


def test_memory_model_detects_new_array_without_delete(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class MissingDelete {
    int* data;
public:
    MissingDelete(int capacity) : data(new int[capacity]) {}
};
""",
    )

    assert "MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY" in _codes(path)


def test_memory_model_detects_double_delete(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class DoubleDelete {
    int* data;
public:
    DoubleDelete(int capacity) : data(new int[capacity]) {}
    ~DoubleDelete() {
        delete[] data;
        delete[] data;
    }
};
""",
    )

    assert "MEM_DOUBLE_DELETE" in _codes(path)


def test_memory_model_detects_possible_null_dereference(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class NullDeref {
    int* data = nullptr;
public:
    int first() const {
        return *data;
    }
};
""",
    )

    assert "MEM_NULL_DEREF_RISK" in _codes(path)


def test_memory_model_detects_capacity_size_mismatch(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class BadCapacity {
    int* data;
    int size_;
    int capacity_;
public:
    BadCapacity(int capacity) : data(new int[capacity]), size_(0), capacity_(capacity) {}
    void corrupt() {
        size_ = capacity_ + 1;
    }
    ~BadCapacity() { delete[] data; }
};
""",
    )

    assert "MEM_CAPACITY_SIZE_MISMATCH" in _codes(path)


def test_memory_model_exposes_class_inventory(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Inventory {
    int* data = nullptr;
public:
    Inventory() {}
};
""",
    )

    models = build_memory_models(path)

    assert len(models) == 1
    assert models[0].class_name == "Inventory"
    assert models[0].pointer_fields[0].name == "data"
    assert models[0].pointer_fields[0].initialized_null is True
