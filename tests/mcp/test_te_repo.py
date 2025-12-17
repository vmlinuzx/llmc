from llmc_mcp.tools import te_repo


class DummyCtx:
    def __init__(self):
        self.agent_id = "agent-xyz"
        self.session_id = "sess-9999"
        self.model = "athena-qwen"


def test_repo_read_builds_args(monkeypatch):
    captured = {}

    def fake_te_run(args, ctx=None, **kw):
        captured["args"] = list(args)
        return {"data": {"ok": True, "args": args}, "meta": {"returncode": 0}}

    monkeypatch.setattr(te_repo, "te_run", fake_te_run)
    ctx = DummyCtx()
    res = te_repo.repo_read("/repo", "README.md", max_bytes=1024, ctx=ctx)  # noqa: F841
    assert res["data"]["ok"] is True
    assert captured["args"][:3] == ["repo", "read", "--root"]
    assert "--max-bytes" in captured["args"]


def test_rag_query_builds_args_and_filters(monkeypatch):
    captured = {}

    def fake_te_run(args, ctx=None, **kw):
        captured["args"] = list(args)
        return {"data": {"ok": True}, "meta": {"returncode": 0}}

    monkeypatch.setattr(te_repo, "te_run", fake_te_run)
    res = te_repo.rag_query(
        "howdy", k=3, index="default", filters={"lang": "py"}
    )  # noqa: F841
    assert captured["args"][:2] == ["rag", "query"]
    assert "--q" in captured["args"]
    assert "--k" in captured["args"]
    assert "--index" in captured["args"]
    assert "--filters" in captured["args"]


def test_rag_query_handles_bad_filters(monkeypatch):
    def bad_default(o):
        raise RuntimeError("nope")

    def fake_te_run(args, ctx=None, **kw):
        return {"data": {"ok": True}, "meta": {"returncode": 0}}

    monkeypatch.setattr(te_repo, "te_run", fake_te_run)

    class Bad:
        pass

    # Should not raise even if filters can't be JSON-encoded
    te_repo.rag_query("x", filters={"bad": Bad()})
