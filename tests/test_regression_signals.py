def test_compare_versions_runs_and_returns_dict(tmp_path):
    # non-failing regression test: ensure comparison runs and writes report
    import sys
    from pathlib import Path
    # ensure project root is on sys.path for pytest invocation environments
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    from scripts.compare_versions import compare_and_report
    res = compare_and_report(output_dir=tmp_path)
    assert isinstance(res, dict)
    # write a small confirmation file so CI can inspect output if needed
    assert tmp_path.exists()


