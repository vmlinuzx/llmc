# Learnings from Wave 1 - 1.Y Bug Fixes

## [2026-01-25 15:45] Tasks 2.1-2.3: urllib3 Dependency Fix

### Problem
- urllib3>=2.6.0 conflicts with kubernetes 34.1.0 requirement of urllib3<2.4.0,>=1.24.2
- This prevented litellm installation and broke DeepSeek integration tests

### Solution
- Changed pyproject.toml line 12 from `urllib3>=2.6.0` to `urllib3>=1.24.2,<2.4.0`
- Verified: No direct urllib3 imports in llmc/ or llmc_mcp/ (transitive dependency only)
- Reinstalled in .venv with `pip install -e ".[agent]"`
- urllib3 downgraded from 2.6.3 → 2.3.0

### Verification
- ✅ All three packages import successfully: urllib3 2.3.0, litellm 1.80.16, kubernetes 34.1.0
- ✅ No import errors

## [2026-01-25 15:47] Tasks 3.1-3.5: DeepSeek Integration Testing

### Discovery
- Tests require `--allow-network` flag due to pytest_ruthless plugin
- Without flag: "Network is blocked by pytest_ruthless. Use --allow-network"

### Commands That Work
```bash
# Individual test
pytest tests/rlm/test_integration_deepseek.py::test_rlm_deepseek_code_analysis -v --allow-network

# All DeepSeek tests
pytest tests/rlm/test_integration_deepseek.py -v --allow-network

# Full RLM suite
pytest tests/rlm/ -v --allow-network
```

### Results
- ✅ 43/43 RLM tests passing (baseline was 41 passed, 2 skipped)
- ✅ Both DeepSeek integration tests now pass
- ✅ Budget enforcement test passes
- ⚠️ Some pydantic serialization warnings (non-blocking)
- ⚠️ Runtime warning about coroutine cleanup (non-blocking)

## Conventions Discovered

### Environment Setup
- Project uses `.venv` directory for virtual environment
- Always activate venv before pip operations: `source .venv/bin/activate`
- System Python is externally managed (requires venv or --break-system-packages)

### Testing Pattern
- Integration tests that hit external APIs need `--allow-network` flag
- Test suite location: `tests/rlm/`
- Evidence should be saved to: `.sisyphus/evidence/`

## Success Metrics
- Baseline: 41 passed, 2 skipped → After fix: 43 passed, 0 skipped
- urllib3 conflict: RESOLVED
- DeepSeek integration: WORKING

## [2026-01-25 15:50] Task 4.1: Full Test Suite Verification

### RLM Tests
- ✅ 43/43 RLM tests passing with --allow-network flag
- ✅ DeepSeek integration working
- ✅ Budget enforcement working
- ✅ No regressions from urllib3 downgrade

### Other Test Modules
- ✅ 113 passed in tests/rlm/ tests/mcp/ tests/agent/test_litellm_backends.py
- ❌ 7 failed in MCP code_exec tests (pre-existing, async fixture issues - unrelated to urllib3)
- ❌ 1 failed in test_openai_compat_backend (pre-existing, 401 Unauthorized - unrelated to urllib3)

### Conclusion
urllib3 fix did NOT introduce any regressions. All RLM functionality working as expected.

