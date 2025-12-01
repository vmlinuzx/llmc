
import json
import types
import subprocess
from llmc_mcp.tools import te as te_module

class DummyCtx:
    def __init__(self):
        self.agent_id = "agent-123"
        self.session_id = "sess-abc"
        self.model = "qwen-2.5-32b"

def test_te_run_injects_json_and_env(monkeypatch):
    captured = {}
    def fake_run(argv, stdout, stderr, cwd, timeout, env, text, check):
        captured['argv'] = argv
        captured['env'] = env
        # Simulate TE --json stdout
        out = json.dumps({"ok": True, "echo": argv[-1] if argv else None})
        cp = types.SimpleNamespace(returncode=0, stdout=out, stderr="")
        return cp

    monkeypatch.setattr(subprocess, "run", fake_run)
    ctx = DummyCtx()
    res = te_module.te_run(["run", "echo", "hello"], ctx=ctx)
    assert res["data"]["ok"] is True
    assert "--json" in captured["argv"]
    # namespaced env and legacy
    assert captured["env"]["LLMC_TE_SESSION_ID"] == ctx.session_id
    assert captured["env"]["TE_SESSION_ID"] == ctx.session_id

def test_te_run_handles_non_json_stdout(monkeypatch):
    def fake_run(argv, stdout, stderr, cwd, timeout, env, text, check):
        return types.SimpleNamespace(returncode=0, stdout="not json", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    res = te_module.te_run(["status"])
    assert "raw" in res["data"]

def test_te_run_failure_path(monkeypatch):
    def fake_run(argv, stdout, stderr, cwd, timeout, env, text, check):
        raise RuntimeError("boom")
    monkeypatch.setattr(subprocess, "run", fake_run)
    res = te_module.te_run(["oops"])
    assert res["meta"]["error"] is True
    assert res["meta"]["returncode"] == -1
