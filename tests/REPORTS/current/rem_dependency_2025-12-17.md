# Rem's Dependency Analysis Report - 2025-12-17

This report details the findings of a dependency analysis conducted on the `llmc` repository.

## 1. Security Vulnerabilities

A security audit was performed using `pip-audit`. The following vulnerabilities were found:

```
Found 8 known vulnerabilities in 5 packages
Name       Version ID             Fix Versions
---------- ------- -------------- ------------
filelock   3.19.1  CVE-2025-68146 3.20.1
mcp        1.22.0  CVE-2025-66416 1.23.0
pip        24.0    CVE-2025-8869  25.3
setuptools 70.2.0  PYSEC-2025-49  78.1.1
urllib3    2.3.0   CVE-2025-50182 2.5.0
urllib3    2.3.0   CVE-2025-50181 2.5.0
urllib3    2.3.0   CVE-2025-66418 2.6.0
urllib3    2.3.0   CVE-2025-66471 2.6.0

The following packages could not be audited:
Name        Skip Reason
----------- --------------------------------------------------------------------------
llmcwrapper Dependency not found on PyPI and could not be audited: llmcwrapper (0.6.2)
torch       Dependency not found on PyPI and could not be audited: torch (2.9.1+cpu)
```

## 2. Outdated Packages

The following packages are outdated and can be updated. Keeping dependencies up-to-date can improve security, performance, and stability.

```
Package                                  Version  Latest    Type
---------------------------------------- -------- --------- -----
anyio                                    4.11.0   4.12.0    wheel
cachetools                               6.2.2    6.2.4     wheel
chromadb                                 1.3.5    1.3.7     wheel
coverage                                 7.12.0   7.13.0    wheel
fastapi                                  0.121.3  0.124.4   wheel
filelock                                 3.19.1   3.20.1    wheel
fsspec                                   2025.9.0 2025.12.0 wheel
google-auth                              2.43.0   2.45.0    wheel
huggingface-hub                          0.36.0   1.2.3     wheel
joblib                                   1.5.2    1.5.3     wheel
langchain                                1.0.8    1.2.0     wheel
langchain-core                           1.1.0    1.2.2     wheel
langgraph                                1.0.3    1.0.5     wheel
langgraph-sdk                            0.2.9    0.3.0     wheel
langsmith                                0.4.46   0.5.0     wheel
MarkupSafe                               2.1.5    3.0.3     wheel
mcp                                      1.22.0   1.24.0    wheel
mypy                                     1.18.2   1.19.1    wheel
networkx                                 3.5      3.6.1     wheel
opentelemetry-api                        1.38.0   1.39.1    wheel
opentelemetry-exporter-otlp-proto-common 1.38.0   1.39.1    wheel
opentelemetry-exporter-otlp-proto-grpc   1.38.0   1.39.1    wheel
opentelemetry-proto                      1.38.0   1.39.1    wheel
opentelemetry-sdk                        1.38.0   1.39.1    wheel
orjson                                   3.11.4   3.11.5    wheel
ormsgpack                                1.12.0   1.12.1    wheel
pip                                      24.0     25.3      wheel
platformdirs                             4.5.0    4.5.1     wheel
posthog                                  5.4.0    7.4.0     wheel
protobuf                                 6.33.1   6.33.2    wheel
pybase64                                 1.4.2    1.4.3     wheel
pydantic                                 2.12.4   2.12.5    wheel
pytest                                   9.0.1    9.0.2     wheel
python-multipart                         0.0.20   0.0.21    wheel
rpds-py                                  0.29.0   0.30.0    wheel
ruff                                     0.14.6   0.14.9    wheel
scikit-learn                             1.7.2    1.8.0     wheel
sentence-transformers                    5.1.2    5.2.0     wheel
setuptools                               70.2.0   80.9.0    wheel
sse-starlette                            3.0.3    3.0.4     wheel
textual                                  6.7.1    6.10.0    wheel
transformers                             4.57.1   4.57.3    wheel
tree_sitter                              0.20.1   0.25.2    wheel
tree-sitter-languages                    1.9.1    1.10.2    wheel
urllib3                                  2.3.0    2.6.2     wheel
```

## 3. Dependency Usage Analysis

An analysis was performed with `deptry` to identify discrepancies between declared dependencies and actual usage in the codebase.

### Unused Dependencies
The following packages are declared as dependencies but do not appear to be used. They may be candidates for removal.
* `setuptools`
* `langchain`
* `humanize`
* `pytest-cov`
* `mypy`
* `types-toml`
* `types-requests`
* `ruff`

### Missing Dependencies
The following packages are imported in the code but are not listed as explicit dependencies in `pyproject.toml`. They should be added to ensure reproducible builds.
* `tiktoken`
* `spacy`
* `scispacy`
* `medspacy`
* `pyinotify`
* `_setup_path` (likely an internal script, may not need to be a formal dependency)
* `ast_chunker` (likely internal)
* `index_workspace` (likely internal)

### Transitive Dependencies
The following packages are used in the code but are not direct dependencies. Relying on transitive dependencies can be risky, as they may be removed or have their versions changed by an update to the parent package. Consider making them direct dependencies if their functionality is critical.
* `toml`
* `torch`
* `transformers`
* `numpy`
* `pydantic`
* `starlette`

## 4. Conclusion

The dependency analysis reveals several areas for improvement:
1.  **Critical Security Vulnerabilities:** There are 8 known vulnerabilities across 5 packages, including `urllib3`, `setuptools`, and `pip`. These should be addressed immediately by updating to the recommended `Fix Versions`.
2.  **Widespread Outdated Packages:** A large number of packages are outdated. A comprehensive update is recommended to improve security and leverage new features.
3.  **Dependency Mismatches:** There are significant discrepancies between the declared dependencies in `pyproject.toml` and the packages actually used in the code. This can lead to build failures and an inflated dependency footprint.

**Recommendations:**
1.  Prioritize updating the packages with known security vulnerabilities.
2.  Perform a full update of all outdated packages.
3.  Review the "Unused" and "Missing" dependency lists to clean up `pyproject.toml`, ensuring it accurately reflects the project's needs.
4.  Consider adding important "Transitive" dependencies as direct project dependencies.

This concludes the dependency analysis report.
