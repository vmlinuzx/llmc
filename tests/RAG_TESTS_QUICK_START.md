# LLMC RAG Tests - Quick Start Guide

## Overview
Comprehensive test suite for the LLMC RAG (Retrieval-Augmented Generation) system covering 9 categories with 17 tests total.

## Quick Test Run

```bash
# Run all tests (recommended)
python3 test_rag_comprehensive.py

# Run with verbose output
python3 test_rag_comprehensive.py --verbose

# Run specific test by name
python3 test_rag_comprehensive.py --filter="test_search_basic"

# Check exit code for CI/CD
python3 test_rag_comprehensive.py && echo "SUCCESS" || echo "FAILED"
```

## Test Categories

### 1. Config & CLI (3 tests)
- CLI help and command structure
- Subcommand documentation
- Error handling for invalid flags

### 2. Database & Index (2 tests)
- Fresh database creation
- Idempotent re-indexing
- Schema validation

### 3. Embeddings & Caching (1 test)
- Embedding job execution
- Cache behavior

### 4. Enrichment & Indexing (2 tests)
- File discovery and filtering
- Incremental updates

### 5. Planner & Context (1 test)
- Query plan generation
- Context selection

### 6. Search & Relevance (3 tests)
- Basic keyword search
- Semantic search
- No-results handling

### 7. Service Layer (1 test)
- Web server startup
- FastAPI integration

### 8. Logging & Observability (1 test)
- Health checks
- Diagnostics

### 9. End-to-End (3 tests)
- Cold start workflow
- Question answering
- Error exit codes

## What Gets Tested

Each test creates a temporary isolated repository with:
- Python source files
- Documentation
- Binary files (for filtering tests)

Then executes RAG commands and verifies:
- Command success/failure
- Output format
- Database state
- Error handling

## Test Output

### Console Output
```
✓ PASS [Category] TestName: Description
✗ FAIL [Category] TestName: Description
  Details: {json}
```

### Files Created
- `rag_test_report.json` - Detailed JSON report with all results
- `RAG_TEST_SUMMARY.md` - This summary document

### Report Structure
```json
{
  "summary": {
    "total": 17,
    "passed": 17,
    "failed": 0,
    "success_rate": 100.0
  },
  "by_category": {...},
  "tests": [...]
}
```

## Expected Behavior

### ✅ All Tests Pass (100%)
Indicates the RAG system is fully functional:
- All CLI commands work
- Database operations correct
- Search functionality operational
- No regressions detected

### ❌ Some Tests Fail (0-99%)
Indicates issues:
- Check console output for details
- Review specific failed tests
- Examine test details in JSON report

### Environment Requirements
- Python 3.x with virtual environment
- LLMC repo at `/home/vmlinux/src/llmc`
- All RAG dependencies installed
- No existing `.rag` directories in test locations

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run RAG Tests
  run: |
    cd /home/vmlinux/src/llmc
    python3 test_rag_comprehensive.py
    if [ $? -ne 0 ]; then
      echo "RAG tests failed"
      cat rag_test_report.json
      exit 1
    fi
```

### Local Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
cd /home/vmlinux/src/llmc
python3 test_rag_comprehensive.py --filter="test_e2e_cold_start" || exit 1
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'tools'"
- Run from `/home/vmlinux/src/llmc` directory
- Ensure virtual environment activated
- PYTHONPATH should include repo root

### "Error while finding module specification"
- Run: `source .venv/bin/activate`
- Or use: `/home/vmlinux/src/llmc/.venv/bin/python3 test_rag_comprehensive.py`

### Tests timeout
- Increase timeout in test code (default 30-60s)
- Check system resources
- Review verbose output

### Database errors
- Tests use temporary directories
- Should not affect production data
- Clean up: `rm -rf /tmp/rag_test_*`

## Test Customization

### Add New Test
```python
def test_my_feature(self):
    """Test description"""
    start = time.time()
    try:
        # Test logic
        result = self.run([...])
        if result.returncode == 0:
            self.add_result(
                "my_feature",
                "My Category",
                True,
                "Success message",
                (time.time() - start) * 1000
            )
        else:
            self.add_result(...)
    except Exception as e:
        self.add_result(...)
```

### Modify Timeout
```python
self.run([...], timeout=120)  # 2 minutes
```

### Add Debug Output
```python
self.verbose = True  # At class init
# Or
self.log("Debug message")
```

## Best Practices

1. **Run all tests** before committing changes
2. **Use verbose mode** when debugging
3. **Check JSON report** for detailed results
4. **Isolate tests** - don't rely on production data
5. **Clean up** - tests auto-clean temporary files

## References

- **Test Suite**: `/home/vmlinux/src/llmc/test_rag_comprehensive.py`
- **Test Report**: `/home/vmlinux/src/llmc/rag_test_report.json`
- **Summary**: `/home/vmlinux/src/llmc/RAG_TEST_SUMMARY.md`
- **RAG CLI**: `python3 -m tools.rag.cli --help`
- **RAG Code**: `tools/rag/` directory

## Support

If tests fail:
1. Check console output for errors
2. Review `rag_test_report.json`
3. Ensure all dependencies installed
4. Verify Python environment
5. Check disk space for temp files

---

**Last Updated**: 2025-11-16
**Test Version**: 1.0
**LLMC Version**: Current branch
