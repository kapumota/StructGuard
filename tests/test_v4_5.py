from pathlib import Path
from structguard.performance import build_performance_profiles, write_performance_json, write_growth_json, write_perf_harness, performance_report


def test_v4_5_performance_profiles(tmp_path: Path):
    h = tmp_path / "stack.h"
    h.write_text('''
class Stack {
  int n;
  int a[10];
public:
  void push(int x) { a[n] = x; n = n + 1; }
  int pop() { n = n - 1; return a[n]; }
};
''')
    profiles = build_performance_profiles(tmp_path, headers_only=True)
    assert profiles
    assert profiles[0].targets
    out = tmp_path / "perf.json"
    growth = tmp_path / "growth.json"
    harness = tmp_path / "harness.cpp"
    write_performance_json(profiles, out)
    write_growth_json(profiles, growth)
    write_perf_harness(profiles, harness)
    assert out.exists() and 'profiles' in out.read_text()
    assert growth.exists() and 'growth' in growth.read_text()
    assert harness.exists() and 'SGPerfCounters' in harness.read_text()
    report = performance_report(tmp_path, headers_only=True)
    assert any(d.code == 'PERF_SUMMARY' for d in report.diagnostics)
