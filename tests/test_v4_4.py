from pathlib import Path
from structguard.fuzz import collect_fuzz_cases, write_cpp_tests, write_fuzz_json, write_replay_script, write_seed_corpus

def test_v4_4_fuzz_artifacts(tmp_path):
    root = Path('examples')
    cases = collect_fuzz_cases(root, headers_only=True, seeds=2, steps=4)
    assert cases
    j = tmp_path / 'fuzz.json'; write_fuzz_json(root, cases, j); assert j.exists()
    r = tmp_path / 'replay.py'; write_replay_script(root, cases, r); assert r.exists()
    c = tmp_path / 'corpus'; write_seed_corpus(root, cases, c); assert (c / 'manifest.json').exists()
    m = write_cpp_tests(root, True, tmp_path / 'tests', seeds=2, steps=4, only_failures=False)
    assert m.exists()
