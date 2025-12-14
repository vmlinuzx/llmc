# Medical RAG Benchmark Documentation

This document outlines the benchmark targets, methodology, and procedures for evaluating the Medical RAG (Retrieval-Augmented Generation) system.

## Target Metrics

The following performance targets have been established for the medical RAG system:

| Metric | Target | Description |
|--------|--------|-------------|
| Section Detection Accuracy | ≥ 0.95 | Accuracy of identifying medical note section headers |
| Negation Detection F1 Score | ≥ 0.90 | F1 score for detecting negated conditions in clinical text |
| PHI Coverage | ≥ 0.99 | Proportion of Protected Health Information correctly identified |
| Search Pipeline Success Rate | ≥ 0.80 | Percentage of medical queries returning relevant results |
| End-to-End Latency | < 2.0 seconds | Time from query to first result (95th percentile) |
| Retrieval Precision@5 | ≥ 0.85 | Precision of top 5 retrieved documents for medical queries |

## How to Run Benchmarks

### Prerequisites

1. **Index Medical Documents**: Ensure the RAG database contains medical documents
   ```bash
   python -m tools.rag.index --repo-root /path/to/repo --medical
   ```

2. **Install Test Dependencies**:
   ```bash
   pip install pytest pytest-benchmark scikit-learn
   ```

### Running Integration Tests

The main integration tests can be run with:

```bash
cd /path/to/repo
pytest tests/test_medical_integration.py -v
```

### Running Performance Benchmarks

For latency and throughput measurements:

```bash
python -m pytest tests/test_medical_integration.py::TestMedicalRAGIntegration::test_full_search_pipeline --benchmark-only
```

### Generating Reports

To generate a comprehensive benchmark report:

```bash
python -c "
import sys
sys.path.insert(0, '.')
from tests.test_medical_integration import TestMedicalRAGIntegration
import pytest

# Run tests and collect metrics
pytest.main(['tests/test_medical_integration.py', '-v', '--tb=short'])
"
```

## Sample Results Format

### Integration Test Results

```
MEDICAL RAG INTEGRATION TEST METRICS
============================================================
section_detection_accuracy       Target: 0.950  Status: PASS
negation_detection_f1            Target: 0.900  Status: PASS  
phi_coverage                     Target: 0.990  Status: PASS
search_pipeline_success          Target: 0.800  Status: PASS
============================================================
```

### Performance Benchmark Results

```json
{
  "benchmark_date": "2024-03-20",
  "metrics": {
    "section_detection_accuracy": 0.97,
    "negation_detection_f1": 0.92,
    "phi_coverage": 0.995,
    "search_latency_p95_ms": 1450,
    "retrieval_precision_at_5": 0.88,
    "throughput_queries_per_second": 8.5
  },
  "environment": {
    "python_version": "3.11.0",
    "platform": "Linux",
    "rag_database_size_mb": 2450,
    "medical_documents_count": 12500
  }
}
```

## Test Data

Benchmarks use synthetic medical notes located at:
- `tests/fixtures/medical/sample_notes.json`

Additional test data can be added to:
- `tests/fixtures/medical/benchmark_queries.json` - Medical search queries
- `tests/fixtures/medical/golden_answers.json` - Expected results for evaluation

## Validation Methodology

### Section Detection
- **Method**: Pattern matching for common medical section headers
- **Evaluation**: Exact match against annotated test data
- **Calculation**: `accuracy = correct_detections / total_sections`

### Negation Detection  
- **Method**: ClinicalRelationExtractor with pattern matching
- **Evaluation**: Compare against manually annotated negations
- **Calculation**: Standard F1 score (harmonic mean of precision and recall)

### PHI Coverage
- **Method**: Regular expression patterns for PHI types (names, IDs, dates, etc.)
- **Evaluation**: Proportion of annotated PHI instances detected
- **Calculation**: `coverage = detected_phi / total_phi`

### Search Pipeline
- **Method**: Execute representative medical queries through RAG search
- **Evaluation**: Manual relevance assessment of top 5 results
- **Calculation**: `success_rate = relevant_results / total_queries`

## Continuous Integration

Benchmarks are integrated into CI/CD pipeline:

```yaml
# Example GitHub Actions configuration
- name: Run Medical RAG Benchmarks
  run: |
    pytest tests/test_medical_integration.py --junitxml=test-results.xml
    python scripts/generate_benchmark_report.py --output benchmark-report.json
```

## Troubleshooting

### Common Issues

1. **Low Section Detection Accuracy**
   - Ensure test data includes proper section headers
   - Check for case sensitivity in detection logic

2. **Poor Negation Detection F1**
   - Verify ClinicalRelationExtractor is properly initialized
   - Check that test data includes clear negation cues ("denies", "no history of")

3. **PHI Coverage Below Target**
   - Update PHI detection patterns to match test data
   - Consider adding custom patterns for institution-specific PHI formats

4. **Search Pipeline Failures**
   - Confirm RAG database is built with medical documents
   - Verify search queries are relevant to indexed content

## Future Enhancements

Planned benchmark improvements:
- Add multilingual medical text support
- Include temporal reasoning tests
- Add clinical coding accuracy metrics
- Incorporate patient cohort retrieval benchmarks

## Contact

For questions about medical RAG benchmarks, contact the Clinical AI team or open an issue in the repository.
