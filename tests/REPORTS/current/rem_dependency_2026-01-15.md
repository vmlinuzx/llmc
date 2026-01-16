# Dependency Demon Scan Report - 2026-01-15

## Summary of Findings

| Severity | Type                  | Count | Description                                                                                             |
|----------|-----------------------|-------|---------------------------------------------------------------------------------------------------------|
| **P0**   | Dependency Conflict   | 1     | Unsolvable conflict in `requirements.txt` prevents installation and CVE scanning.                       |
| **P2**   | Environment Drift     | 1     | Significant drift between `requirements.txt` and the installed virtual environment.                     |
| **P3**   | Outdated Packages     | 78    | Numerous packages have newer versions available, including security and feature updates.                |
| -        | Blocked               | 1     | CVE scan could not be completed due to the critical dependency conflict.                                |

---

## P0 - Critical Issues

### 1. Unsolvable Dependency Conflict in `requirements.txt`

**Description:** A critical and unsolvable dependency conflict exists within `requirements.txt`. This prevents the creation of a stable, reproducible environment and blocks further security analysis like CVE scanning.

**Conflict Details:**
- `requirements.txt` explicitly requires `urllib3>=2.6.0`.
- The dependency `kubernetes==34.1.0` requires `urllib3<2.4.0`.

**Evidence:**
The following error was produced by `pip`:
```
ERROR: Cannot install kubernetes==34.1.0 and urllib3>=2.6.0 because these package versions have conflicting dependencies.

The conflict is caused by:
    The user requested urllib3>=2.6.0
    kubernetes 34.1.0 depends on urllib3<2.4.0 and >=1.24.2
```

**Recommendation:** Resolve this conflict immediately. This likely requires either downgrading the `urllib3` requirement or finding a version of the `kubernetes` client that is compatible with modern `urllib3` versions.

---

## P2 - Medium Issues

### 1. Environment Drift

**Description:** There is a significant drift between the packages defined in `requirements.txt` and the packages actually installed in the virtual environment. This makes it difficult to reproduce the environment and can lead to "works on my machine" issues.

**Drift Highlights:**
- **Packages Installed but not in `requirements.txt`:** `aiohttp`, `litellm`, `openai`, `detect-secrets`, and numerous `nvidia-*` packages are present in the environment but not specified in the requirements file. These should be added to `requirements.txt` to ensure reproducibility.
- **Incorrect Versions:**
    - `langchain-core` is specified as `>=1.2.5` but `1.1.0` is installed.
    - `urllib3` is specified as `>=2.6.0` but `2.3.0` is installed (due to the conflict).
- **Local Editable Install:** The local `llmc` package points to a different commit hash than what is in `requirements.txt`.

**Recommendation:**
1.  Run `pip freeze > requirements.txt` to capture the known-good state of the current environment.
2.  Manually review the captured list to remove any development-only tools (like `py-spy`, `ruff`, etc.) that should not be in the production dependencies.
3.  Address the P0 conflict before finalizing the new `requirements.txt`.

---

## P3 - Low Issues

### 1. Outdated Packages

**Description:** The environment contains 78 packages with newer versions available. While not all updates are critical, they can contain important bug fixes, performance improvements, and security patches.

**Recommendation:** Regularly update packages and test for regressions. Prioritize updates for packages with known security vulnerabilities once the CVE scan is unblocked.

**Details:** See the full list of outdated packages in the section below.

---

## Outdated Packages Details

| Package | Current Version | Latest Version | Type |
|---|---|---|---|
| anyio | 4.12.0 | 4.12.1 | wheel |
| build | 1.3.0 | 1.4.0 | wheel |
| cachetools | 6.2.2 | 6.2.4 | wheel |
| certifi | 2025.11.12 | 2026.1.4 | wheel |
| chromadb | 1.3.5 | 1.4.1 | wheel |
| coverage | 7.12.0 | 7.13.1 | wheel |
| fastapi | 0.121.3 | 0.128.0 | wheel |
| filelock | 3.20.1 | 3.20.3 | wheel |
| flatbuffers | 25.9.23 | 25.12.19 | wheel |
| fsspec | 2025.9.0 | 2026.1.0 | wheel |
| GitPython | 3.1.45 | 3.1.46 | wheel |
| google-auth | 2.43.0 | 2.47.0 | wheel |
| huggingface-hub | 0.36.0 | 1.3.2 | wheel |
| humanize | 4.14.0 | 4.15.0 | wheel |
| importlib_metadata | 8.7.0 | 8.7.1 | wheel |
| joblib | 1.5.2 | 1.5.3 | wheel |
| jsonschema | 4.25.1 | 4.26.0 | wheel |
| kubernetes | 34.1.0 | 35.0.0 | wheel |
| langchain | 1.0.8 | 1.2.4 | wheel |
| langchain-core | 1.1.0 | 1.2.7 | wheel |
| langgraph | 1.0.3 | 1.0.6 | wheel |
| langgraph-checkpoint | 3.0.1 | 4.0.0 | wheel |
| langgraph-prebuilt | 1.0.5 | 1.0.6 | wheel |
| langgraph-sdk | 0.2.9 | 0.3.3 | wheel |
| langsmith | 0.4.46 | 0.6.4 | wheel |
| librt | 0.7.4 | 0.7.8 | wheel |
| MarkupSafe | 2.1.5 | 3.0.3 | wheel |
| mcp | 1.24.0 | 1.25.0 | wheel |
| mistune | 3.1.4 | 3.2.0 | wheel |
| mypy | 1.18.2 | 1.19.1 | wheel |
| networkx | 3.5 | 3.6.1 | wheel |
| numpy | 2.3.5 | 2.4.1 | wheel |
| nvidia-cublas-cu12 | 12.8.4.1 | 12.9.1.4 | wheel |
| nvidia-cuda-cupti-cu12 | 12.8.90 | 12.9.79 | wheel |
| nvidia-cuda-nvrtc-cu12 | 12.8.93 | 12.9.86 | wheel |
| nvidia-cuda-runtime-cu12 | 12.8.90 | 12.9.79 | wheel |
| nvidia-cudnn-cu12 | 9.10.2.21 | 9.17.1.4 | wheel |
| nvidia-cufft-cu12 | 11.3.3.83 | 11.4.1.4 | wheel |
| nvidia-cufile-cu12 | 1.13.1.3 | 1.14.1.1 | wheel |
| nvidia-curand-cu12 | 10.3.9.90 | 10.3.10.19 | wheel |
| nvidia-cusolver-cu12 | 11.7.3.90 | 11.7.5.82 | wheel |
| nvidia-cusparse-cu12 | 12.5.8.93 | 12.5.10.65 | wheel |
| nvidia-cusparselt-cu12 | 0.7.1 | 0.8.1 | wheel |
| nvidia-nccl-cu12 | 2.27.5 | 2.29.2 | wheel |
| nvidia-nvjitlink-cu12 | 12.8.93 | 12.9.86 | wheel |
| nvidia-nvshmem-cu12 | 3.3.20 | 3.5.19 | wheel |
| nvidia-nvtx-cu12 | 12.8.90 | 12.9.79 | wheel |
| opentelemetry-api | 1.38.0 | 1.39.1 | wheel |
| opentelemetry-exporter-otlp-proto-common | 1.38.0 | 1.39.1 | wheel |
| opentelemetry-exporter-otlp-proto-grpc | 1.38.0 | 1.39.1 | wheel |
| opentelemetry-proto | 1.38.0 | 1.39.1 | wheel |
| opentelemetry-sdk | 1.38.0 | 1.39.1 | wheel |
| orjson | 3.11.4 | 3.11.5 | wheel |
| ormsgpack | 1.12.0 | 1.12.1 | wheel |
| pathspec | 0.12.1 | 1.0.3 | wheel |
| pillow | 12.0.0 | 12.1.0 | wheel |
| pip | 24.0 | 25.3 | wheel |
| platformdirs | 4.5.0 | 4.5.1 | wheel |
| posthog | 5.4.0 | 7.5.1 | wheel |
| protobuf | 6.33.1 | 6.33.4 | wheel |
| psutil | 7.1.3 | 7.2.1 | wheel |
| pybase64 | 1.4.2 | 1.4.3 | wheel |
| pyparsing | 3.2.5 | 3.3.1 | wheel |
| PyPika | 0.48.9 | 0.50.0 | wheel |
| pytest | 9.0.1 | 9.0.2 | wheel |
| regex | 2025.11.3 | 2026.1.15 | wheel |
| ruff | 0.14.6 | 0.14.13 | wheel |
| scikit-learn | 1.7.2 | 1.8.0 | wheel |
| scipy | 1.16.3 | 1.17.0 | wheel |
| sentence-transformers | 5.1.2 | 5.2.0 | wheel |
| sse-starlette | 3.0.4 | 3.1.2 | wheel |
| starlette | 0.50.0 | 0.51.0 | wheel |
| textual | 6.7.1 | 7.3.0 | wheel |
| tokenizers | 0.22.1 | 0.22.2 | wheel |
| tomli | 2.3.0 | 2.4.0 | wheel |
| tomlkit | 0.13.3 | 0.14.0 | wheel |
| transformers | 4.57.1 | 4.57.5 | wheel |
| tree_sitter | 0.20.1 | 0.25.2 | wheel |
| tree-sitter-languages | 1.9.1 | 1.10.2 | wheel |
| typer | 0.20.0 | 0.21.1 | wheel |
| types-requests | 2.32.4.20250913 | 2.32.4.20260107 | wheel |
| urllib3 | 2.3.0 | 2.6.3 | wheel |
| uuid_utils | 0.12.0 | 0.13.0 | wheel |
| uvicorn | 0.38.0 | 0.40.0 | wheel |
| websockets | 15.0.1 | 16.0 | wheel |
