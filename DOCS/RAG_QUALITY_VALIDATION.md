# RAG Data Quality Validation System

**Created:** 2025-11-12  
**Status:** Implemented and Integrated

---

## Overview

The RAG Quality Validation System provides ongoing monitoring and validation of enrichment data quality to prevent:
- Fake/placeholder summaries from polluting the index
- Empty or missing critical fields
- Low-quality generic summaries
- Model misconfigurations

---

## Components

### 1. Standalone Quality Checker
**File:** `/home/vmlinux/src/llmc/scripts/rag_quality_check.py`

Comprehensive CLI tool for detailed analysis and reporting.

**Usage:**
```bash
# Basic check (human-readable report)
python3 scripts/rag_quality_check.py /path/to/repo

# JSON output (for automation)
python3 scripts/rag_quality_check.py /path/to/repo --json

# Auto-fix (delete fake data)
python3 scripts/rag_quality_check.py /path/to/repo --fix

# Quiet mode (summary only)
python3 scripts/rag_quality_check.py /path/to/repo --quiet
```

**Features:**
- Detects fake "auto-summary generated offline" data
- Identifies empty/missing fields
- Finds low-quality generic summaries
- Checks model distribution
- Calculates quality score (0-100)
- Can auto-delete bad data with `--fix`

---

### 2. Service Integration Module
**File:** `/home/vmlinux/src/llmc/tools/rag/quality.py`

Lightweight module for integration into the RAG service.

**Features:**
- Quick quality checks during service runs
- Minimal overhead
- Returns structured results

**Usage:**
```python
from tools.rag.quality import run_quality_check, format_quality_summary

result = run_quality_check(repo_path)
print(format_quality_summary(result, repo.name))

# result contains:
# {
#     'quality_score': 95.5,
#     'status': 'PASS',  # or 'FAIL', 'NO_DB', 'EMPTY'
#     'fake_count': 0,
#     'empty_count': 1,
#     'low_quality_count': 2,
#     'total': 150,
#     'checked_at': '2025-11-12T...'
# }
```

---

### 3. Automatic Service Integration
**File:** `/home/vmlinux/src/llmc/tools/rag/service.py` (modified)

Quality checks are now integrated into the RAG service daemon.

**Configuration:**
```bash
export ENRICH_QUALITY_CHECK=on   # Default: on (set to 'off' to disable)
```

**Behavior:**
- Runs after each repo processing cycle
- Reports quality score and issues
- Logs quality failures to failure tracker
- Non-blocking (enrichment continues even if quality check fails)

---

## Quality Checks Performed

### 1. Fake Data Detection
Identifies placeholder/fake summaries:
- "auto-summary generated offline"
- "TODO: implement"
- "PLACEHOLDER"
- Generic file:line patterns

### 2. Empty Field Detection
Finds enrichments with:
- Summaries < 10 characters
- Both inputs and outputs empty
- Missing critical fields

### 3. Low Quality Detection
Identifies generic/poor summaries:
- < 5 words
- Starts with "This code...", "The function..."
- Contains "undefined", "unknown", "N/A"

### 4. Model Validation
Checks for:
- Suspicious model names ("unknown", "default", "placeholder")
- Unexpected model distribution
- Model consistency

---

## Quality Scoring

**Formula:**
```
problems = fake_count + empty_count + low_quality_count
quality_score = max(0, 100 - (problems / total * 100))
```

**Thresholds:**
- ✅ **PASS:** ≥ 90% (< 10% problems)
- ⚠️ **FAIL:** < 90% (≥ 10% problems)

---

## Example Outputs

### Good Quality (PASS)
```
======================================================================
RAG DATA QUALITY REPORT
======================================================================

📊 Statistics:
  Total enrichments: 250
  Recent (24h): 45

🎯 Quality Score: 96.8/100 - PASS

🤖 Model Distribution:
  qwen2.5:7b-instruct-q4_K_M: 180 (72.0%)
  qwen2.5:14b-instruct-q4_K_M: 65 (26.0%)
  gpt-4o-mini: 5 (2.0%)

🚨 Issues Found:
  Fake/placeholder data: 0
  Empty/missing fields: 3
  Low-quality summaries: 5

======================================================================
```

### Bad Quality (FAIL)
```
======================================================================
RAG DATA QUALITY REPORT
======================================================================

📊 Statistics:
  Total enrichments: 100
  Recent (24h): 100

🎯 Quality Score: 5.0/100 - FAIL

🤖 Model Distribution:
  local-qwen: 100 (100.0%)
  ⚠️  Warnings:
    - Suspicious model name: local-qwen (100 enrichments)

🚨 Issues Found:
  Fake/placeholder data: 95  ⚠️
  Empty/missing fields: 0
  Low-quality summaries: 0

❌ Fake Data Examples:
  - a1b2c3d4e5f6... | src/utils.py:10-50 auto-summary generated offline.
    Model: local-qwen | Reason: Known fake placeholder text
  - b2c3d4e5f6g7... | src/config.py:5-30 auto-summary generated offline.
    Model: local-qwen | Reason: Known fake placeholder text
  ... and 90 more

======================================================================
```

---

## Service Integration Example

### Console Output
```
🚀 RAG service started (PID 12345)
   Tracking 1 repos
   Interval: 180s

🔄 Processing llmc...
  ℹ️  No file changes detected
  🤖 Enriching with: backend=ollama, router=on, tier=7b
  ✅ Enriched pending spans with real LLM summaries
  ✅ Generated embeddings (limit=100)
  ✅ llmc: Quality 95.2% (250 enrichments)
  ✅ llmc processing complete
💤 Sleeping 180s until next cycle...
```

### With Quality Issues
```
🔄 Processing llmc...
  ✅ Synced 5 changed files
  🤖 Enriching with: backend=ollama, router=on, tier=7b
  ✅ Enriched pending spans with real LLM summaries
  ✅ Generated embeddings (limit=100)
  ⚠️  llmc: Quality 75.0% (100 enrichments, issues: 15 fake, 5 empty, 5 low-quality)
  ✅ llmc processing complete
```

---

## Automation & CI/CD Integration

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

python3 scripts/rag_quality_check.py . --quiet
if [ $? -ne 0 ]; then
    echo "⚠️  RAG quality check failed. Run 'python3 scripts/rag_quality_check.py .' for details"
    exit 1
fi
```

### CI/CD Pipeline
```yaml
# .github/workflows/rag-quality.yml
name: RAG Quality Check
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check RAG quality
        run: |
          python3 scripts/rag_quality_check.py . --json > quality-report.json
          python3 -c "
          import json, sys
          report = json.load(open('quality-report.json'))
          if report['status'] != 'PASS':
              sys.exit(1)
          "
      - name: Upload report
        uses: actions/upload-artifact@v2
        with:
          name: quality-report
          path: quality-report.json
```

---

## Monitoring & Alerting

### Cron Job for Daily Reports
```bash
# Add to crontab: crontab -e
0 9 * * * cd /home/vmlinux/src/llmc && python3 scripts/rag_quality_check.py . --quiet | mail -s "Daily RAG Quality Report" admin@example.com
```

### Alert on Quality Drop
```bash
#!/bin/bash
# check-and-alert.sh

QUALITY=$(python3 scripts/rag_quality_check.py . --json | jq '.quality_score')

if (( $(echo "$QUALITY < 90" | bc -l) )); then
    echo "⚠️  RAG quality dropped to $QUALITY%" | mail -s "RAG Quality Alert" admin@example.com
fi
```

---

## Cleaning Up Bad Data

### Manual Cleanup
```bash
# Check what will be deleted
python3 scripts/rag_quality_check.py /path/to/repo

# Confirm and delete
python3 scripts/rag_quality_check.py /path/to/repo --fix
```

### Automatic Cleanup Script
```bash
#!/bin/bash
# auto-cleanup.sh - Run weekly via cron

cd /home/vmlinux/src/llmc

for repo in $(./scripts/llmc-rag-service status | grep "registered" | cut -d' ' -f2); do
    echo "Cleaning $repo..."
    python3 scripts/rag_quality_check.py "$repo" --fix --quiet
done
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENRICH_QUALITY_CHECK` | `on` | Enable/disable quality checks in service |

### Service Behavior

**Enabled (default):**
- Quality check runs after each repo cycle
- Reports summary to console
- Logs failures to failure tracker
- Does NOT block enrichment

**Disabled:**
```bash
export ENRICH_QUALITY_CHECK=off
./llmc-rag-service start
```

---

## Troubleshooting

### "No RAG database found"
**Cause:** Repo hasn't been indexed yet  
**Fix:** Run `python -m tools.rag.cli index` first

### High fake data count
**Cause:** Service was running with broken enrichment code  
**Fix:** 
1. Stop service
2. Apply the enrichment fix (already done)
3. Run `python3 scripts/rag_quality_check.py /path/to/repo --fix`
4. Restart service

### Quality check slowing down service
**Cause:** Large databases  
**Fix:** Disable for now: `export ENRICH_QUALITY_CHECK=off`

---

## Future Enhancements

Potential improvements:
1. **Semantic analysis** - Check if summary actually relates to code
2. **Duplicate detection** - Find identical summaries for different code
3. **Consistency checks** - Verify inputs/outputs match code
4. **Drift detection** - Alert when quality trends downward
5. **Auto-remediation** - Automatically re-enrich failed spans

---

## Summary

✅ **Implemented:**
- Standalone quality checker (`rag_quality_check.py`)
- Service integration module (`quality.py`)
- Automatic quality checks in daemon
- Comprehensive reporting
- Auto-fix capability

✅ **Features:**
- Detects fake/placeholder data
- Identifies empty/low-quality enrichments
- Model distribution validation
- Quality scoring (0-100)
- Pass/fail thresholds

✅ **Integration:**
- Runs automatically in service (configurable)
- Non-blocking (doesn't stop enrichment)
- Logs failures to tracker
- Easy to automate

---

**Status: PRODUCTION READY** 🎉

The quality validation system is fully implemented and integrated into the RAG service!
