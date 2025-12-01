# llmc_mcp/benchmarks/test_runner.py
from llmc_mcp.benchmarks import runner


def _ok(meta=None, data=None):
    return {
        "data": data or {"ok": True},
        "meta": {"returncode": 0, **(meta or {})},
    }


def test_run_cases_with_monkeypatched_wrappers(monkeypatch, tmp_path):
    # Force output dir
    monkeypatch.setenv("LLMC_BENCH_OUTDIR", str(tmp_path))

    # Monkeypatch wrapper functions to avoid real subprocess/TE
    monkeypatch.setattr(runner, "te_run", lambda args: _ok(data={"echo": args[-1]}), raising=False)
    monkeypatch.setattr(
        runner,
        "repo_read",
        lambda root, path, max_bytes=None: _ok(data={"path": path}),
        raising=False,
    )
    monkeypatch.setattr(runner, "rag_query", lambda q, k=3: _ok(data={"k": k}), raising=False)

    rows = runner.run_cases(["te_echo", "repo_read_small", "rag_top3"])
    assert len(rows) == 3
    assert all(r.ok for r in rows)

    # Emit CSV and ensure file exists
    out = runner._emit_csv(rows)
    assert str(tmp_path) in out
